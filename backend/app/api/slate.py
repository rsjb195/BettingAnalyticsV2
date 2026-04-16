"""
Slate & Accumulator API endpoints.

Provides accumulator build, save, and history endpoints.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_async_session
from backend.app.models.accumulator import AccumulatorLog

logger = logging.getLogger("api.slate")
router = APIRouter()


class AccumulatorLeg(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    selection: str  # "home" | "draw" | "away"
    odds: float
    our_probability: float
    edge_pct: float


class AccumulatorSaveRequest(BaseModel):
    slate_date: str  # YYYY-MM-DD
    legs: list[AccumulatorLeg]
    target_odds: float
    actual_odds: float
    our_probability: float
    stake: float = 50.0
    potential_return: float
    notes: str | None = None


class AccumulatorResponse(BaseModel):
    id: int
    slate_date: str
    legs: list
    target_odds: float
    actual_odds: float
    our_probability: float
    stake: float
    potential_return: float
    result: str
    actual_return: float | None
    notes: str | None


@router.get("/accumulator/build")
async def build_accumulator(
    target_odds: float = Query(25.0, description="Target combined odds"),
    min_edge: float = Query(0.02, description="Minimum edge per leg"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Auto-build optimal accumulator combinations targeting specified odds.

    Filters available outcomes by minimum edge, then uses combinatorial
    search to find the best combinations matching target odds.
    Returns top 5 combinations ranked by expected value.
    """
    from backend.app.models.accumulator import ModelOutput
    from backend.app.models.match import Match
    from backend.app.models.team import Team
    from backend.app.config import get_settings

    settings = get_settings()

    # Get all upcoming matches with model outputs
    result = await session.execute(
        select(ModelOutput, Match)
        .join(Match, ModelOutput.match_id == Match.id)
        .where(Match.status == "upcoming")
        .order_by(desc(ModelOutput.generated_at))
    )
    rows = result.all()

    # Build available outcomes with positive edge
    available: list[dict] = []
    seen_matches = set()

    for mo, match in rows:
        if match.id in seen_matches:
            continue
        seen_matches.add(match.id)

        home = await session.get(Team, match.home_team_id)
        away = await session.get(Team, match.away_team_id)
        h_name = (home.clean_name or home.name) if home else "?"
        a_name = (away.clean_name or away.name) if away else "?"

        for outcome, prob, edge, odds in [
            ("home", mo.our_home_prob, mo.home_edge_pct, mo.market_home_odds),
            ("draw", mo.our_draw_prob, mo.draw_edge_pct, mo.market_draw_odds),
            ("away", mo.our_away_prob, mo.away_edge_pct, mo.market_away_odds),
        ]:
            if edge is not None and edge >= min_edge and odds and odds > 0:
                available.append({
                    "match_id": match.id,
                    "home_team": h_name,
                    "away_team": a_name,
                    "selection": outcome,
                    "odds": odds,
                    "our_probability": prob,
                    "edge_pct": edge,
                    "confidence": mo.confidence_rating or 5.0,
                    "score": edge * (mo.confidence_rating or 5.0),
                })

    if not available:
        return {
            "target_odds": target_odds,
            "combinations": [],
            "message": "No outcomes with sufficient positive edge found.",
        }

    # Sort by score (edge * confidence)
    available.sort(key=lambda x: x["score"], reverse=True)

    # Combinatorial search for target odds
    from itertools import combinations

    best_combos = []
    max_legs = min(8, len(available))

    for num_legs in range(2, max_legs + 1):
        for combo in combinations(available, num_legs):
            # Ensure no duplicate matches in same combo
            match_ids = [leg["match_id"] for leg in combo]
            if len(set(match_ids)) != len(match_ids):
                continue

            combined_odds = 1.0
            combined_prob = 1.0
            for leg in combo:
                combined_odds *= leg["odds"]
                combined_prob *= leg["our_probability"]

            # Check if within target range (allow 20% tolerance)
            if combined_odds < target_odds * 0.5 or combined_odds > target_odds * 2.0:
                continue

            ev = combined_prob * combined_odds * settings.default_stake - settings.default_stake

            best_combos.append({
                "legs": [
                    {
                        "match_id": l["match_id"],
                        "home_team": l["home_team"],
                        "away_team": l["away_team"],
                        "selection": l["selection"],
                        "odds": l["odds"],
                        "our_probability": round(l["our_probability"], 4),
                        "edge_pct": round(l["edge_pct"], 4),
                    }
                    for l in combo
                ],
                "combined_odds": round(combined_odds, 2),
                "our_win_probability": round(combined_prob, 6),
                "expected_value": round(ev, 2),
                "potential_return": round(combined_odds * settings.default_stake, 2),
                "stake": settings.default_stake,
            })

    # Sort by expected value, return top 5
    best_combos.sort(key=lambda x: x["expected_value"], reverse=True)

    return {
        "target_odds": target_odds,
        "available_outcomes": len(available),
        "combinations": best_combos[:5],
    }


@router.post("/accumulator/save", response_model=AccumulatorResponse)
async def save_accumulator(
    request: AccumulatorSaveRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Save an accumulator selection to the log."""
    acc = AccumulatorLog(
        slate_date=date.fromisoformat(request.slate_date),
        legs=[leg.model_dump() for leg in request.legs],
        target_odds=request.target_odds,
        actual_odds=request.actual_odds,
        our_probability=request.our_probability,
        stake=request.stake,
        potential_return=request.potential_return,
        result="pending",
        notes=request.notes,
    )
    session.add(acc)
    await session.flush()

    return AccumulatorResponse(
        id=acc.id,
        slate_date=request.slate_date,
        legs=acc.legs,
        target_odds=acc.target_odds,
        actual_odds=acc.actual_odds,
        our_probability=acc.our_probability,
        stake=acc.stake,
        potential_return=acc.potential_return,
        result=acc.result,
        actual_return=acc.actual_return,
        notes=acc.notes,
    )


@router.get("/accumulator/log")
async def get_accumulator_log(
    result_filter: Optional[str] = Query(None, alias="result"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    """History of all accumulators."""
    query = select(AccumulatorLog)
    if result_filter:
        query = query.where(AccumulatorLog.result == result_filter)
    query = query.order_by(desc(AccumulatorLog.created_at)).offset((page - 1) * per_page).limit(per_page)

    result = await session.execute(query)
    accumulators = result.scalars().all()

    return {
        "page": page,
        "per_page": per_page,
        "accumulators": [
            {
                "id": a.id,
                "slate_date": a.slate_date.isoformat(),
                "legs": a.legs,
                "target_odds": a.target_odds,
                "actual_odds": a.actual_odds,
                "our_probability": a.our_probability,
                "stake": a.stake,
                "potential_return": a.potential_return,
                "result": a.result,
                "actual_return": a.actual_return,
                "notes": a.notes,
            }
            for a in accumulators
        ],
    }
