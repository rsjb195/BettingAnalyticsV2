"""
Accumulator builder engine.

Finds optimal accumulator combinations from available value selections,
targeting specific combined odds ranges (25/1 to 40/1) while maximising
expected value.

Key features:
  - Filters outcomes by minimum edge threshold
  - Scores each outcome by edge * confidence
  - Combinatorial search for target odds with tolerance bands
  - Calculates compounding bookmaker margin across legs
  - Returns top-N combinations ranked by expected value
"""

import logging
from itertools import combinations
from typing import NamedTuple

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.accumulator import AccumulatorLog, ModelOutput
from backend.app.models.match import Match
from backend.app.models.team import Team

logger = logging.getLogger("analytics.accumulator")


class AccumulatorLeg(NamedTuple):
    """Single leg of an accumulator."""
    match_id: int
    home_team: str
    away_team: str
    selection: str  # home / draw / away
    odds: float
    our_probability: float
    edge_pct: float
    confidence: float
    score: float


class AccumulatorCombination(NamedTuple):
    """Complete accumulator combination."""
    legs: list[AccumulatorLeg]
    combined_odds: float
    our_win_probability: float
    expected_value: float
    potential_return: float
    compound_margin: float
    positive_ev: bool


def _get_available_outcomes(
    session: Session,
    min_edge: float = 0.02,
) -> list[AccumulatorLeg]:
    """
    Retrieve all upcoming match outcomes with positive edge above threshold.

    Args:
        session: SQLAlchemy session.
        min_edge: Minimum edge percentage (decimal) to include.

    Returns:
        List of AccumulatorLeg objects sorted by score (edge * confidence).
    """
    # Get latest model output per upcoming match
    upcoming_matches = session.execute(
        select(Match).where(Match.status == "upcoming")
    ).scalars().all()

    available: list[AccumulatorLeg] = []
    seen = set()

    for match in upcoming_matches:
        if match.id in seen:
            continue
        seen.add(match.id)

        mo = session.execute(
            select(ModelOutput)
            .where(ModelOutput.match_id == match.id)
            .order_by(desc(ModelOutput.generated_at))
            .limit(1)
        ).scalar_one_or_none()

        if not mo:
            continue

        home = session.get(Team, match.home_team_id)
        away = session.get(Team, match.away_team_id)
        h_name = (home.clean_name or home.name) if home else "?"
        a_name = (away.clean_name or away.name) if away else "?"

        for outcome, prob, edge, odds in [
            ("home", mo.our_home_prob, mo.home_edge_pct, mo.market_home_odds),
            ("draw", mo.our_draw_prob, mo.draw_edge_pct, mo.market_draw_odds),
            ("away", mo.our_away_prob, mo.away_edge_pct, mo.market_away_odds),
        ]:
            if edge is None or odds is None or odds <= 0:
                continue
            if edge < min_edge:
                continue

            confidence = mo.confidence_rating or 5.0
            score = edge * confidence

            available.append(AccumulatorLeg(
                match_id=match.id,
                home_team=h_name,
                away_team=a_name,
                selection=outcome,
                odds=odds,
                our_probability=prob,
                edge_pct=edge,
                confidence=confidence,
                score=score,
            ))

    available.sort(key=lambda x: x.score, reverse=True)
    logger.info("Found %d available outcomes with edge >= %.2f%%.", len(available), min_edge * 100)
    return available


def _calculate_compound_margin(legs: list[AccumulatorLeg]) -> float:
    """
    Calculate the compounding bookmaker margin across all legs.

    Each leg's odds contain ~5-10% margin. Across N legs, the
    effective margin compounds: total_margin = 1 - (prod of (1 - individual_margins)).

    For a single bet with fair odds F and market odds M:
      individual_margin = 1 - M/F = 1 - our_prob * M

    Returns:
        Compound margin as a decimal (e.g. 0.35 = 35% total margin).
    """
    fair_product = 1.0
    market_product = 1.0

    for leg in legs:
        fair_odds = 1 / leg.our_probability if leg.our_probability > 0 else leg.odds
        fair_product *= fair_odds
        market_product *= leg.odds

    if fair_product == 0:
        return 0.0

    return round(1.0 - (market_product / fair_product), 6)


def build_accumulator(
    session: Session,
    target_odds: float = 25.0,
    min_edge: float = 0.02,
    max_legs: int = 8,
    tolerance: float = 0.5,
    top_n: int = 5,
) -> list[AccumulatorCombination]:
    """
    Build optimal accumulator combinations targeting specific odds.

    Algorithm:
    1. Retrieve all outcomes with positive edge >= min_edge.
    2. Score each by edge * confidence.
    3. Search combinations of 2 to max_legs for those hitting target odds
       within tolerance band (target * tolerance to target / tolerance).
    4. For each valid combination, calculate expected value.
    5. Return top_n combinations ranked by expected value.

    Args:
        session: SQLAlchemy session.
        target_odds: Target combined decimal odds (e.g. 25.0 for 25/1).
        min_edge: Minimum per-leg edge (decimal).
        max_legs: Maximum number of legs to consider.
        tolerance: Odds tolerance multiplier (0.5 = allow 50% to 200% of target).
        top_n: Number of top combinations to return.

    Returns:
        List of AccumulatorCombination objects ranked by expected value.
    """
    settings = get_settings()
    stake = settings.default_stake

    available = _get_available_outcomes(session, min_edge)

    if len(available) < 2:
        logger.info("Fewer than 2 available outcomes — cannot build accumulator.")
        return []

    odds_low = target_odds * tolerance
    odds_high = target_odds / tolerance

    best_combos: list[AccumulatorCombination] = []
    max_search_legs = min(max_legs, len(available))

    for num_legs in range(2, max_search_legs + 1):
        # Limit search space — only consider top outcomes by score
        search_pool = available[:min(20, len(available))]

        for combo in combinations(search_pool, num_legs):
            # No duplicate matches
            match_ids = [leg.match_id for leg in combo]
            if len(set(match_ids)) != len(match_ids):
                continue

            combined_odds = 1.0
            combined_prob = 1.0
            for leg in combo:
                combined_odds *= leg.odds
                combined_prob *= leg.our_probability

            # Check target range
            if combined_odds < odds_low or combined_odds > odds_high:
                continue

            potential_return = combined_odds * stake
            expected_value = combined_prob * potential_return - stake
            compound_margin = _calculate_compound_margin(list(combo))

            best_combos.append(AccumulatorCombination(
                legs=list(combo),
                combined_odds=round(combined_odds, 2),
                our_win_probability=round(combined_prob, 8),
                expected_value=round(expected_value, 2),
                potential_return=round(potential_return, 2),
                compound_margin=round(compound_margin, 4),
                positive_ev=expected_value > 0,
            ))

    # Sort by expected value descending
    best_combos.sort(key=lambda x: x.expected_value, reverse=True)

    logger.info(
        "Accumulator search: target=%.1f, found %d valid combinations, returning top %d.",
        target_odds, len(best_combos), min(top_n, len(best_combos)),
    )

    return best_combos[:top_n]


def calculate_parlay_edge(legs: list[dict]) -> dict:
    """
    Calculate the true edge of a parlay after accounting for compounding margin.

    The bookmaker margin compounds with each leg. A parlay that looks like
    it has edge on each individual leg may still be negative EV overall
    due to margin compounding.

    Args:
        legs: List of leg dicts with keys: odds, our_probability, edge_pct.

    Returns:
        Dict with compound analysis.
    """
    settings = get_settings()
    stake = settings.default_stake

    combined_odds = 1.0
    combined_prob = 1.0
    individual_edges = []

    for leg in legs:
        combined_odds *= leg.get("odds", 1)
        combined_prob *= leg.get("our_probability", 0)
        individual_edges.append(leg.get("edge_pct", 0))

    potential_return = combined_odds * stake
    expected_value = combined_prob * potential_return - stake

    # Fair combined odds (what odds we'd need for the parlay to be fair)
    fair_combined_odds = 1 / combined_prob if combined_prob > 0 else 999

    # Compound margin
    compound_margin = 1.0 - (combined_odds / fair_combined_odds) if fair_combined_odds > 0 else 0

    return {
        "combined_odds": round(combined_odds, 2),
        "fair_combined_odds": round(fair_combined_odds, 2),
        "our_win_probability": round(combined_prob, 8),
        "expected_value": round(expected_value, 2),
        "potential_return": round(potential_return, 2),
        "stake": stake,
        "compound_margin": round(compound_margin, 4),
        "compound_margin_pct": round(compound_margin * 100, 2),
        "positive_ev_after_margin": expected_value > 0,
        "avg_individual_edge": round(sum(individual_edges) / len(individual_edges), 4) if individual_edges else 0,
        "num_legs": len(legs),
        "message": (
            "This parlay has POSITIVE expected value after compounding margin."
            if expected_value > 0
            else "WARNING: This parlay has NEGATIVE expected value after compounding margin."
        ),
    }
