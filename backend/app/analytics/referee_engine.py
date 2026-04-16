"""
Referee Impact Model.

Calculates detailed referee behavioural profiles and match-level probability
adjustments based on a referee's disciplinary tendencies, home/away bias,
and game flow impact.

This is a genuine edge source — bookmakers underweight referee assignments
in their models. Our referee profiles use rolling windows (last 20 matches)
which are more predictive than career averages.
"""

import logging
import statistics
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from backend.app.models.match import Match
from backend.app.models.metrics import RefereeProfile
from backend.app.models.referee import Referee, RefereeMatchLog

logger = logging.getLogger("analytics.referee")


class RefereeAdjustment(NamedTuple):
    """Probability adjustments and narrative for a referee assignment."""
    home_win_adj: float
    draw_adj: float
    away_win_adj: float
    over25_adj: float
    card_alert: bool
    home_bias_alert: bool
    narrative: str


def calculate_referee_profile(referee_id: int, session: Session) -> RefereeProfile | None:
    """
    Calculate a complete referee behavioural profile from their match log.

    Uses all available match data for career metrics, and the most recent
    20 matches for rolling (predictive) metrics. Compares referee's rates
    to league averages where possible.

    Args:
        referee_id: Database referee ID.
        session: SQLAlchemy session.

    Returns:
        RefereeProfile object (not yet committed to DB), or None if
        insufficient data (< 5 matches).
    """
    logs = session.execute(
        select(RefereeMatchLog)
        .where(RefereeMatchLog.referee_id == referee_id)
        .order_by(desc(RefereeMatchLog.match_date))
    ).scalars().all()

    if len(logs) < 5:
        logger.debug("Referee %d has only %d matches — insufficient for profiling.", referee_id, len(logs))
        return None

    # --- Career metrics ---
    total_matches = len(logs)
    all_cards = [log.total_cards for log in logs]
    all_yellows = [log.home_yellows + log.away_yellows for log in logs]
    all_fouls = [log.total_fouls for log in logs if log.total_fouls is not None]

    cards_career = sum(all_cards) / total_matches
    yellows_career = sum(all_yellows) / total_matches

    # --- Rolling last 20 metrics (more predictive) ---
    recent = logs[:20]
    recent_cards = [log.total_cards for log in recent]
    recent_yellows = [log.home_yellows + log.away_yellows for log in recent]

    cards_l20 = sum(recent_cards) / len(recent_cards)
    yellows_l20 = sum(recent_yellows) / len(recent_yellows)

    # --- Home bias score ---
    total_home_yellows = sum(log.home_yellows for log in logs)
    total_away_yellows = sum(log.away_yellows for log in logs)

    if total_away_yellows > 0:
        home_bias = total_home_yellows / total_away_yellows
    else:
        home_bias = 1.0

    if home_bias > 1.15:
        bias_direction = "home_heavy"
    elif home_bias < 0.85:
        bias_direction = "away_heavy"
    else:
        bias_direction = "neutral"

    # --- Game flow impact ---
    match_ids = [log.match_id for log in logs]
    matches = session.execute(
        select(Match).where(Match.id.in_(match_ids), Match.home_goals.isnot(None))
    ).scalars().all()

    total_goals_list = []
    over25_count = 0
    for m in matches:
        tg = (m.home_goals or 0) + (m.away_goals or 0)
        total_goals_list.append(tg)
        if tg > 2:
            over25_count += 1

    goals_per_match = sum(total_goals_list) / len(total_goals_list) if total_goals_list else None
    over25_rate = over25_count / len(total_goals_list) if total_goals_list else None

    # --- Penalty profile ---
    total_pens = sum(log.penalties_awarded for log in logs)
    pens_per_match = total_pens / total_matches

    # --- Card volatility (standard deviation) ---
    card_volatility = statistics.stdev(all_cards) if len(all_cards) > 1 else 0.0

    # --- Build profile ---
    profile = RefereeProfile(
        referee_id=referee_id,
        calculated_at=datetime.utcnow(),
        cards_per_match_career=round(cards_career, 3),
        cards_per_match_l20=round(cards_l20, 3),
        yellows_per_match_career=round(yellows_career, 3),
        yellows_per_match_l20=round(yellows_l20, 3),
        home_bias_score=round(home_bias, 4),
        home_bias_direction=bias_direction,
        goals_per_match_when_refereeing=round(goals_per_match, 3) if goals_per_match else None,
        over25_rate_when_refereeing=round(over25_rate, 4) if over25_rate else None,
        penalties_per_match=round(pens_per_match, 4),
        card_volatility_score=round(card_volatility, 3),
    )

    # Also update aggregate columns on the referee record
    ref = session.get(Referee, referee_id)
    if ref:
        ref.total_matches = total_matches
        ref.total_yellows = total_home_yellows + total_away_yellows
        ref.total_reds = sum(log.home_reds + log.away_reds for log in logs)
        ref.avg_yellows_per_match = round(yellows_career, 3)
        ref.avg_reds_per_match = round(ref.total_reds / total_matches, 3)
        ref.avg_cards_per_match = round(cards_career, 3)
        ref.avg_fouls_per_match = round(sum(all_fouls) / len(all_fouls), 3) if all_fouls else None
        ref.home_yellow_rate = round(total_home_yellows / total_matches, 3) if total_matches > 0 else None
        ref.away_yellow_rate = round(total_away_yellows / total_matches, 3) if total_matches > 0 else None
        ref.home_bias_score = round(home_bias, 4)
        ref.penalties_per_match = round(pens_per_match, 4)

    logger.info(
        "Referee %d profile: cards=%.2f (L20: %.2f), bias=%.3f (%s), volatility=%.2f",
        referee_id, cards_career, cards_l20, home_bias, bias_direction, card_volatility,
    )

    return profile


def calculate_referee_match_adjustment(
    referee_id: int,
    home_team_id: int,
    away_team_id: int,
    base_home_prob: float,
    base_draw_prob: float,
    base_away_prob: float,
    session: Session,
) -> RefereeAdjustment:
    """
    Calculate probability adjustments based on referee assignment.

    Adjusts base match probabilities based on:
    1. Home bias — strong bias shifts home/away win probabilities.
    2. Card rate — high card rate is context for player suspension risk.
    3. Over 2.5 rate — deviation from league average affects totals markets.

    Args:
        referee_id: Database referee ID.
        home_team_id: Database home team ID.
        away_team_id: Database away team ID.
        base_home_prob: Pre-adjustment home win probability.
        base_draw_prob: Pre-adjustment draw probability.
        base_away_prob: Pre-adjustment away win probability.
        session: SQLAlchemy session.

    Returns:
        RefereeAdjustment with adjusted probabilities and narrative.
    """
    profile_result = session.execute(
        select(RefereeProfile)
        .where(RefereeProfile.referee_id == referee_id)
        .order_by(desc(RefereeProfile.calculated_at))
        .limit(1)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        return RefereeAdjustment(
            home_win_adj=0.0, draw_adj=0.0, away_win_adj=0.0,
            over25_adj=0.0, card_alert=False, home_bias_alert=False,
            narrative="No referee profile available — using base probabilities.",
        )

    home_adj = 0.0
    draw_adj = 0.0
    away_adj = 0.0
    over25_adj = 0.0
    narratives = []
    card_alert = False
    home_bias_alert = False

    # --- Home bias adjustment ---
    if profile.home_bias_score is not None:
        if profile.home_bias_score > 1.15:
            # Referee tends to card home teams more — slight away advantage
            home_adj = -0.015
            away_adj = +0.010
            draw_adj = +0.005
            home_bias_alert = True
            narratives.append(
                f"Referee has strong home-card bias ({profile.home_bias_score:.3f}). "
                f"Home teams receive more cards, potentially disrupting home advantage."
            )
        elif profile.home_bias_score < 0.85:
            # Referee cards away teams more — slight home advantage
            home_adj = +0.010
            away_adj = -0.015
            draw_adj = +0.005
            home_bias_alert = True
            narratives.append(
                f"Referee has strong away-card bias ({profile.home_bias_score:.3f}). "
                f"Away teams receive more cards, strengthening home advantage."
            )

    # --- High card rate context ---
    if profile.cards_per_match_l20 is not None and profile.cards_per_match_l20 > 5.0:
        card_alert = True
        narratives.append(
            f"High card rate ({profile.cards_per_match_l20:.1f}/match L20). "
            f"Consider player suspension risk for both teams."
        )

    # --- Over 2.5 rate deviation ---
    league_avg_over25 = 0.50  # Use this as baseline; could be parameterised per league
    if profile.over25_rate_when_refereeing is not None:
        deviation = profile.over25_rate_when_refereeing - league_avg_over25
        if abs(deviation) > 0.08:
            over25_adj = deviation * 0.3  # Dampen the effect
            direction = "above" if deviation > 0 else "below"
            narratives.append(
                f"Referee's matches go O2.5 at {profile.over25_rate_when_refereeing:.1%} "
                f"({direction} league avg of {league_avg_over25:.0%}). "
                f"{'Goals may be encouraged' if deviation > 0 else 'This referee may suppress goals'}."
            )

    # --- Team-specific history ---
    team_history = get_referee_team_history(referee_id, home_team_id, session)
    if team_history and team_history["matches"] >= 3:
        narratives.append(
            f"Home team has played under this referee {team_history['matches']} times "
            f"(avg cards received: {team_history['avg_cards_received']:.1f})."
        )

    narrative = " | ".join(narratives) if narratives else "Referee profile is neutral — no significant adjustments."

    return RefereeAdjustment(
        home_win_adj=round(home_adj, 4),
        draw_adj=round(draw_adj, 4),
        away_win_adj=round(away_adj, 4),
        over25_adj=round(over25_adj, 4),
        card_alert=card_alert,
        home_bias_alert=home_bias_alert,
        narrative=narrative,
    )


def get_referee_team_history(referee_id: int, team_id: int, session: Session) -> dict | None:
    """
    Retrieve a referee's history with a specific team.

    Args:
        referee_id: Database referee ID.
        team_id: Database team ID.
        session: SQLAlchemy session.

    Returns:
        Dict with match count, results, and card data, or None.
    """
    # Find matches where this referee officiated this team
    logs = session.execute(
        select(RefereeMatchLog)
        .join(Match, RefereeMatchLog.match_id == Match.id)
        .where(
            RefereeMatchLog.referee_id == referee_id,
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
        )
        .order_by(desc(RefereeMatchLog.match_date))
    ).scalars().all()

    if not logs:
        return None

    total_cards_received = 0
    results = []

    for log in logs:
        match = session.get(Match, log.match_id)
        if not match:
            continue

        is_home = match.home_team_id == team_id
        cards = log.home_yellows + log.home_reds if is_home else log.away_yellows + log.away_reds
        total_cards_received += cards

        if match.home_goals is not None and match.away_goals is not None:
            gf = match.home_goals if is_home else match.away_goals
            ga = match.away_goals if is_home else match.home_goals
            if gf > ga:
                results.append("W")
            elif gf == ga:
                results.append("D")
            else:
                results.append("L")

    return {
        "matches": len(logs),
        "avg_cards_received": total_cards_received / len(logs) if logs else 0,
        "results": results,
        "wins": results.count("W"),
        "draws": results.count("D"),
        "losses": results.count("L"),
    }


def flag_significant_referees(session: Session) -> list[dict]:
    """
    Flag upcoming matches where the assigned referee has notable characteristics.

    Flags if:
    - home_bias_score > 1.2 or < 0.8
    - avg_cards_per_match > league_avg + 1 standard deviation
    - over25_rate deviates > 10% from league average

    Args:
        session: SQLAlchemy session.

    Returns:
        List of dicts with match info and referee flag explanations.
    """
    from datetime import date

    upcoming = session.execute(
        select(Match).where(
            Match.status == "upcoming",
            Match.referee_id.isnot(None),
            Match.match_date >= date.today(),
        )
    ).scalars().all()

    # Get league average card rate for comparison
    all_refs = session.execute(
        select(Referee).where(Referee.total_matches >= 10)
    ).scalars().all()

    if all_refs:
        avg_cards_rates = [r.avg_cards_per_match for r in all_refs if r.avg_cards_per_match]
        league_avg_cards = sum(avg_cards_rates) / len(avg_cards_rates) if avg_cards_rates else 4.0
        card_std = statistics.stdev(avg_cards_rates) if len(avg_cards_rates) > 1 else 1.0
    else:
        league_avg_cards = 4.0
        card_std = 1.0

    flags = []

    for match in upcoming:
        ref = session.get(Referee, match.referee_id)
        if not ref:
            continue

        reasons = []

        # Home bias
        if ref.home_bias_score is not None:
            if ref.home_bias_score > 1.2:
                reasons.append(f"Strong home-card bias ({ref.home_bias_score:.3f})")
            elif ref.home_bias_score < 0.8:
                reasons.append(f"Strong away-card bias ({ref.home_bias_score:.3f})")

        # High card rate
        if ref.avg_cards_per_match is not None:
            if ref.avg_cards_per_match > league_avg_cards + card_std:
                reasons.append(
                    f"High card rate ({ref.avg_cards_per_match:.1f} vs league avg {league_avg_cards:.1f})"
                )

        if reasons:
            from backend.app.models.team import Team
            home = session.get(Team, match.home_team_id)
            away = session.get(Team, match.away_team_id)

            flags.append({
                "match_id": match.id,
                "match_date": match.match_date.isoformat(),
                "home_team": (home.clean_name or home.name) if home else "?",
                "away_team": (away.clean_name or away.name) if away else "?",
                "referee_name": ref.name,
                "referee_id": ref.id,
                "flags": reasons,
            })

    logger.info("Flagged %d upcoming matches with significant referee profiles.", len(flags))
    return flags
