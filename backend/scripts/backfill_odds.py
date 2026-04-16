"""Backfill odds data for matches that have NULL odds from initial bootstrap."""
import asyncio
import logging
import sys
import time

from sqlalchemy import select, update

from backend.app.database import get_sync_session
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.league import League
from backend.app.models.match import Match

import backend.app.models  # noqa: F401

logger = logging.getLogger("backfill_odds")

fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])


async def backfill():
    start = time.time()
    session = get_sync_session()

    leagues = session.execute(select(League)).scalars().all()
    logger.info("Found %d leagues.", len(leagues))

    total_updated = 0

    async with FootyStatsClient() as client:
        for league in leagues:
            logger.info("Processing league %d: %s %s", league.id, league.name, league.season)

            # Get matches from API for this league
            fs_matches = await client.get_league_matches(league.footystats_id)
            logger.info("  API returned %d matches.", len(fs_matches))

            # Build lookup by footystats_id
            api_odds = {}
            for fm in fs_matches:
                if fm.odds_ft_1 or fm.odds_ft_x or fm.odds_ft_2:
                    api_odds[fm.id] = {
                        "odds_home": fm.odds_ft_1,
                        "odds_draw": fm.odds_ft_x,
                        "odds_away": fm.odds_ft_2,
                        "odds_over25": fm.odds_over25,
                        "odds_under25": fm.odds_under25,
                        "odds_btts_yes": fm.odds_btts_yes,
                        "odds_btts_no": fm.odds_btts_no,
                    }

            logger.info("  %d matches have odds data.", len(api_odds))

            # Get DB matches for this league that need odds (NULL or 0)
            from sqlalchemy import or_
            db_matches = session.execute(
                select(Match).where(
                    Match.league_id == league.id,
                    or_(Match.odds_home.is_(None), Match.odds_home == 0),
                )
            ).scalars().all()

            updated = 0
            for m in db_matches:
                if m.footystats_id in api_odds:
                    odds = api_odds[m.footystats_id]
                    m.odds_home = odds["odds_home"]
                    m.odds_draw = odds["odds_draw"]
                    m.odds_away = odds["odds_away"]
                    m.odds_over25 = odds["odds_over25"]
                    m.odds_under25 = odds["odds_under25"]
                    m.odds_btts_yes = odds["odds_btts_yes"]
                    m.odds_btts_no = odds["odds_btts_no"]
                    updated += 1

            session.commit()
            total_updated += updated
            logger.info("  Updated %d matches with odds.", updated)

    elapsed = time.time() - start
    logger.info("Backfill complete in %.1fs. Updated %d matches total.", elapsed, total_updated)
    session.close()


if __name__ == "__main__":
    asyncio.run(backfill())
