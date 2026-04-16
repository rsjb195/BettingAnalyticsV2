"""
Dixon-Coles Poisson probability model.

Implements the Dixon & Coles (1997) approach to football match prediction:
1. Attack/Defence ratings per team (home and away separately)
2. Poisson-distributed goal expectations
3. Low-score correction factor (rho) for 0-0, 1-0, 0-1, 1-1
4. Time-decay weighting (recent matches contribute more)
5. Edge calculation against market odds

Reference:
    Dixon, M. & Coles, S. (1997). "Modelling Association Football Scores
    and Inefficiencies in the Football Betting Market."
"""

import logging
import math
from datetime import date, timedelta
from typing import NamedTuple

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend.app.models.match import Match
from backend.app.models.team import Team
from backend.app.models.accumulator import ModelOutput

logger = logging.getLogger("analytics.probability")

MAX_GOALS = 10  # Maximum goals to consider in scoreline enumeration


class MatchProbabilities(NamedTuple):
    """Model output for a single match."""
    home_win: float
    draw: float
    away_win: float
    expected_home_goals: float
    expected_away_goals: float
    home_fair_odds: float
    draw_fair_odds: float
    away_fair_odds: float
    confidence: float
    scoreline_probs: dict  # {(h, a): prob}


class TeamRatings(NamedTuple):
    """Attack and defence ratings for a team."""
    attack_home: float
    defence_home: float
    attack_away: float
    defence_away: float
    matches_used: int


def _time_decay_weight(match_date: date, reference_date: date, half_life_days: int = 180) -> float:
    """
    Exponential time-decay weight.

    More recent matches have higher weight. A match played `half_life_days`
    ago receives weight 0.5.

    Args:
        match_date: Date of the match.
        reference_date: Reference date (usually today).
        half_life_days: Half-life in days (default 180 = ~6 months).

    Returns:
        Weight between 0 and 1.
    """
    days_ago = (reference_date - match_date).days
    if days_ago < 0:
        return 0.0
    return math.exp(-0.693 * days_ago / half_life_days)


def _dixon_coles_rho(home_goals: int, away_goals: int, lambda_h: float, lambda_a: float, rho: float) -> float:
    """
    Dixon-Coles correction factor for low-scoring outcomes.

    Adjusts the independence assumption of the bivariate Poisson model
    for scorelines (0,0), (1,0), (0,1), (1,1).

    Args:
        home_goals: Home team goals.
        away_goals: Away team goals.
        lambda_h: Expected home goals.
        lambda_a: Expected away goals.
        rho: Correlation parameter (typically small, ~-0.05 to 0.05).

    Returns:
        Correction multiplier (close to 1 for non-low scores).
    """
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lambda_h * lambda_a * rho
    elif home_goals == 0 and away_goals == 1:
        return 1.0 + lambda_h * rho
    elif home_goals == 1 and away_goals == 0:
        return 1.0 + lambda_a * rho
    elif home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    else:
        return 1.0


def calculate_team_ratings(
    league_id: int,
    session: Session,
    reference_date: date | None = None,
    min_matches: int = 5,
    half_life_days: int = 180,
) -> dict[int, TeamRatings]:
    """
    Calculate attack and defence ratings for all teams in a league.

    Uses weighted historical match data with time decay. Separate
    home and away ratings account for the home advantage effect.

    Args:
        league_id: Database league ID.
        session: SQLAlchemy session.
        reference_date: Date to calculate from (default: today).
        min_matches: Minimum matches required for reliable rating.
        half_life_days: Half-life for time decay weighting.

    Returns:
        Dict mapping team_id to TeamRatings.
    """
    if reference_date is None:
        reference_date = date.today()

    # Fetch all completed matches for this league
    matches = session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "complete",
            Match.home_goals.isnot(None),
            Match.away_goals.isnot(None),
        ).order_by(Match.match_date)
    ).scalars().all()

    if not matches:
        return {}

    # Calculate league averages (weighted)
    total_home_goals_w = 0.0
    total_away_goals_w = 0.0
    total_weight = 0.0

    for m in matches:
        w = _time_decay_weight(m.match_date, reference_date, half_life_days)
        total_home_goals_w += m.home_goals * w
        total_away_goals_w += m.away_goals * w
        total_weight += w

    if total_weight == 0:
        return {}

    league_avg_home_goals = total_home_goals_w / total_weight
    league_avg_away_goals = total_away_goals_w / total_weight
    league_avg_goals = (league_avg_home_goals + league_avg_away_goals) / 2

    if league_avg_goals == 0:
        league_avg_goals = 1.35  # fallback

    # Per-team weighted stats
    team_stats: dict[int, dict] = {}

    for m in matches:
        w = _time_decay_weight(m.match_date, reference_date, half_life_days)

        for team_id, is_home in [(m.home_team_id, True), (m.away_team_id, False)]:
            if team_id not in team_stats:
                team_stats[team_id] = {
                    "home_scored_w": 0.0, "home_conceded_w": 0.0, "home_w": 0.0, "home_n": 0,
                    "away_scored_w": 0.0, "away_conceded_w": 0.0, "away_w": 0.0, "away_n": 0,
                }

            s = team_stats[team_id]
            if is_home:
                s["home_scored_w"] += m.home_goals * w
                s["home_conceded_w"] += m.away_goals * w
                s["home_w"] += w
                s["home_n"] += 1
            else:
                s["away_scored_w"] += m.away_goals * w
                s["away_conceded_w"] += m.home_goals * w
                s["away_w"] += w
                s["away_n"] += 1

    # Calculate ratings
    ratings: dict[int, TeamRatings] = {}

    for team_id, s in team_stats.items():
        total_n = s["home_n"] + s["away_n"]
        if total_n < min_matches:
            continue

        # Attack rating = team's scoring rate / league average
        # Defence rating = team's conceding rate / league average
        attack_home = (s["home_scored_w"] / s["home_w"] / league_avg_home_goals) if s["home_w"] > 0 else 1.0
        defence_home = (s["home_conceded_w"] / s["home_w"] / league_avg_away_goals) if s["home_w"] > 0 else 1.0
        attack_away = (s["away_scored_w"] / s["away_w"] / league_avg_away_goals) if s["away_w"] > 0 else 1.0
        defence_away = (s["away_conceded_w"] / s["away_w"] / league_avg_home_goals) if s["away_w"] > 0 else 1.0

        ratings[team_id] = TeamRatings(
            attack_home=attack_home,
            defence_home=defence_home,
            attack_away=attack_away,
            defence_away=defence_away,
            matches_used=total_n,
        )

    logger.info("Calculated ratings for %d teams in league %d.", len(ratings), league_id)
    return ratings


def predict_match(
    home_team_id: int,
    away_team_id: int,
    ratings: dict[int, TeamRatings],
    league_avg_goals: float = 1.35,
    home_advantage: float = 1.2,
    rho: float = -0.04,
) -> MatchProbabilities | None:
    """
    Predict match probabilities using the Dixon-Coles model.

    Args:
        home_team_id: Database home team ID.
        away_team_id: Database away team ID.
        ratings: Pre-calculated team ratings dict.
        league_avg_goals: Average goals per team per match in the league.
        home_advantage: Home advantage multiplier (typically 1.15-1.25).
        rho: Dixon-Coles low-score correlation parameter.

    Returns:
        MatchProbabilities or None if either team lacks ratings.
    """
    home_r = ratings.get(home_team_id)
    away_r = ratings.get(away_team_id)

    if not home_r or not away_r:
        return None

    # Expected goals
    lambda_home = home_r.attack_home * away_r.defence_away * league_avg_goals * home_advantage
    lambda_away = away_r.attack_away * home_r.defence_home * league_avg_goals

    # Sanity bounds
    lambda_home = max(0.2, min(lambda_home, 5.0))
    lambda_away = max(0.2, min(lambda_away, 5.0))

    # Calculate scoreline probabilities with Dixon-Coles correction
    scoreline_probs = {}
    home_win_prob = 0.0
    draw_prob = 0.0
    away_win_prob = 0.0

    for h in range(MAX_GOALS + 1):
        for a in range(MAX_GOALS + 1):
            base_prob = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
            dc_correction = _dixon_coles_rho(h, a, lambda_home, lambda_away, rho)
            prob = base_prob * max(dc_correction, 0.0)

            scoreline_probs[(h, a)] = prob

            if h > a:
                home_win_prob += prob
            elif h == a:
                draw_prob += prob
            else:
                away_win_prob += prob

    # Normalise probabilities (they should sum close to 1, but floating point)
    total = home_win_prob + draw_prob + away_win_prob
    if total > 0:
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

    # Fair odds (1 / probability)
    home_fair = 1 / home_win_prob if home_win_prob > 0 else 999
    draw_fair = 1 / draw_prob if draw_prob > 0 else 999
    away_fair = 1 / away_win_prob if away_win_prob > 0 else 999

    # Confidence rating (1-10)
    min_matches = min(home_r.matches_used, away_r.matches_used)
    if min_matches >= 30:
        confidence = 8.0
    elif min_matches >= 20:
        confidence = 7.0
    elif min_matches >= 10:
        confidence = 5.5
    elif min_matches >= 5:
        confidence = 4.0
    else:
        confidence = 2.0

    # Adjust confidence based on lambda reasonableness
    if lambda_home > 3.5 or lambda_away > 3.5:
        confidence -= 1.0
    if abs(lambda_home - lambda_away) > 2.0:
        confidence -= 0.5

    confidence = max(1.0, min(confidence, 10.0))

    return MatchProbabilities(
        home_win=round(home_win_prob, 6),
        draw=round(draw_prob, 6),
        away_win=round(away_win_prob, 6),
        expected_home_goals=round(lambda_home, 3),
        expected_away_goals=round(lambda_away, 3),
        home_fair_odds=round(home_fair, 3),
        draw_fair_odds=round(draw_fair, 3),
        away_fair_odds=round(away_fair, 3),
        confidence=round(confidence, 1),
        scoreline_probs={f"{h}-{a}": round(p, 6) for (h, a), p in sorted(scoreline_probs.items()) if p > 0.005},
    )


def calculate_edge(
    our_prob: float,
    market_odds: float | None,
) -> float | None:
    """
    Calculate our edge vs market odds.

    Edge = our_probability - implied_market_probability.
    Positive edge means we think this outcome is more likely than the market.

    Args:
        our_prob: Our model's probability for this outcome.
        market_odds: Decimal market odds (e.g. 2.50).

    Returns:
        Edge as a decimal (e.g. 0.05 = 5% edge), or None if no market odds.
    """
    if market_odds is None or market_odds <= 0:
        return None
    implied_prob = 1 / market_odds
    return round(our_prob - implied_prob, 6)


def generate_model_output(
    match: Match,
    predictions: MatchProbabilities,
    session: Session,
) -> ModelOutput:
    """
    Create a ModelOutput record for a match.

    Calculates edge against market odds and determines the best value outcome.

    Args:
        match: Match ORM object.
        predictions: MatchProbabilities from predict_match.
        session: SQLAlchemy session.

    Returns:
        ModelOutput object (added to session but not committed).
    """
    home_edge = calculate_edge(predictions.home_win, match.odds_home)
    draw_edge = calculate_edge(predictions.draw, match.odds_draw)
    away_edge = calculate_edge(predictions.away_win, match.odds_away)

    # Determine best value outcome
    edges = {
        "home": home_edge or -999,
        "draw": draw_edge or -999,
        "away": away_edge or -999,
    }
    best = max(edges, key=edges.get)
    if edges[best] <= 0:
        best_value = "none"
    else:
        best_value = best

    output = ModelOutput(
        match_id=match.id,
        our_home_prob=float(predictions.home_win),
        our_draw_prob=float(predictions.draw),
        our_away_prob=float(predictions.away_win),
        our_home_odds=float(predictions.home_fair_odds),
        our_draw_odds=float(predictions.draw_fair_odds),
        our_away_odds=float(predictions.away_fair_odds),
        market_home_odds=float(match.odds_home or 0),
        market_draw_odds=float(match.odds_draw or 0),
        market_away_odds=float(match.odds_away or 0),
        home_edge_pct=float(home_edge) if home_edge is not None else None,
        draw_edge_pct=float(draw_edge) if draw_edge is not None else None,
        away_edge_pct=float(away_edge) if away_edge is not None else None,
        best_value_outcome=best_value,
        confidence_rating=float(predictions.confidence),
        model_version="dixon_coles_v1",
    )

    session.add(output)
    logger.debug(
        "Model output for match %d: H=%.3f D=%.3f A=%.3f | Best: %s (edge=%.4f)",
        match.id, predictions.home_win, predictions.draw, predictions.away_win,
        best_value, edges.get(best_value, 0),
    )

    return output


def run_model_for_league(league_id: int, session: Session) -> int:
    """
    Run the probability model for all upcoming matches in a league.

    Calculates team ratings, generates predictions, and stores model outputs.

    Args:
        league_id: Database league ID.
        session: SQLAlchemy session.

    Returns:
        Number of model outputs generated.
    """
    logger.info("Running Dixon-Coles model for league %d...", league_id)

    # Calculate ratings
    ratings = calculate_team_ratings(league_id, session)
    if not ratings:
        logger.warning("No ratings could be calculated for league %d.", league_id)
        return 0

    # Calculate league average goals
    completed = session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "complete",
            Match.home_goals.isnot(None),
        )
    ).scalars().all()

    if not completed:
        return 0

    total_goals = sum((m.home_goals + m.away_goals) for m in completed)
    avg_goals_per_team = total_goals / (2 * len(completed))

    # Get upcoming matches
    upcoming = session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "upcoming",
        )
    ).scalars().all()

    generated = 0
    for match in upcoming:
        predictions = predict_match(
            match.home_team_id,
            match.away_team_id,
            ratings,
            league_avg_goals=avg_goals_per_team,
        )

        if predictions:
            generate_model_output(match, predictions, session)
            generated += 1

    session.commit()
    logger.info("Generated %d model outputs for league %d.", generated, league_id)
    return generated
