"""
FastAPI application entry point.

Configures CORS, includes all API routers, manages lifespan events
(scheduler start/stop, database connection pool), and serves the
football quant analytics API.

Run:
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.leagues import router as leagues_router
from backend.app.api.teams import router as teams_router
from backend.app.api.matches import router as matches_router
from backend.app.api.players import router as players_router
from backend.app.api.referees import router as referees_router
from backend.app.api.slate import router as slate_router
from backend.app.config import get_settings
from backend.app.ingestion.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI application."""
    logger.info("Starting Football Quant Analytics Platform...")
    if settings.environment != "development":
        start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutting down Football Quant Analytics Platform.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Football Quant Analytics API",
    description="Professional football analytics platform for accumulator construction and edge detection.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request timing middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.debug(
        "%s %s -> %d (%.0fms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(leagues_router, prefix="/api/leagues", tags=["Leagues"])
app.include_router(teams_router, prefix="/api/teams", tags=["Teams"])
app.include_router(matches_router, prefix="/api/matches", tags=["Matches"])
app.include_router(players_router, prefix="/api/players", tags=["Players"])
app.include_router(referees_router, prefix="/api/referees", tags=["Referees"])
app.include_router(slate_router, prefix="/api", tags=["Slate & Accumulator"])


# ---------------------------------------------------------------------------
# Health / status endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/ticker", tags=["System"])
async def get_ticker():
    """
    Return the last 20 match results for the scrolling ticker component.

    Includes recent results and key league stats for the ticker tape display.
    """
    from sqlalchemy import select, desc
    from backend.app.database import async_session_ctx
    from backend.app.models.match import Match
    from backend.app.models.team import Team

    async with async_session_ctx() as session:
        result = await session.execute(
            select(Match)
            .where(Match.status == "complete")
            .order_by(desc(Match.match_date))
            .limit(20)
        )
        matches = result.scalars().all()

        ticker_items = []
        for m in matches:
            # Load team names
            home = await session.get(Team, m.home_team_id)
            away = await session.get(Team, m.away_team_id)
            home_name = (home.short_name or home.clean_name or home.name).upper() if home else "?"
            away_name = (away.short_name or away.clean_name or away.name).upper() if away else "?"

            if m.home_goals is not None and m.away_goals is not None:
                if m.home_goals > m.away_goals:
                    result_type = "home_win"
                elif m.away_goals > m.home_goals:
                    result_type = "away_win"
                else:
                    result_type = "draw"
            else:
                result_type = "unknown"

            ticker_items.append({
                "home_team": home_name,
                "away_team": away_name,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "result_type": result_type,
                "match_date": m.match_date.isoformat() if m.match_date else None,
            })

        return {"items": ticker_items}


@app.get("/api/performance", tags=["Performance"])
async def get_performance():
    """
    P&L tracker — returns accumulator performance metrics.

    Shows ROI by league, market type, and time period.
    """
    from sqlalchemy import select, func
    from backend.app.database import async_session_ctx
    from backend.app.models.accumulator import AccumulatorLog

    async with async_session_ctx() as session:
        # Overall stats
        total_result = await session.execute(select(func.count()).select_from(AccumulatorLog))
        total = total_result.scalar() or 0

        wins_result = await session.execute(
            select(func.count()).select_from(AccumulatorLog).where(AccumulatorLog.result == "win")
        )
        wins = wins_result.scalar() or 0

        total_staked_result = await session.execute(
            select(func.sum(AccumulatorLog.stake)).where(AccumulatorLog.result != "pending")
        )
        total_staked = total_staked_result.scalar() or 0.0

        total_returned_result = await session.execute(
            select(func.sum(AccumulatorLog.actual_return)).where(AccumulatorLog.result != "pending")
        )
        total_returned = total_returned_result.scalar() or 0.0

        roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0.0

        # Recent accumulators
        recent_result = await session.execute(
            select(AccumulatorLog)
            .order_by(AccumulatorLog.created_at.desc())
            .limit(20)
        )
        recent = recent_result.scalars().all()

        return {
            "total_accumulators": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": (wins / total * 100) if total > 0 else 0.0,
            "total_staked": total_staked,
            "total_returned": total_returned,
            "net_pnl": total_returned - total_staked,
            "roi_pct": round(roi, 2),
            "recent": [
                {
                    "id": a.id,
                    "slate_date": a.slate_date.isoformat(),
                    "legs": a.legs,
                    "actual_odds": a.actual_odds,
                    "stake": a.stake,
                    "potential_return": a.potential_return,
                    "result": a.result,
                    "actual_return": a.actual_return,
                }
                for a in recent
            ],
        }
