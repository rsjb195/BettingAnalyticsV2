"""
Backfill match stats (shots, possession, fouls, cards, corners) for completed
matches that have NULL values for these fields.

The original bootstrap loaded 0 shots/possession/etc because FSMatch was missing
the team_a_*/team_b_* field aliases. This script re-fetches those matches from
the FootyStats API and updates the DB records.

Usage:
    python -m backend.scripts.backfill_match_stats
    python -m backend.scripts.backfill_match_stats --limit 500
    python -m backend.scripts.backfill_match_stats --league-id 1
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from sqlalchemy import select, and_, func

from backend.app.database import get_sync_session
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.league import League
from backend.app.models.match import Match

import backend.app.models  # noqa: F401

logger = logging.getLogger("backfill_match_stats")


def _setup_logging():
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])


async def backfill(limit: int = 0, league_db_id: int | None = None):
    _setup_logging()
    session = get_sync_session()

    try:
        # Find completed matches missing shots data
        q = select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            Match.home_shots.is_(None),
            Match.footystats_id.isnot(None),
        )
        if league_db_id:
            q = q.where(Match.league_id == league_db_id)

        total_missing = session.execute(
            select(func.count()).select_from(q.subquery())
        ).scalar()
        logger.info("Matches missing shots data: %d", total_missing)

        if limit:
            q = q.limit(limit)
        matches_to_update = session.execute(q).scalars().all()
        logger.info("Will update: %d matches", len(matches_to_update))

        updated = 0
        skipped = 0

        async with FootyStatsClient() as client:
            for i, match in enumerate(matches_to_update):
                if i % 50 == 0:
                    logger.info("Progress: %d/%d (updated=%d skipped=%d)",
                                i, len(matches_to_update), updated, skipped)

                detail = await client.get_match_details(match.footystats_id)
                if detail is None:
                    skipped += 1
                    continue

                changed = False

                # Update stats if API provided them
                if detail.home_shots is not None:
                    match.home_shots = detail.home_shots
                    match.away_shots = detail.away_shots
                    changed = True

                if detail.home_shotsOnTarget is not None:
                    match.home_shots_on_target = detail.home_shotsOnTarget
                    match.away_shots_on_target = detail.away_shotsOnTarget
                    changed = True

                if detail.home_possession is not None:
                    match.home_possession = detail.home_possession
                    match.away_possession = detail.away_possession
                    changed = True

                if detail.home_fouls is not None:
                    match.home_fouls = detail.home_fouls
                    match.away_fouls = detail.away_fouls
                    changed = True

                if detail.home_yellow_cards is not None:
                    match.home_yellow_cards = detail.home_yellow_cards
                    match.away_yellow_cards = detail.away_yellow_cards
                    changed = True

                if detail.home_red_cards is not None:
                    match.home_red_cards = detail.home_red_cards
                    match.away_red_cards = detail.away_red_cards
                    changed = True

                if detail.home_corners is not None:
                    match.home_corners = detail.home_corners
                    match.away_corners = detail.away_corners
                    changed = True

                if changed:
                    updated += 1
                else:
                    skipped += 1

                # Commit in batches
                if updated % 100 == 0 and updated > 0:
                    session.commit()
                    logger.info("Committed batch (updated so far: %d)", updated)

        session.commit()
        logger.info(
            "\n"
            "╔══════════════════════════════════════════╗\n"
            "║       BACKFILL MATCH STATS COMPLETE      ║\n"
            "╠══════════════════════════════════════════╣\n"
            "║  Total missing:    %-22d║\n"
            "║  Updated:          %-22d║\n"
            "║  Skipped (no data):%-22d║\n"
            "╚══════════════════════════════════════════╝",
            total_missing, updated, skipped,
        )

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill match stats from FootyStats API")
    parser.add_argument("--limit", type=int, default=0, help="Max matches to update (0 = all)")
    parser.add_argument("--league-id", type=int, default=None, help="DB league ID to limit to")
    args = parser.parse_args()
    asyncio.run(backfill(limit=args.limit, league_db_id=args.league_id))


if __name__ == "__main__":
    main()
