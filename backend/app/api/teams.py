"""
Team API endpoints.

Provides team listing, profiles, match history, form data, squad, and head-to-head.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.team import Team
from backend.app.models.match import Match
from backend.app.models.player import Player
from backend.app.models.metrics import TeamMetrics

logger = logging.getLogger("api.teams")
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TeamResponse(BaseModel):
    id: int
    footystats_id: int
    name: str
    clean_name: str | None
    short_name: str | None
    league_id: int
    season: str
    stadium: str | None
    city: str | None

    class Config:
        from_attributes = True


class TeamStatsResponse(BaseModel):
    team_id: int
    team_name: str
    season: str
    metrics: dict | None
    recent_form: str | None
    ppg_season: float | None
    ppg_home: float | None
    ppg_away: float | None


class H2HResponse(BaseModel):
    home_team: str
    away_team: str
    total_meetings: int
    home_wins: int
    draws: int
    away_wins: int
    avg_total_goals: float | None
    btts_rate: float | None
    matches: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    league_id: Optional[int] = Query(None),
    season: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search team name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """List all teams with optional filters."""
    query = select(Team)
    if league_id is not None:
        query = query.where(Team.league_id == league_id)
    if season is not None:
        query = query.where(Team.season == season)
    if search:
        query = query.where(
            or_(
                Team.name.ilike(f"%{search}%"),
                Team.clean_name.ilike(f"%{search}%"),
            )
        )
    query = query.order_by(Team.name).offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get a single team by ID."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/matches")
async def get_team_matches(
    team_id: int,
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Get match history for a team."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    query = select(Match).where(
        or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
    )
    if status:
        query = query.where(Match.status == status)
    query = query.order_by(desc(Match.match_date)).limit(limit)

    result = await session.execute(query)
    matches = result.scalars().all()

    items = []
    for m in matches:
        is_home = m.home_team_id == team_id
        opp_id = m.away_team_id if is_home else m.home_team_id
        opp = await session.get(Team, opp_id)
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals

        if gf is not None and ga is not None:
            res = "W" if gf > ga else ("D" if gf == ga else "L")
        else:
            res = None

        items.append({
            "match_id": m.id,
            "date": m.match_date.isoformat(),
            "opponent": opp.clean_name or opp.name if opp else "?",
            "venue": "H" if is_home else "A",
            "goals_for": gf,
            "goals_against": ga,
            "result": res,
            "xg_for": m.home_xg if is_home else m.away_xg,
            "xg_against": m.away_xg if is_home else m.home_xg,
            "odds_home": m.odds_home,
            "odds_draw": m.odds_draw,
            "odds_away": m.odds_away,
        })

    return {"team_id": team_id, "team_name": team.name, "matches": items}


@router.get("/{team_id}/stats", response_model=TeamStatsResponse)
async def get_team_stats(team_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get all raw + derived metrics for a team."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get latest metrics
    metrics_result = await session.execute(
        select(TeamMetrics)
        .where(TeamMetrics.team_id == team_id)
        .order_by(desc(TeamMetrics.calculated_at))
        .limit(1)
    )
    metrics = metrics_result.scalar_one_or_none()

    metrics_dict = None
    if metrics:
        metrics_dict = {
            "form_last5": metrics.form_last5,
            "form_last10": metrics.form_last10,
            "ppg_last5": metrics.ppg_last5,
            "ppg_last10": metrics.ppg_last10,
            "ppg_season": metrics.ppg_season,
            "ppg_home": metrics.ppg_home,
            "ppg_away": metrics.ppg_away,
            "xg_for_avg": metrics.xg_for_avg,
            "xg_against_avg": metrics.xg_against_avg,
            "xg_overperformance": metrics.xg_overperformance,
            "goals_scored_avg": metrics.goals_scored_avg,
            "goals_conceded_avg": metrics.goals_conceded_avg,
            "clean_sheet_rate": metrics.clean_sheet_rate,
            "btts_rate": metrics.btts_rate,
            "over25_rate": metrics.over25_rate,
            "momentum_score": metrics.momentum_score,
            "momentum_direction": metrics.momentum_direction,
            "fatigue_index": metrics.fatigue_index,
            "conversion_rate": metrics.conversion_rate,
        }

    return TeamStatsResponse(
        team_id=team_id,
        team_name=team.name,
        season=team.season,
        metrics=metrics_dict,
        recent_form=metrics.form_last5 if metrics else None,
        ppg_season=metrics.ppg_season if metrics else None,
        ppg_home=metrics.ppg_home if metrics else None,
        ppg_away=metrics.ppg_away if metrics else None,
    )


@router.get("/{team_id}/form")
async def get_team_form(
    team_id: int,
    last_n: int = Query(20, ge=5, le=50),
    session: AsyncSession = Depends(get_async_session),
):
    """Get form data suitable for charting (last N matches)."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    result = await session.execute(
        select(Match)
        .where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
            Match.status == "complete",
        )
        .order_by(desc(Match.match_date))
        .limit(last_n)
    )
    matches = result.scalars().all()

    form_data = []
    for m in reversed(matches):  # chronological order
        is_home = m.home_team_id == team_id
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals
        xgf = m.home_xg if is_home else m.away_xg
        xga = m.away_xg if is_home else m.home_xg

        if gf is not None and ga is not None:
            res = "W" if gf > ga else ("D" if gf == ga else "L")
            points = 3 if gf > ga else (1 if gf == ga else 0)
        else:
            res = None
            points = None

        form_data.append({
            "date": m.match_date.isoformat(),
            "goals_for": gf,
            "goals_against": ga,
            "xg_for": xgf,
            "xg_against": xga,
            "result": res,
            "points": points,
            "venue": "H" if is_home else "A",
        })

    return {"team_id": team_id, "team_name": team.name, "form": form_data}


@router.get("/{team_id}/players")
async def get_team_players(
    team_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Get the squad list with stats for a team."""
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    result = await session.execute(
        select(Player)
        .where(Player.team_id == team_id)
        .order_by(Player.position, desc(Player.appearances))
    )
    players = result.scalars().all()

    return {
        "team_id": team_id,
        "team_name": team.name,
        "players": [
            {
                "id": p.id,
                "name": p.clean_name or p.name,
                "position": p.position,
                "appearances": p.appearances,
                "goals": p.goals,
                "assists": p.assists,
                "xg": p.xg,
                "xa": p.xa,
                "xg_per90": p.xg_per90,
                "rating": p.rating,
                "yellow_cards": p.yellow_cards,
                "red_cards": p.red_cards,
                "minutes_played": p.minutes_played,
            }
            for p in players
        ],
    }


@router.get("/h2h", response_model=H2HResponse)
async def get_head_to_head(
    home: int = Query(..., description="Home team ID"),
    away: int = Query(..., description="Away team ID"),
    session: AsyncSession = Depends(get_async_session),
):
    """Head-to-head record between two teams."""
    home_team = await session.get(Team, home)
    away_team = await session.get(Team, away)
    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="Team not found")

    # All meetings between these teams (in any order)
    result = await session.execute(
        select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            or_(
                and_(Match.home_team_id == home, Match.away_team_id == away),
                and_(Match.home_team_id == away, Match.away_team_id == home),
            ),
        ).order_by(desc(Match.match_date))
    )
    meetings = result.scalars().all()

    home_wins = 0
    away_wins = 0
    draws = 0
    total_goals = 0
    btts_count = 0
    match_list = []

    for m in meetings:
        hg = m.home_goals or 0
        ag = m.away_goals or 0
        total_goals += hg + ag
        if m.btts:
            btts_count += 1

        # Determine result from perspective of the queried 'home' team
        if m.home_team_id == home:
            if hg > ag:
                home_wins += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1
        else:
            if ag > hg:
                home_wins += 1
            elif ag == hg:
                draws += 1
            else:
                away_wins += 1

        match_list.append({
            "date": m.match_date.isoformat(),
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "stadium": m.stadium,
        })

    n = len(meetings)

    return H2HResponse(
        home_team=home_team.name,
        away_team=away_team.name,
        total_meetings=n,
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
        avg_total_goals=round(total_goals / n, 2) if n else None,
        btts_rate=round(btts_count / n * 100, 1) if n else None,
        matches=match_list[:10],
    )
