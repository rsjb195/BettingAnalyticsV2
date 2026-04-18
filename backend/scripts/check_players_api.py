"""Diagnostic: check what the league-players API returns and why players aren't loading."""
import asyncio
import logging
import sys
from sqlalchemy import select, func
from backend.app.database import get_sync_session
from backend.app.ingestion.footystats_client import FootyStatsClient, FSPlayer
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

    # Build global team map (all teams, all leagues)
    all_teams = session.execute(select(Team)).scalars().all()
    team_fs_to_db = {t.footystats_id: t.id for t in all_teams}
    logger.info("Total teams in DB: %d (footystats IDs: %s)", len(all_teams), sorted(team_fs_to_db.keys())[:10])

    # Get most recent league (first in DB = newest season)
    league = session.execute(
        select(League).order_by(League.id.asc()).limit(1)
    ).scalar_one_or_none()
    if not league:
        logger.error("No leagues found")
        return

    logger.info("Testing with: %s (footystats_id=%d)", league.name, league.footystats_id)

    async with FootyStatsClient() as client:
        raw = await client._request("/league-players", {"league_id": league.footystats_id})
        if not raw:
            logger.error("Empty response from /league-players")
            return

        logger.info("Response type: %s, length: %d", type(raw).__name__, len(raw) if isinstance(raw, list) else 1)

        if isinstance(raw, list) and raw:
            # Test FSPlayer parsing
            fp = FSPlayer(**raw[0])
            logger.info("\nFSPlayer parsed team_id: %s (from club_team_id=%s)",
                        fp.team_id, raw[0].get("club_team_id"))

            # Check all club_team_ids against our DB
            club_ids = {p.get("club_team_id") for p in raw if isinstance(p, dict)}
            matched = {cid for cid in club_ids if team_fs_to_db.get(cid)}
            missing = club_ids - matched
            logger.info("\nUnique club_team_ids from API: %d", len(club_ids))
            logger.info("Matched to DB teams: %d", len(matched))
            logger.info("Missing from DB: %d  (sample: %s)", len(missing), sorted(missing)[:10])

            if missing:
                logger.info("\nNOTE: These team IDs from /league-players are not in our teams table.")
                logger.info("This means we need to load these teams, or the API uses different IDs.")

                # Check what the /league-teams endpoint returns for this league
                logger.info("\nChecking /league-teams for same league...")
                teams_data = await client._request("/league-teams", {"league_id": league.footystats_id})
                if isinstance(teams_data, list) and teams_data:
                    team_ids_from_teams_ep = {t.get("id") for t in teams_data if isinstance(t, dict)}
                    logger.info("/league-teams returned %d teams, IDs: %s",
                                len(teams_data), sorted(team_ids_from_teams_ep)[:10])
                    overlap = club_ids & team_ids_from_teams_ep
                    logger.info("club_team_ids that match /league-teams IDs: %d/%d",
                                len(overlap), len(club_ids))

    session.close()


asyncio.run(check())
