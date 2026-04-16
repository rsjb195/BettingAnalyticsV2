"""
Daily refresh script — keeps the database up to date with latest results.

Runs daily at 3am UK time (scheduled via APScheduler or cron).
Saturday-specific logic runs at 9am on Saturdays to prep the slate.

Usage:
    python -m backend.scripts.daily_refresh
    python -m backend.scripts.daily_refresh --saturday-slate
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, date

from sqlalchemy import select, update

from backend.app.config import get_settings
from backend.app.database import get_sync_session, get_sync_engine, Base
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.ingestion_log import IngestionLog
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.team import Team
from backend.app.models.referee import Referee, RefereeMatchLog

import backend.app.models  # noqa: F401

logger = logging.getLogger("daily_refresh")


def _setup_logging() -> None:
    import os
    os.makedirs("logs", exist_ok=True)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/daily_refresh.log", mode="a"),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


async def _refresh_todays_matches(client: FootyStatsClient, session) -> int:
    """Fetch today's matches and update any that have completed."""
    logger.info("Refreshing today's matches...")
    fs_matches = await client.get_todays_matches()

    # Build lookup maps
    team_fs_to_db = {}
    for t in session.execute(select(Team)).scalars().all():
        team_fs_to_db[t.footystats_id] = t.id

    league_map = {}
    for lg in session.execute(select(League)).scalars().all():
        league_map[lg.footystats_id] = lg

    referee_fs_to_db = {}
    for r in session.execute(select(Referee)).scalars().all():
        if r.footystats_id:
            referee_fs_to_db[r.footystats_id] = r.id

    existing_fs_ids = set()
    for row in session.execute(select(Match.footystats_id).where(Match.footystats_id.isnot(None))):
        existing_fs_ids.add(row[0])

    created = 0
    updated = 0

    for fm in fs_matches:
        home_db_id = team_fs_to_db.get(fm.homeID)
        away_db_id = team_fs_to_db.get(fm.awayID)
        if not home_db_id or not away_db_id:
            continue

        league_obj = league_map.get(fm.league_id)
        if not league_obj:
            continue

        is_complete = fm.status == "complete" or (
            fm.homeGoalCount is not None and fm.awayGoalCount is not None
        )

        if fm.id in existing_fs_ids:
            # Update existing match if it has completed
            if is_complete:
                existing = session.execute(
                    select(Match).where(Match.footystats_id == fm.id)
                ).scalar_one_or_none()

                if existing and existing.status != "complete":
                    hg = fm.homeGoalCount
                    ag = fm.awayGoalCount
                    total_goals = (hg or 0) + (ag or 0) if hg is not None and ag is not None else None

                    existing.status = "complete"
                    existing.home_goals = hg
                    existing.away_goals = ag
                    existing.home_xg = fm.home_xg
                    existing.away_xg = fm.away_xg
                    existing.home_shots = fm.home_shots
                    existing.away_shots = fm.away_shots
                    existing.home_shots_on_target = fm.home_shotsOnTarget
                    existing.away_shots_on_target = fm.away_shotsOnTarget
                    existing.home_possession = fm.home_possession
                    existing.away_possession = fm.away_possession
                    existing.home_fouls = fm.home_fouls
                    existing.away_fouls = fm.away_fouls
                    existing.home_yellow_cards = fm.home_yellow_cards
                    existing.away_yellow_cards = fm.away_yellow_cards
                    existing.home_red_cards = fm.home_red_cards
                    existing.away_red_cards = fm.away_red_cards
                    existing.home_corners = fm.home_corners
                    existing.away_corners = fm.away_corners
                    existing.btts = (hg > 0 and ag > 0) if hg is not None and ag is not None else None
                    existing.over_05 = total_goals > 0 if total_goals is not None else None
                    existing.over_15 = total_goals > 1 if total_goals is not None else None
                    existing.over_25 = total_goals > 2 if total_goals is not None else None
                    existing.over_35 = total_goals > 3 if total_goals is not None else None
                    existing.over_45 = total_goals > 4 if total_goals is not None else None
                    existing.attendance = fm.attendance
                    updated += 1

                    # Create referee match log if referee is assigned
                    if existing.referee_id:
                        _create_referee_log(session, existing)
        else:
            # Create new match
            match_date = None
            if fm.date_unix:
                try:
                    match_date = datetime.utcfromtimestamp(fm.date_unix).date()
                except (ValueError, OSError):
                    continue
            if not match_date:
                continue

            status = "complete" if is_complete else "upcoming"
            hg = fm.homeGoalCount
            ag = fm.awayGoalCount
            total_goals = (hg or 0) + (ag or 0) if hg is not None and ag is not None else None

            match = Match(
                footystats_id=fm.id,
                league_id=league_obj.id,
                home_team_id=home_db_id,
                away_team_id=away_db_id,
                season=league_obj.season,
                game_week=fm.game_week,
                match_date=match_date,
                status=status,
                home_goals=hg,
                away_goals=ag,
                home_xg=fm.home_xg,
                away_xg=fm.away_xg,
                home_shots=fm.home_shots,
                away_shots=fm.away_shots,
                home_shots_on_target=fm.home_shotsOnTarget,
                away_shots_on_target=fm.away_shotsOnTarget,
                home_possession=fm.home_possession,
                away_possession=fm.away_possession,
                home_fouls=fm.home_fouls,
                away_fouls=fm.away_fouls,
                home_yellow_cards=fm.home_yellow_cards,
                away_yellow_cards=fm.away_yellow_cards,
                home_red_cards=fm.home_red_cards,
                away_red_cards=fm.away_red_cards,
                home_corners=fm.home_corners,
                away_corners=fm.away_corners,
                btts=(hg > 0 and ag > 0) if hg is not None and ag is not None else None,
                over_05=total_goals > 0 if total_goals is not None else None,
                over_15=total_goals > 1 if total_goals is not None else None,
                over_25=total_goals > 2 if total_goals is not None else None,
                over_35=total_goals > 3 if total_goals is not None else None,
                over_45=total_goals > 4 if total_goals is not None else None,
                referee_id=referee_fs_to_db.get(fm.referee_id) if fm.referee_id else None,
                stadium=fm.stadium_name,
                attendance=fm.attendance,
                odds_home=fm.odds_ft_1,
                odds_draw=fm.odds_ft_x,
                odds_away=fm.odds_ft_2,
                odds_over25=fm.odds_over25,
                odds_under25=fm.odds_under25,
                odds_btts_yes=fm.odds_btts_yes,
                odds_btts_no=fm.odds_btts_no,
                home_ppg_pre=fm.pre_match_home_ppg or fm.home_ppg,
                away_ppg_pre=fm.pre_match_away_ppg or fm.away_ppg,
                source="footystats",
            )
            session.add(match)
            created += 1

    session.commit()
    logger.info("Today's matches: %d created, %d updated.", created, updated)
    return created + updated


def _create_referee_log(session, match: Match) -> None:
    """Create a referee match log entry for a completed match."""
    existing = session.execute(
        select(RefereeMatchLog).where(
            RefereeMatchLog.referee_id == match.referee_id,
            RefereeMatchLog.match_id == match.id,
        )
    ).scalar_one_or_none()

    if existing:
        return

    total_cards = (
        (match.home_yellow_cards or 0) + (match.away_yellow_cards or 0) +
        (match.home_red_cards or 0) + (match.away_red_cards or 0)
    )
    total_fouls = None
    if match.home_fouls is not None and match.away_fouls is not None:
        total_fouls = match.home_fouls + match.away_fouls

    log = RefereeMatchLog(
        referee_id=match.referee_id,
        match_id=match.id,
        league_id=match.league_id,
        season=match.season,
        match_date=match.match_date,
        home_yellows=match.home_yellow_cards or 0,
        away_yellows=match.away_yellow_cards or 0,
        home_reds=match.home_red_cards or 0,
        away_reds=match.away_red_cards or 0,
        total_cards=total_cards,
        total_fouls=total_fouls,
    )
    session.add(log)


async def _refresh_league_matches(client: FootyStatsClient, session) -> int:
    """Fetch recent matches for all leagues and update completed ones."""
    logger.info("Refreshing league matches...")
    leagues = session.execute(
        select(League).order_by(League.season_year.desc())
    ).scalars().all()

    # Only refresh the most recent season per tier
    latest_by_tier: dict[int, League] = {}
    for lg in leagues:
        if lg.tier not in latest_by_tier:
            latest_by_tier[lg.tier] = lg

    total_updated = 0
    for tier, league_obj in latest_by_tier.items():
        try:
            fs_matches = await client.get_league_matches(league_obj.footystats_id)
            for fm in fs_matches:
                if fm.id and fm.status == "complete":
                    existing = session.execute(
                        select(Match).where(Match.footystats_id == fm.id)
                    ).scalar_one_or_none()
                    if existing and existing.status != "complete":
                        existing.status = "complete"
                        existing.home_goals = fm.homeGoalCount
                        existing.away_goals = fm.awayGoalCount
                        total_updated += 1
            session.commit()
        except Exception as e:
            logger.error("Failed to refresh league %d: %s", league_obj.footystats_id, e)
            session.rollback()

    logger.info("League match refresh: %d matches updated.", total_updated)
    return total_updated


async def run_daily_refresh() -> None:
    """Execute the daily data refresh pipeline."""
    _setup_logging()
    start_time = time.time()
    logger.info("Starting daily refresh at %s", datetime.utcnow().isoformat())

    session = get_sync_session()

    ingestion_log = IngestionLog(
        source="daily_refresh",
        operation="daily_refresh",
        status="running",
        started_at=datetime.utcnow(),
    )
    session.add(ingestion_log)
    session.commit()

    try:
        async with FootyStatsClient() as client:
            todays_count = await _refresh_todays_matches(client, session)
            league_count = await _refresh_league_matches(client, session)

        ingestion_log.status = "success"
        ingestion_log.completed_at = datetime.utcnow()
        ingestion_log.records_updated = todays_count + league_count
        ingestion_log.details = {
            "todays_matches": todays_count,
            "league_updates": league_count,
        }
        session.commit()

        elapsed = time.time() - start_time
        logger.info("Daily refresh complete in %.1fs. Updated %d records.", elapsed, todays_count + league_count)

    except Exception as e:
        logger.exception("Daily refresh failed: %s", e)
        ingestion_log.status = "failure"
        ingestion_log.error_message = str(e)
        ingestion_log.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


async def run_saturday_slate() -> None:
    """
    Saturday-specific job: fetch 3pm KO fixtures, generate model outputs,
    flag high-value opportunities.
    """
    _setup_logging()
    logger.info("Running Saturday slate preparation...")

    session = get_sync_session()

    try:
        async with FootyStatsClient() as client:
            # Refresh today's matches to get the latest fixture data
            await _refresh_todays_matches(client, session)

        # Fetch Saturday 3pm fixtures
        today = date.today()
        saturday_matches = session.execute(
            select(Match).where(
                Match.match_date == today,
                Match.status == "upcoming",
            )
        ).scalars().all()

        logger.info("Saturday slate: %d upcoming fixtures found for %s", len(saturday_matches), today)

        # Model outputs would be generated here by the probability engine
        # (Step 14 builds this)

        for match in saturday_matches:
            logger.info(
                "  Fixture: team %d vs team %d (league %d) | Odds: H=%.2f D=%.2f A=%.2f",
                match.home_team_id, match.away_team_id, match.league_id,
                match.odds_home or 0, match.odds_draw or 0, match.odds_away or 0,
            )

    except Exception as e:
        logger.exception("Saturday slate preparation failed: %s", e)
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Daily data refresh for football quant platform")
    parser.add_argument("--saturday-slate", action="store_true", help="Run Saturday slate preparation")
    args = parser.parse_args()

    if args.saturday_slate:
        asyncio.run(run_saturday_slate())
    else:
        asyncio.run(run_daily_refresh())


if __name__ == "__main__":
    main()
