"""
Match API endpoints.

Provides match listing, detail views, upcoming fixtures, Saturday slate data,
model outputs, and edge detection.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.match import Match
from backend.app.models.team import Team
from backend.app.models.referee import Referee
from backend.app.models.accumulator import ModelOutput

logger = logging.getLogger("api.matches")
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MatchSummary(BaseModel):
    id: int
    footystats_id: int | None
    league_id: int
    home_team_id: int
    away_team_id: int
    home_team_name: str | None = None
    away_team_name: str | None = None
    match_date: str
    status: str
    home_goals: int | None
    away_goals: int | None
    odds_home: float | None
    odds_draw: float | None
    odds_away: float | None


class MatchDetail(BaseModel):
    id: int
    footystats_id: int | None
    league_id: int
    home_team_id: int
    away_team_id: int
    home_team_name: str | None
    away_team_name: str | None
    season: str
    game_week: int | None
    match_date: str
    status: str
    home_goals: int | None
    away_goals: int | None
    home_goals_ht: int | None
    away_goals_ht: int | None
    home_xg: float | None
    away_xg: float | None
    home_shots: int | None
    away_shots: int | None
    home_shots_on_target: int | None
    away_shots_on_target: int | None
    home_possession: float | None
    away_possession: float | None
    home_fouls: int | None
    away_fouls: int | None
    home_yellow_cards: int | None
    away_yellow_cards: int | None
    home_red_cards: int | None
    away_red_cards: int | None
    home_corners: int | None
    away_corners: int | None
    btts: bool | None
    over_25: bool | None
    referee_id: int | None
    referee_name: str | None
    stadium: str | None
    attendance: int | None
    odds_home: float | None
    odds_draw: float | None
    odds_away: float | None
    odds_over25: float | None
    odds_btts_yes: float | None
    home_ppg_pre: float | None
    away_ppg_pre: float | None
    model_output: dict | None


class ModelOutputResponse(BaseModel):
    match_id: int
    our_home_prob: float
    our_draw_prob: float
    our_away_prob: float
    our_home_odds: float
    our_draw_odds: float
    our_away_odds: float
    market_home_odds: float | None
    market_draw_odds: float | None
    market_away_odds: float | None
    home_edge_pct: float | None
    draw_edge_pct: float | None
    away_edge_pct: float | None
    best_value_outcome: str | None
    confidence_rating: float | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_matches(
    league_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """Paginated match list with date/league/status filters."""
    query = select(Match)

    if league_id is not None:
        query = query.where(Match.league_id == league_id)
    if status:
        query = query.where(Match.status == status)
    if date_from:
        query = query.where(Match.match_date >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(Match.match_date <= date.fromisoformat(date_to))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar()

    query = query.order_by(desc(Match.match_date)).offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    matches = result.scalars().all()

    items = []
    for m in matches:
        home = await session.get(Team, m.home_team_id)
        away = await session.get(Team, m.away_team_id)
        items.append({
            "id": m.id,
            "league_id": m.league_id,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_team_name": (home.clean_name or home.name) if home else None,
            "away_team_name": (away.clean_name or away.name) if away else None,
            "match_date": m.match_date.isoformat(),
            "status": m.status,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "odds_home": m.odds_home,
            "odds_draw": m.odds_draw,
            "odds_away": m.odds_away,
        })

    return {"total": total, "page": page, "per_page": per_page, "matches": items}


@router.get("/upcoming")
async def get_upcoming_matches(
    days: int = Query(7, ge=1, le=30),
    league_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Get upcoming fixtures within the next N days."""
    today = date.today()
    end = today + timedelta(days=days)

    query = select(Match).where(
        Match.match_date >= today,
        Match.match_date <= end,
        Match.status == "upcoming",
    )
    if league_id is not None:
        query = query.where(Match.league_id == league_id)
    query = query.order_by(Match.match_date)

    result = await session.execute(query)
    matches = result.scalars().all()

    items = []
    for m in matches:
        home = await session.get(Team, m.home_team_id)
        away = await session.get(Team, m.away_team_id)
        ref = await session.get(Referee, m.referee_id) if m.referee_id else None

        # Get model output if available
        mo_result = await session.execute(
            select(ModelOutput)
            .where(ModelOutput.match_id == m.id)
            .order_by(desc(ModelOutput.generated_at))
            .limit(1)
        )
        mo = mo_result.scalar_one_or_none()

        items.append({
            "id": m.id,
            "league_id": m.league_id,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_team_name": (home.clean_name or home.name) if home else None,
            "away_team_name": (away.clean_name or away.name) if away else None,
            "match_date": m.match_date.isoformat(),
            "odds_home": m.odds_home,
            "odds_draw": m.odds_draw,
            "odds_away": m.odds_away,
            "odds_over25": m.odds_over25,
            "odds_btts_yes": m.odds_btts_yes,
            "referee_name": ref.name if ref else None,
            "referee_avg_cards": ref.avg_cards_per_match if ref else None,
            "home_ppg": m.home_ppg_pre,
            "away_ppg": m.away_ppg_pre,
            "model": {
                "our_home_prob": mo.our_home_prob,
                "our_draw_prob": mo.our_draw_prob,
                "our_away_prob": mo.our_away_prob,
                "home_edge": mo.home_edge_pct,
                "draw_edge": mo.draw_edge_pct,
                "away_edge": mo.away_edge_pct,
                "best_value": mo.best_value_outcome,
                "confidence": mo.confidence_rating,
            } if mo else None,
        })

    return {"count": len(items), "fixtures": items}


@router.get("/saturday-slate")
async def get_saturday_slate(session: AsyncSession = Depends(get_async_session)):
    """
    Get all Saturday 3pm fixtures with full model data.

    Returns the next Saturday's fixtures if today is not Saturday,
    otherwise returns today's fixtures.
    """
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday) if today.weekday() != 5 else today

    result = await session.execute(
        select(Match)
        .where(Match.match_date == saturday)
        .order_by(Match.league_id)
    )
    matches = result.scalars().all()

    fixtures = []
    for m in matches:
        home = await session.get(Team, m.home_team_id)
        away = await session.get(Team, m.away_team_id)
        ref = await session.get(Referee, m.referee_id) if m.referee_id else None

        mo_result = await session.execute(
            select(ModelOutput)
            .where(ModelOutput.match_id == m.id)
            .order_by(desc(ModelOutput.generated_at))
            .limit(1)
        )
        mo = mo_result.scalar_one_or_none()

        fixtures.append({
            "match_id": m.id,
            "league_id": m.league_id,
            "home_team": {
                "id": m.home_team_id,
                "name": (home.clean_name or home.name) if home else "?",
                "ppg": m.home_ppg_pre,
                "form": m.home_form_pre,
            },
            "away_team": {
                "id": m.away_team_id,
                "name": (away.clean_name or away.name) if away else "?",
                "ppg": m.away_ppg_pre,
                "form": m.away_form_pre,
            },
            "referee": {
                "id": ref.id,
                "name": ref.name,
                "avg_cards": ref.avg_cards_per_match,
                "home_bias": ref.home_bias_score,
            } if ref else None,
            "odds": {
                "home": m.odds_home,
                "draw": m.odds_draw,
                "away": m.odds_away,
                "over25": m.odds_over25,
                "btts_yes": m.odds_btts_yes,
            },
            "model": {
                "our_home_prob": mo.our_home_prob,
                "our_draw_prob": mo.our_draw_prob,
                "our_away_prob": mo.our_away_prob,
                "home_edge": mo.home_edge_pct,
                "draw_edge": mo.draw_edge_pct,
                "away_edge": mo.away_edge_pct,
                "best_value": mo.best_value_outcome,
                "confidence": mo.confidence_rating,
            } if mo else None,
            "status": m.status,
        })

    return {
        "slate_date": saturday.isoformat(),
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


@router.get("/{match_id}")
async def get_match_detail(match_id: int, session: AsyncSession = Depends(get_async_session)):
    """Full match detail with all stats and model output."""
    m = await session.get(Match, match_id)
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")

    home = await session.get(Team, m.home_team_id)
    away = await session.get(Team, m.away_team_id)
    ref = await session.get(Referee, m.referee_id) if m.referee_id else None

    mo_result = await session.execute(
        select(ModelOutput).where(ModelOutput.match_id == m.id).order_by(desc(ModelOutput.generated_at)).limit(1)
    )
    mo = mo_result.scalar_one_or_none()

    return MatchDetail(
        id=m.id,
        footystats_id=m.footystats_id,
        league_id=m.league_id,
        home_team_id=m.home_team_id,
        away_team_id=m.away_team_id,
        home_team_name=(home.clean_name or home.name) if home else None,
        away_team_name=(away.clean_name or away.name) if away else None,
        season=m.season,
        game_week=m.game_week,
        match_date=m.match_date.isoformat(),
        status=m.status,
        home_goals=m.home_goals,
        away_goals=m.away_goals,
        home_goals_ht=m.home_goals_ht,
        away_goals_ht=m.away_goals_ht,
        home_xg=m.home_xg,
        away_xg=m.away_xg,
        home_shots=m.home_shots,
        away_shots=m.away_shots,
        home_shots_on_target=m.home_shots_on_target,
        away_shots_on_target=m.away_shots_on_target,
        home_possession=m.home_possession,
        away_possession=m.away_possession,
        home_fouls=m.home_fouls,
        away_fouls=m.away_fouls,
        home_yellow_cards=m.home_yellow_cards,
        away_yellow_cards=m.away_yellow_cards,
        home_red_cards=m.home_red_cards,
        away_red_cards=m.away_red_cards,
        home_corners=m.home_corners,
        away_corners=m.away_corners,
        btts=m.btts,
        over_25=m.over_25,
        referee_id=m.referee_id,
        referee_name=ref.name if ref else None,
        stadium=m.stadium,
        attendance=m.attendance,
        odds_home=m.odds_home,
        odds_draw=m.odds_draw,
        odds_away=m.odds_away,
        odds_over25=m.odds_over25,
        odds_btts_yes=m.odds_btts_yes,
        home_ppg_pre=m.home_ppg_pre,
        away_ppg_pre=m.away_ppg_pre,
        model_output={
            "our_home_prob": mo.our_home_prob,
            "our_draw_prob": mo.our_draw_prob,
            "our_away_prob": mo.our_away_prob,
            "home_edge": mo.home_edge_pct,
            "draw_edge": mo.draw_edge_pct,
            "away_edge": mo.away_edge_pct,
            "best_value": mo.best_value_outcome,
            "confidence": mo.confidence_rating,
        } if mo else None,
    )


@router.get("/model/outputs")
async def get_model_outputs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
):
    """List model probability outputs for all matches."""
    count_result = await session.execute(select(func.count()).select_from(ModelOutput))
    total = count_result.scalar()

    result = await session.execute(
        select(ModelOutput)
        .order_by(desc(ModelOutput.generated_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    outputs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "outputs": [
            {
                "match_id": o.match_id,
                "generated_at": o.generated_at.isoformat(),
                "our_home_prob": o.our_home_prob,
                "our_draw_prob": o.our_draw_prob,
                "our_away_prob": o.our_away_prob,
                "home_edge_pct": o.home_edge_pct,
                "draw_edge_pct": o.draw_edge_pct,
                "away_edge_pct": o.away_edge_pct,
                "best_value_outcome": o.best_value_outcome,
                "confidence_rating": o.confidence_rating,
            }
            for o in outputs
        ],
    }


@router.get("/model/edge")
async def get_edge_matches(
    min_edge: float = Query(0.02, description="Minimum edge percentage"),
    session: AsyncSession = Depends(get_async_session),
):
    """Find matches where we have positive edge vs market odds."""
    result = await session.execute(
        select(ModelOutput).where(
            func.greatest(
                func.coalesce(ModelOutput.home_edge_pct, 0),
                func.coalesce(ModelOutput.draw_edge_pct, 0),
                func.coalesce(ModelOutput.away_edge_pct, 0),
            ) >= min_edge
        ).order_by(desc(ModelOutput.generated_at))
    )
    outputs = result.scalars().all()

    items = []
    for o in outputs:
        match = await session.get(Match, o.match_id)
        if not match or match.status != "upcoming":
            continue

        home = await session.get(Team, match.home_team_id)
        away = await session.get(Team, match.away_team_id)

        items.append({
            "match_id": o.match_id,
            "match_date": match.match_date.isoformat(),
            "home_team": (home.clean_name or home.name) if home else "?",
            "away_team": (away.clean_name or away.name) if away else "?",
            "our_home_prob": o.our_home_prob,
            "our_draw_prob": o.our_draw_prob,
            "our_away_prob": o.our_away_prob,
            "home_edge": o.home_edge_pct,
            "draw_edge": o.draw_edge_pct,
            "away_edge": o.away_edge_pct,
            "best_value": o.best_value_outcome,
            "confidence": o.confidence_rating,
            "market_odds": {
                "home": o.market_home_odds,
                "draw": o.market_draw_odds,
                "away": o.market_away_odds,
            },
        })

    return {"count": len(items), "edge_matches": items}
