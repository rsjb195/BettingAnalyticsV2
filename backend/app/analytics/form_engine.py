"""
Form engine — calculates rolling form metrics and trend analysis.

Used by the team metrics calculator and the UI form charts.
Provides PPG trends, result sequences, and opposition-quality-adjusted form.
"""

import logging
from datetime import date

from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session

from backend.app.models.match import Match

logger = logging.getLogger("analytics.form")


def get_rolling_ppg(team_id: int, session: Session, window: int = 5, max_matches: int = 38) -> list[dict]:
    """
    Calculate rolling points-per-game over a sliding window.

    Args:
        team_id: Database team ID.
        session: SQLAlchemy session.
        window: Rolling window size.
        max_matches: Maximum number of matches to include.

    Returns:
        List of dicts with date, ppg, and cumulative points.
    """
    matches = session.execute(
        select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        ).order_by(Match.match_date)
    ).scalars().all()

    matches = matches[-max_matches:]

    results = []
    points_history = []

    for m in matches:
        is_home = m.home_team_id == team_id
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals
        pts = 3 if gf > ga else (1 if gf == ga else 0)
        points_history.append(pts)

        # Rolling average
        window_slice = points_history[-window:]
        rolling_ppg = sum(window_slice) / len(window_slice)

        results.append({
            "date": m.match_date.isoformat(),
            "points": pts,
            "rolling_ppg": round(rolling_ppg, 3),
            "cumulative_ppg": round(sum(points_history) / len(points_history), 3),
        })

    return results


def get_form_string(team_id: int, session: Session, last_n: int = 10) -> str:
    """
    Get the form string (e.g. "WWDLW") for a team's last N matches.

    Args:
        team_id: Database team ID.
        session: SQLAlchemy session.
        last_n: Number of recent matches.

    Returns:
        Form string, most recent first.
    """
    matches = session.execute(
        select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        ).order_by(desc(Match.match_date)).limit(last_n)
    ).scalars().all()

    form = []
    for m in matches:
        is_home = m.home_team_id == team_id
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals
        if gf > ga:
            form.append("W")
        elif gf == ga:
            form.append("D")
        else:
            form.append("L")

    return "".join(form)


def get_scoring_patterns(team_id: int, session: Session) -> dict:
    """
    Analyse scoring and conceding patterns.

    Returns data on first goals, set pieces context, and game state impact.
    """
    matches = session.execute(
        select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        ).order_by(desc(Match.match_date))
    ).scalars().all()

    if not matches:
        return {}

    n = len(matches)
    scored_first = 0
    conceded_first = 0
    win_after_scoring_first = 0
    lose_after_conceding_first = 0

    for m in matches:
        is_home = m.home_team_id == team_id
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals

        # Use HT score as proxy for "first goal" if available
        ht_gf = (m.home_goals_ht if is_home else m.away_goals_ht) or 0
        ht_ga = (m.away_goals_ht if is_home else m.home_goals_ht) or 0

        if ht_gf > 0 and ht_ga == 0:
            scored_first += 1
            if gf > ga:
                win_after_scoring_first += 1
        elif ht_ga > 0 and ht_gf == 0:
            conceded_first += 1
            if gf < ga:
                lose_after_conceding_first += 1

    return {
        "total_matches": n,
        "scored_first_rate": round(scored_first / n, 3) if n else 0,
        "conceded_first_rate": round(conceded_first / n, 3) if n else 0,
        "win_when_scoring_first": round(win_after_scoring_first / scored_first, 3) if scored_first else None,
        "lose_when_conceding_first": round(lose_after_conceding_first / conceded_first, 3) if conceded_first else None,
    }
