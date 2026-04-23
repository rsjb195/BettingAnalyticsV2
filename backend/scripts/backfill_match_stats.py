"""
Backfill match stats (shots, possession, fouls, cards, corners) for completed
matches that have NULL values for these fields.

Re-fetches league-matches in bulk (one API call per league) and updates existing
DB records. Much faster than fetching individual match detail endpoints.

Usage:
    python -m backend.scripts.backfill_match_stats
    python -m backend.scripts.backfill_match_stats --league-id 1
    python -m backend.scripts.backfill_match_stats --detail   # slow: per-match detail fallback
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select, func

from backend.app.database import get_sync_session
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.league import League
from backend.app.models.match import Match

import backend.app.models  # noqa: F401

logger = logging.getLogger("backfill_match_stats")


def _setup_logging():
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])


async def backfill_via_league(league_db_id: int | None = None):
    """Fast bulk backfill: re-fetch /league-matches per league and UPDATE existing rows."""
    _setup_logging()
    session = get_sync_session()

    try:
        q = select(League)
        if league_db_id:
            q = q.where(League.id == league_db_id)
        leagues = session.execute(q).scalars().all()
        logger.info("Backfilling %d leagues via bulk league-matches fetch...", len(leagues))

        # Build footystats_id -> Match map for fast lookup
        logger.info("Building match lookup map...")
        all_matches = session.execute(
            select(Match).where(Match.footystats_id.isnot(None))
        ).scalars().all()
        match_by_fs_id = {m.footystats_id: m for m in all_matches}
        logger.info("Loaded %d matches into lookup map.", len(match_by_fs_id))

        total_updated = 0
        total_skipped = 0

        async with FootyStatsClient() as client:
            for league in leagues:
                logger.info("Fetching matches for league %d (%s %s)...",
                            league.id, league.name, league.season)

                fs_matches = await client.get_league_matches(league.footystats_id)
                league_updated = 0

                for fm in fs_matches:
                    match = match_by_fs_id.get(fm.id)
                    if match is None:
                        continue

                    changed = False

                    if fm.home_shots is not None and match.home_shots is None:
                        match.home_shots = fm.home_shots
                        match.away_shots = fm.away_shots
                        changed = True

                    if fm.home_shotsOnTarget is not None and match.home_shots_on_target is None:
                        match.home_shots_on_target = fm.home_shotsOnTarget
                        match.away_shots_on_target = fm.away_shotsOnTarget
                        changed = True

                    if fm.home_possession is not None and match.home_possession is None:
                        match.home_possession = fm.home_possession
                        match.away_possession = fm.away_possession
                        changed = True

                    if fm.home_fouls is not None and match.home_fouls is None:
                        match.home_fouls = fm.home_fouls
                        match.away_fouls = fm.away_fouls
                        changed = True

                    if fm.home_yellow_cards is not None and match.home_yellow_cards is None:
                        match.home_yellow_cards = fm.home_yellow_cards
                        match.away_yellow_cards = fm.away_yellow_cards
                        changed = True

                    if fm.home_red_cards is not None and match.home_red_cards is None:
                        match.home_red_cards = fm.home_red_cards
                        match.away_red_cards = fm.away_red_cards
                        changed = True

                    if fm.home_corners is not None and match.home_corners is None:
                        match.home_corners = fm.home_corners
                        match.away_corners = fm.away_corners
                        changed = True

                    if changed:
                        league_updated += 1
                    else:
                        total_skipped += 1

                session.commit()
                total_updated += league_updated
                logger.info("  League %d: %d matches updated.", league.id, league_updated)

        # Verify results
        still_null = session.execute(
            select(func.count(Match.id)).where(
                Match.status == "complete",
                Match.home_goals.isnot(None),
                Match.home_shots.is_(None),
            )
        ).scalar()

        logger.info(
            "\n"
            "╔══════════════════════════════════════════╗\n"
            "║       BACKFILL MATCH STATS COMPLETE      ║\n"
            "╠══════════════════════════════════════════╣\n"
            "║  Leagues processed: %-21d║\n"
            "║  Matches updated:   %-21d║\n"
            "║  Still NULL shots:  %-21d║\n"
            "╚══════════════════════════════════════════╝",
            len(leagues), total_updated, still_null,
        )

    finally:
        session.close()


async def backfill_via_detail(limit: int = 0, league_db_id: int | None = None):
    """Slow per-match fallback: fetches individual match detail endpoint for each match."""
    _setup_logging()
    session = get_sync_session()

    try:
        # Filter on corners NULL — shots may be populated but corners/fouls/cards may not be
        q = select(Match).where(
            Match.status == "complete",
            Match.home_goals.isnot(None),
            Match.home_corners.is_(None),
            Match.footystats_id.isnot(None),
        ).order_by(Match.match_date.desc())
        if league_db_id:
            q = q.where(Match.league_id == league_db_id)

        total_missing = session.execute(
            select(func.count()).select_from(q.subquery())
        ).scalar()
        logger.info("Matches missing corners/detail stats: %d", total_missing)

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

                if updated % 100 == 0 and updated > 0:
                    session.commit()

        session.commit()
        logger.info("Done: updated=%d skipped=%d", updated, skipped)

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill match stats from FootyStats API")
    parser.add_argument("--detail", action="store_true",
                        help="Use slow per-match detail endpoint instead of bulk league-matches")
    parser.add_argument("--limit", type=int, default=0,
                        help="(--detail mode only) Max matches to update")
    parser.add_argument("--league-id", type=int, default=None, help="DB league ID to limit to")
    args = parser.parse_args()

    if args.detail:
        asyncio.run(backfill_via_detail(limit=args.limit, league_db_id=args.league_id))
    else:
        asyncio.run(backfill_via_league(league_db_id=args.league_id))


if __name__ == "__main__":
    main()
