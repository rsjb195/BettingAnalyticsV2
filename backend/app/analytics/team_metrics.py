"""
Team metrics calculator.

Computes all derived team performance metrics from raw match data.
Each calculation produces a TeamMetrics snapshot for a team at a
specific point in time (gameweek).
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session

from backend.app.models.match import Match
from backend.app.models.metrics import TeamMetrics
from backend.app.models.team import Team

logger = logging.getLogger("analytics.team_metrics")


def calculate_team_metrics(team_id: int, league_id: int, season: str, session: Session) -> TeamMetrics | None:
    """
    Calculate all performance metrics for a team from their match history.

    Args:
        team_id: Database team ID.
        league_id: Database league ID.
        season: Season string (e.g. "2023/2024").
        session: SQLAlchemy session.

    Returns:
        TeamMetrics object, or None if insufficient data.
    """
    matches = session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "complete",
            Match.home_goals.isnot(None),
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        ).order_by(desc(Match.match_date))
    ).scalars().all()

    if len(matches) < 3:
        return None

    # Process matches into a consistent format
    results = []
    for m in matches:
        is_home = m.home_team_id == team_id
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals
        xgf = m.home_xg if is_home else m.away_xg
        xga = m.away_xg if is_home else m.home_xg
        sf = m.home_shots if is_home else m.away_shots
        sa = m.away_shots if is_home else m.home_shots

        if gf > ga:
            res, pts = "W", 3
        elif gf == ga:
            res, pts = "D", 1
        else:
            res, pts = "L", 0

        results.append({
            "date": m.match_date, "is_home": is_home,
            "gf": gf, "ga": ga, "xgf": xgf, "xga": xga,
            "sf": sf, "sa": sa, "result": res, "points": pts,
            "btts": m.btts, "over25": m.over_25,
        })

    n = len(results)
    last5 = results[:5]
    last10 = results[:10]

    # Form strings
    form5 = "".join(r["result"] for r in last5)
    form10 = "".join(r["result"] for r in last10)

    # PPG
    ppg5 = sum(r["points"] for r in last5) / len(last5) if last5 else None
    ppg10 = sum(r["points"] for r in last10) / len(last10) if last10 else None
    ppg_season = sum(r["points"] for r in results) / n
    home_results = [r for r in results if r["is_home"]]
    away_results = [r for r in results if not r["is_home"]]
    ppg_home = sum(r["points"] for r in home_results) / len(home_results) if home_results else None
    ppg_away = sum(r["points"] for r in away_results) / len(away_results) if away_results else None

    # xG metrics
    xgs = [r for r in results if r["xgf"] is not None]
    xg_for_avg = sum(r["xgf"] for r in xgs) / len(xgs) if xgs else None
    xg_against_avg = sum(r["xga"] for r in xgs) / len(xgs) if xgs else None
    home_xgs = [r for r in xgs if r["is_home"]]
    away_xgs = [r for r in xgs if not r["is_home"]]
    xg_for_home = sum(r["xgf"] for r in home_xgs) / len(home_xgs) if home_xgs else None
    xg_against_home = sum(r["xga"] for r in home_xgs) / len(home_xgs) if home_xgs else None
    xg_for_away = sum(r["xgf"] for r in away_xgs) / len(away_xgs) if away_xgs else None
    xg_against_away = sum(r["xga"] for r in away_xgs) / len(away_xgs) if away_xgs else None

    total_goals = sum(r["gf"] for r in results)
    total_xg = sum(r["xgf"] for r in xgs) if xgs else 0
    xg_overperf = (total_goals - total_xg) / n if xgs else None

    # Attacking
    goals_scored_avg = sum(r["gf"] for r in results) / n
    goals_conceded_avg = sum(r["ga"] for r in results) / n
    shots_with = [r for r in results if r["sf"] is not None]
    shots_for_avg = sum(r["sf"] for r in shots_with) / len(shots_with) if shots_with else None
    shots_against_avg = sum(r["sa"] for r in shots_with) / len(shots_with) if shots_with else None
    total_shots = sum(r["sf"] for r in shots_with) if shots_with else 0
    conversion = total_goals / total_shots if total_shots > 0 else None

    # Defensive
    clean_sheets = sum(1 for r in results if r["ga"] == 0)
    cs_rate = clean_sheets / n
    cs_home = sum(1 for r in home_results if r["ga"] == 0) / len(home_results) if home_results else None
    cs_away = sum(1 for r in away_results if r["ga"] == 0) / len(away_results) if away_results else None
    btts_rate = sum(1 for r in results if r["btts"]) / n
    over25_rate = sum(1 for r in results if r["over25"]) / n

    # Momentum score (composite)
    recent_ppg = ppg5 or 0
    max_ppg = 3.0
    form_score = (recent_ppg / max_ppg) * 40

    xg_trend = 0
    if len(xgs) >= 5:
        recent_xg_diff = sum((xgs[i]["xgf"] or 0) - (xgs[i]["xga"] or 0) for i in range(min(5, len(xgs)))) / min(5, len(xgs))
        xg_trend = min(max(recent_xg_diff * 10, -20), 20) + 20

    results_momentum = sum(1 for r in last5 if r["result"] == "W") * 8
    momentum_score = form_score + xg_trend + results_momentum
    momentum_score = max(0, min(100, momentum_score))

    if len(last5) >= 2:
        recent_pts = sum(r["points"] for r in last5[:3])
        older_pts = sum(r["points"] for r in last5[3:]) if len(last5) > 3 else 0
        if recent_pts > older_pts + 2:
            momentum_dir = "rising"
        elif recent_pts < older_pts - 2:
            momentum_dir = "falling"
        else:
            momentum_dir = "stable"
    else:
        momentum_dir = "stable"

    # Fatigue
    today = date.today()
    days_since = (today - results[0]["date"]).days if results else None
    matches_14d = sum(1 for r in results if (today - r["date"]).days <= 14)
    fatigue = min(1.0, matches_14d / 5.0) if matches_14d > 0 else 0.0

    # Determine gameweek
    gameweek = n

    metrics = TeamMetrics(
        team_id=team_id,
        league_id=league_id,
        season=season,
        calculated_at=datetime.utcnow(),
        gameweek=gameweek,
        form_last5=form5,
        form_last10=form10,
        ppg_last5=round(ppg5, 3) if ppg5 is not None else None,
        ppg_last10=round(ppg10, 3) if ppg10 is not None else None,
        ppg_season=round(ppg_season, 3),
        ppg_home=round(ppg_home, 3) if ppg_home is not None else None,
        ppg_away=round(ppg_away, 3) if ppg_away is not None else None,
        xg_for_avg=round(xg_for_avg, 3) if xg_for_avg is not None else None,
        xg_against_avg=round(xg_against_avg, 3) if xg_against_avg is not None else None,
        xg_for_home=round(xg_for_home, 3) if xg_for_home is not None else None,
        xg_against_home=round(xg_against_home, 3) if xg_against_home is not None else None,
        xg_for_away=round(xg_for_away, 3) if xg_for_away is not None else None,
        xg_against_away=round(xg_against_away, 3) if xg_against_away is not None else None,
        xg_overperformance=round(xg_overperf, 3) if xg_overperf is not None else None,
        goals_scored_avg=round(goals_scored_avg, 3),
        goals_conceded_avg=round(goals_conceded_avg, 3),
        shots_for_avg=round(shots_for_avg, 3) if shots_for_avg is not None else None,
        shots_against_avg=round(shots_against_avg, 3) if shots_against_avg is not None else None,
        conversion_rate=round(conversion, 4) if conversion is not None else None,
        clean_sheet_rate=round(cs_rate, 3),
        clean_sheet_home=round(cs_home, 3) if cs_home is not None else None,
        clean_sheet_away=round(cs_away, 3) if cs_away is not None else None,
        btts_rate=round(btts_rate, 3),
        over25_rate=round(over25_rate, 3),
        momentum_score=round(momentum_score, 1),
        momentum_direction=momentum_dir,
        days_since_last_match=days_since,
        matches_last_14_days=matches_14d,
        fatigue_index=round(fatigue, 3),
    )

    session.add(metrics)
    logger.debug("Calculated metrics for team %d: PPG=%.2f, momentum=%.1f", team_id, ppg_season, momentum_score)
    return metrics


def recalculate_all_teams(league_id: int, session: Session) -> int:
    """
    Recalculate metrics for all teams in a league.

    Args:
        league_id: Database league ID.
        session: SQLAlchemy session.

    Returns:
        Number of teams updated.
    """
    from backend.app.models.league import League

    league = session.get(League, league_id)
    if not league:
        return 0

    teams = session.execute(
        select(Team).where(Team.league_id == league_id)
    ).scalars().all()

    count = 0
    for team in teams:
        metrics = calculate_team_metrics(team.id, league_id, league.season, session)
        if metrics:
            count += 1

    session.commit()
    logger.info("Recalculated metrics for %d teams in league %d.", count, league_id)
    return count
