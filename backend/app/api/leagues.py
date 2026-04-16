"""
League API endpoints.

Provides league listing, standings, match history, and league-level statistics.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.team import Team

logger = logging.getLogger("api.leagues")
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class LeagueResponse(BaseModel):
    id: int
    footystats_id: int
    name: str
    country: str
    season: str
    season_year: int
    tier: int
    total_matches: int | None
    matches_played: int | None

    class Config:
        from_attributes = True


class LeagueTableEntry(BaseModel):
    team_id: int
    team_name: str
    clean_name: str | None
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: str | None


class LeagueStatsResponse(BaseModel):
    league_id: int
    league_name: str
    season: str
    total_matches: int
    completed_matches: int
    avg_goals_per_match: float | None
    btts_rate: float | None
    over25_rate: float | None
    home_win_rate: float | None
    draw_rate: float | None
    away_win_rate: float | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[LeagueResponse])
async def list_leagues(
    tier: Optional[int] = Query(None, ge=1, le=4, description="Filter by tier (1-4)"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    session: AsyncSession = Depends(get_async_session),
):
    """List all leagues with optional tier and season filters."""
    query = select(League).order_by(League.tier, desc(League.season_year))
    if tier is not None:
        query = query.where(League.tier == tier)
    if season_year is not None:
        query = query.where(League.season_year == season_year)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{league_id}", response_model=LeagueResponse)
async def get_league(league_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get a single league by ID."""
    league = await session.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.get("/{league_id}/table", response_model=list[LeagueTableEntry])
async def get_league_table(league_id: int, session: AsyncSession = Depends(get_async_session)):
    """
    Calculate and return the current league table / standings.

    Built from match results — not cached standings.
    """
    league = await session.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Get all teams in this league
    teams_result = await session.execute(
        select(Team).where(Team.league_id == league_id)
    )
    teams = {t.id: t for t in teams_result.scalars().all()}

    # Get all completed matches
    matches_result = await session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "complete",
            Match.home_goals.isnot(None),
        )
    )
    matches = matches_result.scalars().all()

    # Build table
    table: dict[int, dict] = {}
    for team_id, team in teams.items():
        table[team_id] = {
            "team_id": team_id,
            "team_name": team.name,
            "clean_name": team.clean_name,
            "played": 0, "wins": 0, "draws": 0, "losses": 0,
            "goals_for": 0, "goals_against": 0,
            "goal_difference": 0, "points": 0,
            "form": "",
            "_recent": [],
        }

    for m in matches:
        for team_id, is_home in [(m.home_team_id, True), (m.away_team_id, False)]:
            if team_id not in table:
                continue
            entry = table[team_id]
            entry["played"] += 1

            gf = m.home_goals if is_home else m.away_goals
            ga = m.away_goals if is_home else m.home_goals
            entry["goals_for"] += gf
            entry["goals_against"] += ga

            if gf > ga:
                entry["wins"] += 1
                entry["points"] += 3
                entry["_recent"].append(("W", m.match_date))
            elif gf == ga:
                entry["draws"] += 1
                entry["points"] += 1
                entry["_recent"].append(("D", m.match_date))
            else:
                entry["losses"] += 1
                entry["_recent"].append(("L", m.match_date))

    # Compute form (last 5) and goal difference
    for entry in table.values():
        entry["goal_difference"] = entry["goals_for"] - entry["goals_against"]
        recent = sorted(entry["_recent"], key=lambda x: x[1], reverse=True)[:5]
        entry["form"] = "".join(r[0] for r in recent)
        del entry["_recent"]

    # Sort by points, then GD, then GF
    sorted_table = sorted(
        table.values(),
        key=lambda x: (x["points"], x["goal_difference"], x["goals_for"]),
        reverse=True,
    )

    return sorted_table


@router.get("/{league_id}/matches")
async def get_league_matches(
    league_id: int,
    status: Optional[str] = Query(None, description="Filter by status: complete/upcoming"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """Paginated match list for a league."""
    league = await session.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    query = select(Match).where(Match.league_id == league_id)
    if status:
        query = query.where(Match.status == status)

    # Count
    count_result = await session.execute(
        select(func.count()).select_from(Match).where(Match.league_id == league_id)
    )
    total = count_result.scalar()

    # Fetch page
    query = query.order_by(desc(Match.match_date)).offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    matches = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "matches": [
            {
                "id": m.id,
                "footystats_id": m.footystats_id,
                "home_team_id": m.home_team_id,
                "away_team_id": m.away_team_id,
                "match_date": m.match_date.isoformat(),
                "status": m.status,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "odds_home": m.odds_home,
                "odds_draw": m.odds_draw,
                "odds_away": m.odds_away,
            }
            for m in matches
        ],
    }


@router.get("/{league_id}/stats", response_model=LeagueStatsResponse)
async def get_league_stats(league_id: int, session: AsyncSession = Depends(get_async_session)):
    """League-level aggregate statistics."""
    league = await session.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    completed = await session.execute(
        select(Match).where(
            Match.league_id == league_id,
            Match.status == "complete",
            Match.home_goals.isnot(None),
        )
    )
    matches = completed.scalars().all()
    n = len(matches)

    if n == 0:
        return LeagueStatsResponse(
            league_id=league_id, league_name=league.name, season=league.season,
            total_matches=league.total_matches or 0, completed_matches=0,
            avg_goals_per_match=None, btts_rate=None, over25_rate=None,
            home_win_rate=None, draw_rate=None, away_win_rate=None,
        )

    total_goals = sum((m.home_goals or 0) + (m.away_goals or 0) for m in matches)
    btts_count = sum(1 for m in matches if m.btts)
    over25_count = sum(1 for m in matches if m.over_25)
    home_wins = sum(1 for m in matches if (m.home_goals or 0) > (m.away_goals or 0))
    draws = sum(1 for m in matches if (m.home_goals or 0) == (m.away_goals or 0))
    away_wins = n - home_wins - draws

    return LeagueStatsResponse(
        league_id=league_id,
        league_name=league.name,
        season=league.season,
        total_matches=league.total_matches or n,
        completed_matches=n,
        avg_goals_per_match=round(total_goals / n, 2),
        btts_rate=round(btts_count / n * 100, 1),
        over25_rate=round(over25_count / n * 100, 1),
        home_win_rate=round(home_wins / n * 100, 1),
        draw_rate=round(draws / n * 100, 1),
        away_win_rate=round(away_wins / n * 100, 1),
    )
