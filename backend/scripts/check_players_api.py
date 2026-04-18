"""Diagnostic: check what the league-players API returns and why players aren't loading."""
import asyncio
import logging
import sys
from sqlalchemy import select, func
from backend.app.database import get_sync_session
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.league import League
from backend.app.models.team import Team
from backend.app.models.player import Player
import backend.app.models  # noqa

logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("check_players")


async def check():
    session = get_sync_session()

    player_count = session.execute(select(func.count()).select_from(Player)).scalar()
    logger.info("Current players in DB: %d", player_count)

    # Get most recent league
    league = session.execute(
        select(League).order_by(League.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not league:
        logger.error("No leagues found")
        return

    logger.info("Testing with: %s (footystats_id=%d)", league.name, league.footystats_id)

    # Check what teams exist for this league
    teams = session.execute(
        select(Team).where(Team.league_id == league.id)
    ).scalars().all()
    team_fs_ids = {t.footystats_id: t.id for t in teams}
    logger.info("Teams in this league: %d (footystats IDs: %s)", len(teams), list(team_fs_ids.keys())[:5])

    async with FootyStatsClient() as client:
        raw = await client._request("/league-players", {"league_id": league.footystats_id})
        if not raw:
            logger.error("Empty response from /league-players")
            return

        logger.info("Response type: %s, length: %d", type(raw).__name__, len(raw) if isinstance(raw, list) else 1)

        if isinstance(raw, list) and raw:
            first = raw[0]
            logger.info("\nFirst player raw keys:")
            for k, v in sorted(first.items()):
                if v is not None and v != "" and v != 0:
                    logger.info("  %s = %r", k, v)

            logger.info("\nChecking team_id mapping for first 5 players:")
            for p in raw[:5]:
                tid = p.get("team_id")
                db_id = team_fs_ids.get(tid)
                logger.info("  player %s: team_id=%s -> db_id=%s (%s)",
                            p.get("full_name") or p.get("known_as", "?"),
                            tid, db_id, "OK" if db_id else "MISSING")

        elif isinstance(raw, dict):
            logger.info("Dict response keys: %s", list(raw.keys())[:20])

    session.close()


asyncio.run(check())
