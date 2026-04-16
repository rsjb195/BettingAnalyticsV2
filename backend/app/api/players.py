"""
Player API endpoints.

Provides player listing and individual player profiles with full statistics.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.player import Player
from backend.app.models.team import Team

logger = logging.getLogger("api.players")
router = APIRouter()


class PlayerResponse(BaseModel):
    id: int
    footystats_id: int
    name: str
    clean_name: str | None
    team_id: int
    team_name: str | None = None
    league_id: int
    season: str
    position: str | None
    age: int | None
    nationality: str | None
    appearances: int | None
    minutes_played: int | None
    goals: int | None
    assists: int | None
    yellow_cards: int | None
    red_cards: int | None
    xg: float | None
    xg_per90: float | None
    xa: float | None
    xa_per90: float | None
    shots: int | None
    shots_on_target: int | None
    shot_conversion_rate: float | None
    rating: float | None
    xg_per90_percentile: float | None
    rating_percentile: float | None

    class Config:
        from_attributes = True


@router.get("")
async def list_players(
    league_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    position: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("rating", description="Sort field"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """Paginated player list with filters."""
    query = select(Player)

    if league_id is not None:
        query = query.where(Player.league_id == league_id)
    if team_id is not None:
        query = query.where(Player.team_id == team_id)
    if position:
        query = query.where(Player.position.ilike(f"%{position}%"))
    if search:
        query = query.where(
            or_(Player.name.ilike(f"%{search}%"), Player.clean_name.ilike(f"%{search}%"))
        )

    # Sorting
    sort_map = {
        "rating": Player.rating,
        "goals": Player.goals,
        "assists": Player.assists,
        "xg": Player.xg,
        "xg_per90": Player.xg_per90,
        "appearances": Player.appearances,
        "minutes": Player.minutes_played,
    }
    sort_col = sort_map.get(sort_by, Player.rating)
    query = query.order_by(desc(sort_col).nulls_last())

    # Pagination
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar()

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    players = result.scalars().all()

    items = []
    for p in players:
        team = await session.get(Team, p.team_id)
        items.append({
            "id": p.id,
            "name": p.clean_name or p.name,
            "team_id": p.team_id,
            "team_name": (team.clean_name or team.name) if team else None,
            "position": p.position,
            "age": p.age,
            "appearances": p.appearances,
            "goals": p.goals,
            "assists": p.assists,
            "xg": p.xg,
            "xg_per90": p.xg_per90,
            "xa": p.xa,
            "rating": p.rating,
            "minutes_played": p.minutes_played,
        })

    return {"total": total, "page": page, "per_page": per_page, "players": items}


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(player_id: int, session: AsyncSession = Depends(get_async_session)):
    """Full player profile with all statistics."""
    player = await session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    team = await session.get(Team, player.team_id)
    return PlayerResponse(
        id=player.id,
        footystats_id=player.footystats_id,
        name=player.name,
        clean_name=player.clean_name,
        team_id=player.team_id,
        team_name=(team.clean_name or team.name) if team else None,
        league_id=player.league_id,
        season=player.season,
        position=player.position,
        age=player.age,
        nationality=player.nationality,
        appearances=player.appearances,
        minutes_played=player.minutes_played,
        goals=player.goals,
        assists=player.assists,
        yellow_cards=player.yellow_cards,
        red_cards=player.red_cards,
        xg=player.xg,
        xg_per90=player.xg_per90,
        xa=player.xa,
        xa_per90=player.xa_per90,
        shots=player.shots,
        shots_on_target=player.shots_on_target,
        shot_conversion_rate=player.shot_conversion_rate,
        rating=player.rating,
        xg_per90_percentile=player.xg_per90_percentile,
        rating_percentile=player.rating_percentile,
    )
