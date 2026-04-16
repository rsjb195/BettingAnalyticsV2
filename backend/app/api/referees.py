"""
Referee API endpoints.

Provides referee listing, full profiles, match logs, and impact model data.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.referee import Referee, RefereeMatchLog
from backend.app.models.metrics import RefereeProfile
from backend.app.models.match import Match
from backend.app.models.team import Team

logger = logging.getLogger("api.referees")
router = APIRouter()


class RefereeResponse(BaseModel):
    id: int
    footystats_id: int | None
    name: str
    clean_name: str | None
    total_matches: int
    total_yellows: int
    total_reds: int
    avg_yellows_per_match: float | None
    avg_reds_per_match: float | None
    avg_cards_per_match: float | None
    avg_fouls_per_match: float | None
    home_bias_score: float | None
    penalties_per_match: float | None
    primary_source: str

    class Config:
        from_attributes = True


class RefereeProfileResponse(BaseModel):
    referee_id: int
    cards_per_match_career: float | None
    cards_per_match_l20: float | None
    yellows_per_match_career: float | None
    yellows_per_match_l20: float | None
    home_bias_score: float | None
    home_bias_direction: str | None
    goals_per_match_when_refereeing: float | None
    over25_rate_when_refereeing: float | None
    penalties_per_match: float | None
    card_volatility_score: float | None


@router.get("", response_model=list[RefereeResponse])
async def list_referees(
    search: Optional[str] = Query(None),
    min_matches: int = Query(0, ge=0),
    sort_by: str = Query("avg_cards_per_match"),
    session: AsyncSession = Depends(get_async_session),
):
    """List all referees with optional filters."""
    query = select(Referee).where(Referee.total_matches >= min_matches)

    if search:
        query = query.where(Referee.name.ilike(f"%{search}%"))

    sort_map = {
        "avg_cards_per_match": Referee.avg_cards_per_match,
        "total_matches": Referee.total_matches,
        "home_bias_score": Referee.home_bias_score,
        "penalties_per_match": Referee.penalties_per_match,
        "name": Referee.name,
    }
    sort_col = sort_map.get(sort_by, Referee.avg_cards_per_match)
    query = query.order_by(desc(sort_col).nulls_last())

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{referee_id}", response_model=RefereeResponse)
async def get_referee(referee_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get a single referee by ID."""
    ref = await session.get(Referee, referee_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Referee not found")
    return ref


@router.get("/{referee_id}/profile", response_model=RefereeProfileResponse)
async def get_referee_profile(referee_id: int, session: AsyncSession = Depends(get_async_session)):
    """Get the latest calculated referee profile."""
    ref = await session.get(Referee, referee_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Referee not found")

    result = await session.execute(
        select(RefereeProfile)
        .where(RefereeProfile.referee_id == referee_id)
        .order_by(desc(RefereeProfile.calculated_at))
        .limit(1)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        # Return basic data from referee table if no profile calculated yet
        return RefereeProfileResponse(
            referee_id=referee_id,
            cards_per_match_career=ref.avg_cards_per_match,
            cards_per_match_l20=None,
            yellows_per_match_career=ref.avg_yellows_per_match,
            yellows_per_match_l20=None,
            home_bias_score=ref.home_bias_score,
            home_bias_direction=None,
            goals_per_match_when_refereeing=None,
            over25_rate_when_refereeing=None,
            penalties_per_match=ref.penalties_per_match,
            card_volatility_score=None,
        )

    return RefereeProfileResponse(
        referee_id=referee_id,
        cards_per_match_career=profile.cards_per_match_career,
        cards_per_match_l20=profile.cards_per_match_l20,
        yellows_per_match_career=profile.yellows_per_match_career,
        yellows_per_match_l20=profile.yellows_per_match_l20,
        home_bias_score=profile.home_bias_score,
        home_bias_direction=profile.home_bias_direction,
        goals_per_match_when_refereeing=profile.goals_per_match_when_refereeing,
        over25_rate_when_refereeing=profile.over25_rate_when_refereeing,
        penalties_per_match=profile.penalties_per_match,
        card_volatility_score=profile.card_volatility_score,
    )


@router.get("/{referee_id}/matches")
async def get_referee_matches(
    referee_id: int,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    """Get the match log for a referee (last N matches officiated)."""
    ref = await session.get(Referee, referee_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Referee not found")

    result = await session.execute(
        select(RefereeMatchLog)
        .where(RefereeMatchLog.referee_id == referee_id)
        .order_by(desc(RefereeMatchLog.match_date))
        .limit(limit)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        match = await session.get(Match, log.match_id)
        home_team = await session.get(Team, match.home_team_id) if match else None
        away_team = await session.get(Team, match.away_team_id) if match else None

        total_goals = None
        if match and match.home_goals is not None and match.away_goals is not None:
            total_goals = match.home_goals + match.away_goals

        items.append({
            "match_id": log.match_id,
            "date": log.match_date.isoformat(),
            "season": log.season,
            "home_team": (home_team.clean_name or home_team.name) if home_team else "?",
            "away_team": (away_team.clean_name or away_team.name) if away_team else "?",
            "score": f"{match.home_goals}-{match.away_goals}" if match and match.home_goals is not None else None,
            "home_yellows": log.home_yellows,
            "away_yellows": log.away_yellows,
            "home_reds": log.home_reds,
            "away_reds": log.away_reds,
            "total_cards": log.total_cards,
            "total_fouls": log.total_fouls,
            "penalties_awarded": log.penalties_awarded,
            "over_25": total_goals > 2 if total_goals is not None else None,
        })

    return {
        "referee_id": referee_id,
        "referee_name": ref.name,
        "match_count": len(items),
        "matches": items,
    }


@router.get("/{referee_id}/impact")
async def get_referee_impact(
    referee_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Referee impact model data — how this referee affects match outcomes.

    Returns card distribution, home/away bias analysis, goal impact,
    and comparison to league averages.
    """
    ref = await session.get(Referee, referee_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Referee not found")

    # Get all match logs
    result = await session.execute(
        select(RefereeMatchLog)
        .where(RefereeMatchLog.referee_id == referee_id)
        .order_by(desc(RefereeMatchLog.match_date))
    )
    logs = result.scalars().all()

    if not logs:
        return {
            "referee_id": referee_id,
            "referee_name": ref.name,
            "insufficient_data": True,
        }

    # Card distribution
    card_counts = [log.total_cards for log in logs]
    avg_cards = sum(card_counts) / len(card_counts) if card_counts else 0
    home_yellows_total = sum(log.home_yellows for log in logs)
    away_yellows_total = sum(log.away_yellows for log in logs)

    # Home bias
    if away_yellows_total > 0:
        home_bias_ratio = home_yellows_total / away_yellows_total
    else:
        home_bias_ratio = None

    # Goals in their matches
    match_ids = [log.match_id for log in logs]
    goals_result = await session.execute(
        select(Match.home_goals, Match.away_goals).where(
            Match.id.in_(match_ids),
            Match.home_goals.isnot(None),
        )
    )
    match_goals = goals_result.all()
    total_goals_list = [(r[0] + r[1]) for r in match_goals]
    avg_goals = sum(total_goals_list) / len(total_goals_list) if total_goals_list else None
    over25_count = sum(1 for g in total_goals_list if g > 2)
    over25_rate = over25_count / len(total_goals_list) * 100 if total_goals_list else None

    # Last 20 vs career
    recent_logs = logs[:20]
    recent_cards = [log.total_cards for log in recent_logs]
    avg_cards_l20 = sum(recent_cards) / len(recent_cards) if recent_cards else 0

    # Card volatility (std dev)
    import statistics
    volatility = statistics.stdev(card_counts) if len(card_counts) > 1 else 0

    return {
        "referee_id": referee_id,
        "referee_name": ref.name,
        "total_matches": len(logs),
        "disciplinary": {
            "avg_cards_career": round(avg_cards, 2),
            "avg_cards_l20": round(avg_cards_l20, 2),
            "total_yellows": home_yellows_total + away_yellows_total,
            "total_reds": sum(log.home_reds + log.away_reds for log in logs),
            "card_volatility": round(volatility, 2),
            "card_distribution": {
                "0-2": sum(1 for c in card_counts if c <= 2),
                "3-4": sum(1 for c in card_counts if 3 <= c <= 4),
                "5-6": sum(1 for c in card_counts if 5 <= c <= 6),
                "7+": sum(1 for c in card_counts if c >= 7),
            },
        },
        "home_away_bias": {
            "home_yellows_total": home_yellows_total,
            "away_yellows_total": away_yellows_total,
            "home_bias_ratio": round(home_bias_ratio, 3) if home_bias_ratio else None,
            "direction": (
                "home_heavy" if home_bias_ratio and home_bias_ratio > 1.15
                else "away_heavy" if home_bias_ratio and home_bias_ratio < 0.85
                else "neutral"
            ) if home_bias_ratio else "unknown",
        },
        "game_flow": {
            "avg_goals_per_match": round(avg_goals, 2) if avg_goals else None,
            "over25_rate": round(over25_rate, 1) if over25_rate else None,
        },
        "penalties": {
            "total_awarded": sum(log.penalties_awarded for log in logs),
            "per_match": round(sum(log.penalties_awarded for log in logs) / len(logs), 3) if logs else 0,
        },
    }
