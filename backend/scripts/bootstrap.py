"""
Bootstrap script — one-time full data load for the football quant platform.

Discovers English league IDs, loads all historical seasons (min 5), populates
teams, matches, players, referees, and runs initial metric calculations.

Resumable: uses database state to skip already-loaded entities.
Progress: tqdm bars + file and console logging.

Usage:
    python -m backend.scripts.bootstrap
    python -m backend.scripts.bootstrap --dry-run
    python -m backend.scripts.bootstrap --seasons 3
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime

from tqdm import tqdm

from backend.app.config import get_settings
from backend.app.database import Base, get_sync_engine, get_sync_session
from backend.app.ingestion.csv_loader import CsvLoader
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.models.ingestion_log import IngestionLog
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.player import Player
from backend.app.models.referee import Referee, RefereeMatchLog
from backend.app.models.team import Team

# Import all models so Base.metadata is fully populated
import backend.app.models  # noqa: F401

from sqlalchemy import select, func

logger = logging.getLogger("bootstrap")

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


def _setup_logging(log_level: str = "INFO") -> None:
    """Configure logging to both console and file."""
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bootstrap.log", mode="a"),
    ]
    logging.basicConfig(level=getattr(logging, log_level), format=fmt, handlers=handlers)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _ensure_tables(engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    logger.info("Database tables verified/created.")


def _get_existing_footystats_ids(session, model_class) -> set[int]:
    """Return set of footystats_ids already in the table."""
    result = session.execute(
        select(model_class.footystats_id).where(model_class.footystats_id.isnot(None))
    )
    return {row[0] for row in result}


# ---------------------------------------------------------------------------
# Ingestion functions
# ---------------------------------------------------------------------------


async def _load_leagues(
    client: FootyStatsClient, session, max_seasons: int = 5
) -> dict[int, list[int]]:
    """
    Discover and load English league records.

    Returns:
        Dict mapping tier -> list of footystats league IDs (newest first).
    """
    logger.info("=== STEP 1: Discovering English leagues ===")
    english_leagues = await client.discover_english_leagues()
    existing_ids = _get_existing_footystats_ids(session, League)

    tier_league_ids: dict[int, list[int]] = {}
    total_created = 0

    for tier in sorted(english_leagues.keys()):
        seasons = english_leagues[tier][:max_seasons]
        tier_league_ids[tier] = []

        for season_entry in seasons:
            fs_id = season_entry["season_id"]
            tier_league_ids[tier].append(fs_id)

            if fs_id in existing_ids:
                logger.debug("League %d already exists, skipping.", fs_id)
                continue

            league = League(
                footystats_id=fs_id,
                name=season_entry["name"],
                country=season_entry["country"],
                season=str(season_entry["year"]),
                season_year=season_entry["year"],
                tier=tier,
            )
            session.add(league)
            total_created += 1

    session.commit()
    logger.info("Leagues: %d created, %d tiers loaded.", total_created, len(tier_league_ids))
    return tier_league_ids


async def _load_teams(client: FootyStatsClient, session, tier_league_ids: dict) -> int:
    """Load all teams for every discovered league-season."""
    logger.info("=== STEP 2: Loading teams ===")
    existing_ids = _get_existing_footystats_ids(session, Team)
    total_created = 0

    # Build league footystats_id -> db id map
    league_map = {}
    for lg in session.execute(select(League)).scalars().all():
        league_map[lg.footystats_id] = lg.id

    all_league_ids = [lid for ids in tier_league_ids.values() for lid in ids]

    for fs_league_id in tqdm(all_league_ids, desc="Loading teams", unit="league"):
        db_league_id = league_map.get(fs_league_id)
        if db_league_id is None:
            continue

        fs_teams = await client.get_league_teams(fs_league_id)
        league_obj = session.get(League, db_league_id)

        for ft in fs_teams:
            if ft.id in existing_ids:
                continue

            team = Team(
                footystats_id=ft.id,
                name=ft.name or ft.clean_name,
                clean_name=ft.clean_name or ft.name,
                short_name=ft.short_name or "",
                league_id=db_league_id,
                season=league_obj.season if league_obj else "",
                stadium=ft.stadium_name,
                city=ft.city,
            )
            session.add(team)
            existing_ids.add(ft.id)
            total_created += 1

        session.commit()

    logger.info("Teams: %d created.", total_created)
    return total_created


async def _load_matches(client: FootyStatsClient, session, tier_league_ids: dict) -> int:
    """Load all matches for every discovered league-season."""
    logger.info("=== STEP 3: Loading matches ===")
    existing_ids = _get_existing_footystats_ids(session, Match)
    total_created = 0

    # Build lookup maps
    league_map = {}
    for lg in session.execute(select(League)).scalars().all():
        league_map[lg.footystats_id] = lg

    team_fs_to_db = {}
    for t in session.execute(select(Team)).scalars().all():
        team_fs_to_db[t.footystats_id] = t.id

    referee_fs_to_db = {}
    for r in session.execute(select(Referee)).scalars().all():
        if r.footystats_id:
            referee_fs_to_db[r.footystats_id] = r.id

    all_league_ids = [lid for ids in tier_league_ids.values() for lid in ids]

    for fs_league_id in tqdm(all_league_ids, desc="Loading matches", unit="league"):
        league_obj = league_map.get(fs_league_id)
        if league_obj is None:
            continue

        fs_matches = await client.get_league_matches(fs_league_id)
        batch_created = 0

        for fm in fs_matches:
            if fm.id in existing_ids:
                continue

            home_team_db_id = team_fs_to_db.get(fm.homeID)
            away_team_db_id = team_fs_to_db.get(fm.awayID)
            if home_team_db_id is None or away_team_db_id is None:
                continue

            # Parse date from unix timestamp
            match_date = None
            if fm.date_unix:
                try:
                    match_date = datetime.utcfromtimestamp(fm.date_unix).date()
                except (ValueError, OSError):
                    continue
            if match_date is None:
                continue

            is_complete = fm.status == "complete" or (fm.homeGoalCount is not None and fm.awayGoalCount is not None)
            status = "complete" if is_complete else "upcoming"

            hg = fm.homeGoalCount
            ag = fm.awayGoalCount
            total_goals = (hg or 0) + (ag or 0) if hg is not None and ag is not None else None
            btts = (hg > 0 and ag > 0) if hg is not None and ag is not None else None

            referee_db_id = referee_fs_to_db.get(fm.referee_id) if fm.referee_id else None

            match = Match(
                footystats_id=fm.id,
                league_id=league_obj.id,
                home_team_id=home_team_db_id,
                away_team_id=away_team_db_id,
                season=league_obj.season,
                game_week=fm.game_week,
                match_date=match_date,
                status=status,
                home_goals=hg,
                away_goals=ag,
                home_goals_ht=fm.home_goals_ht,
                away_goals_ht=fm.away_goals_ht,
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
                btts=btts,
                over_05=total_goals > 0 if total_goals is not None else None,
                over_15=total_goals > 1 if total_goals is not None else None,
                over_25=total_goals > 2 if total_goals is not None else None,
                over_35=total_goals > 3 if total_goals is not None else None,
                over_45=total_goals > 4 if total_goals is not None else None,
                referee_id=referee_db_id,
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
            existing_ids.add(fm.id)
            batch_created += 1

            # Flush periodically to avoid huge memory buildup
            if batch_created % 200 == 0:
                session.flush()

        session.commit()
        total_created += batch_created
        logger.info("League %d (%s): %d matches loaded.", fs_league_id, league_obj.name, batch_created)

    logger.info("Matches: %d total created.", total_created)
    return total_created


async def _load_players(client: FootyStatsClient, session, tier_league_ids: dict) -> int:
    """Load all players for every discovered league-season."""
    logger.info("=== STEP 4: Loading players ===")
    existing_ids = _get_existing_footystats_ids(session, Player)
    total_created = 0

    league_map = {}
    for lg in session.execute(select(League)).scalars().all():
        league_map[lg.footystats_id] = lg

    team_fs_to_db = {}
    for t in session.execute(select(Team)).scalars().all():
        team_fs_to_db[t.footystats_id] = t.id

    all_league_ids = [lid for ids in tier_league_ids.values() for lid in ids]

    for fs_league_id in tqdm(all_league_ids, desc="Loading players", unit="league"):
        league_obj = league_map.get(fs_league_id)
        if league_obj is None:
            continue

        fs_players = await client.get_league_players(fs_league_id)

        unmatched_teams: set[int | None] = set()
        for fp in fs_players:
            if fp.id in existing_ids:
                continue

            team_db_id = team_fs_to_db.get(fp.team_id)
            if team_db_id is None:
                unmatched_teams.add(fp.team_id)
                continue

            player = Player(
                footystats_id=fp.id,
                name=fp.full_name or fp.known_as,
                clean_name=fp.known_as or fp.full_name,
                team_id=team_db_id,
                league_id=league_obj.id,
                season=league_obj.season,
                position=fp.position or "",
                age=fp.age,
                nationality=fp.nationality or "",
                appearances=fp.appearances_overall,
                minutes_played=fp.minutes_played_overall,
                goals=fp.goals_overall,
                assists=fp.assists_overall,
                yellow_cards=fp.yellow_cards_overall,
                red_cards=fp.red_cards_overall,
                xg=fp.xg,
                xg_per90=fp.xg_per90,
                xa=fp.xa,
                xa_per90=fp.xa_per90,
                shots=fp.shots_overall,
                shots_on_target=fp.shots_on_target_overall,
                shot_conversion_rate=fp.shot_conversion_rate_overall,
                passes_per90=fp.passes_per90_overall,
                aerial_duels_won=fp.aerial_duels_won,
                aerial_duels_won_pct=fp.aerial_duels_won_percentage,
                rating=fp.rating,
                xg_per90_percentile=fp.xg_per90_percentile,
                rating_percentile=fp.rating_percentile,
                aerial_won_per90_percentile=fp.aerial_won_per90_percentile,
            )
            session.add(player)
            existing_ids.add(fp.id)
            total_created += 1

        if unmatched_teams:
            logger.warning(
                "League %d: %d players skipped — team IDs not in DB: %s",
                fs_league_id, len(unmatched_teams),
                sorted(t for t in unmatched_teams if t is not None)[:10],
            )
        session.commit()

    logger.info("Players: %d created.", total_created)
    return total_created


async def _load_referees(client: FootyStatsClient, session, tier_league_ids: dict) -> int:
    """Load all referees for every discovered league-season."""
    logger.info("=== STEP 5: Loading referees ===")
    existing_ids = _get_existing_footystats_ids(session, Referee)
    total_created = 0

    league_map = {}
    for lg in session.execute(select(League)).scalars().all():
        league_map[lg.footystats_id] = lg

    all_league_ids = [lid for ids in tier_league_ids.values() for lid in ids]

    for fs_league_id in tqdm(all_league_ids, desc="Loading referees", unit="league"):
        league_obj = league_map.get(fs_league_id)
        if league_obj is None:
            continue

        fs_referees = await client.get_league_referees(fs_league_id)

        for fr in fs_referees:
            if fr.id in existing_ids:
                continue

            ref = Referee(
                footystats_id=fr.id,
                name=fr.name or fr.clean_name,
                clean_name=fr.clean_name or fr.name,
                total_matches=fr.total_matches or 0,
                total_yellows=fr.total_yellows or 0,
                total_reds=fr.total_reds or 0,
                avg_yellows_per_match=fr.avg_yellows,
                avg_reds_per_match=fr.avg_reds,
                avg_cards_per_match=fr.avg_cards,
                avg_fouls_per_match=fr.avg_fouls,
                home_yellow_rate=fr.home_yellow_rate,
                away_yellow_rate=fr.away_yellow_rate,
                penalties_per_match=fr.penalties_per_match,
                home_penalty_rate=fr.home_penalty_rate,
                away_penalty_rate=fr.away_penalty_rate,
                primary_source="footystats",
            )
            session.add(ref)
            existing_ids.add(fr.id)
            total_created += 1

        session.commit()

    logger.info("Referees: %d created.", total_created)
    return total_created


def _build_referee_match_logs(session) -> int:
    """
    Build referee_match_log entries from completed matches that have referee assignments.

    Scans all complete matches with a referee_id and creates log entries
    where they don't already exist.
    """
    logger.info("=== STEP 6: Building referee match logs ===")

    existing_pairs = set()
    for row in session.execute(select(RefereeMatchLog.referee_id, RefereeMatchLog.match_id)):
        existing_pairs.add((row[0], row[1]))

    matches = session.execute(
        select(Match).where(
            Match.status == "complete",
            Match.referee_id.isnot(None),
        )
    ).scalars().all()

    created = 0
    for m in tqdm(matches, desc="Building referee logs", unit="match"):
        if (m.referee_id, m.id) in existing_pairs:
            continue

        total_cards = (
            (m.home_yellow_cards or 0) + (m.away_yellow_cards or 0) +
            (m.home_red_cards or 0) + (m.away_red_cards or 0)
        )
        total_fouls = None
        if m.home_fouls is not None and m.away_fouls is not None:
            total_fouls = m.home_fouls + m.away_fouls

        log = RefereeMatchLog(
            referee_id=m.referee_id,
            match_id=m.id,
            league_id=m.league_id,
            season=m.season,
            match_date=m.match_date,
            home_yellows=m.home_yellow_cards or 0,
            away_yellows=m.away_yellow_cards or 0,
            home_reds=m.home_red_cards or 0,
            away_reds=m.away_red_cards or 0,
            total_cards=total_cards,
            total_fouls=total_fouls,
        )
        session.add(log)
        created += 1

        if created % 500 == 0:
            session.flush()

    session.commit()
    logger.info("Referee match logs: %d created.", created)
    return created


def _load_csvs(session) -> dict:
    """Process all CSV files from the data directory."""
    logger.info("=== STEP 7: Loading CSV data ===")
    loader = CsvLoader(session)
    results = loader.load_all()
    return {
        "files_processed": len(results),
        "total_created": sum(r.get("created", 0) for r in results),
        "total_skipped": sum(r.get("skipped", 0) for r in results),
        "total_errors": sum(r.get("errors", 0) for r in results),
    }


def _print_final_report(session, start_time: float) -> None:
    """Print a summary of all data in the database."""
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    counts = {}
    for name, model in [
        ("leagues", League),
        ("teams", Team),
        ("matches", Match),
        ("players", Player),
        ("referees", Referee),
        ("referee_match_logs", RefereeMatchLog),
    ]:
        result = session.execute(select(func.count()).select_from(model))
        counts[name] = result.scalar()

    complete_matches = session.execute(
        select(func.count()).select_from(Match).where(Match.status == "complete")
    ).scalar()
    upcoming_matches = session.execute(
        select(func.count()).select_from(Match).where(Match.status == "upcoming")
    ).scalar()

    report = f"""
╔══════════════════════════════════════════════════════════════╗
║              BOOTSTRAP COMPLETE — FINAL REPORT              ║
╠══════════════════════════════════════════════════════════════╣
║  Duration:            {minutes}m {seconds}s{' ' * (36 - len(f'{minutes}m {seconds}s'))}║
╠══════════════════════════════════════════════════════════════╣
║  Leagues:             {counts['leagues']:<39}║
║  Teams:               {counts['teams']:<39}║
║  Matches (total):     {counts['matches']:<39}║
║    ├─ Complete:       {complete_matches:<39}║
║    └─ Upcoming:       {upcoming_matches:<39}║
║  Players:             {counts['players']:<39}║
║  Referees:            {counts['referees']:<39}║
║  Referee Match Logs:  {counts['referee_match_logs']:<39}║
╚══════════════════════════════════════════════════════════════╝
"""
    logger.info(report)
    print(report)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_bootstrap(dry_run: bool = False, max_seasons: int = 5) -> None:
    """
    Execute the full bootstrap pipeline.

    Args:
        dry_run: If True, log what would be fetched without hitting the API.
        max_seasons: Maximum number of seasons per league to load.
    """
    import os
    os.makedirs("logs", exist_ok=True)

    settings = get_settings()
    _setup_logging(settings.log_level)

    start_time = time.time()
    logger.info("Starting bootstrap (dry_run=%s, max_seasons=%d)", dry_run, max_seasons)

    # Create tables
    engine = get_sync_engine()
    _ensure_tables(engine)
    session = get_sync_session()

    # Log ingestion start
    ingestion_log = IngestionLog(
        source="bootstrap",
        operation="full_bootstrap",
        status="running",
        started_at=datetime.utcnow(),
    )
    session.add(ingestion_log)
    session.commit()

    try:
        async with FootyStatsClient(dry_run=dry_run) as client:
            # Step 1: Discover and load leagues
            tier_league_ids = await _load_leagues(client, session, max_seasons)

            # Step 2: Load teams
            teams_created = await _load_teams(client, session, tier_league_ids)

            # Step 3: Load referees (before matches, so we can link)
            referees_created = await _load_referees(client, session, tier_league_ids)

            # Step 4: Load matches
            matches_created = await _load_matches(client, session, tier_league_ids)

            # Step 5: Load players
            players_created = await _load_players(client, session, tier_league_ids)

            # Step 6: Build referee match logs
            ref_logs_created = _build_referee_match_logs(session)

            # Step 7: Process CSVs
            csv_stats = _load_csvs(session)

        # Update ingestion log
        ingestion_log.status = "success"
        ingestion_log.completed_at = datetime.utcnow()
        ingestion_log.records_created = (
            teams_created + matches_created + players_created + referees_created + ref_logs_created
        )
        ingestion_log.details = {
            "teams": teams_created,
            "matches": matches_created,
            "players": players_created,
            "referees": referees_created,
            "referee_logs": ref_logs_created,
            "csv": csv_stats,
            "api_requests": 0,  # Will be set by client
        }
        session.commit()

        _print_final_report(session, start_time)

    except Exception as e:
        logger.exception("Bootstrap failed: %s", e)
        ingestion_log.status = "failure"
        ingestion_log.error_message = str(e)
        ingestion_log.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Bootstrap the football quant database")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be fetched without hitting API")
    parser.add_argument("--seasons", type=int, default=5, help="Max seasons per league to load (default: 5)")
    args = parser.parse_args()

    asyncio.run(run_bootstrap(dry_run=args.dry_run, max_seasons=args.seasons))


if __name__ == "__main__":
    main()
