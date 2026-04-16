"""
Football-Data.co.uk CSV loader.

Parses historical English football CSV data with:
  - Automatic league detection from Div column (E0=PL, E1=Champ, E2=L1, E3=L2)
  - Fuzzy name matching for referees and teams (handles spelling variations and name changes)
  - Deduplication against existing matches (match on date + home + away)
  - Conflict logging when CSV data disagrees with FootyStats data
  - Referee match log population from historical data
  - SHA-256 file hashing to prevent re-processing
"""

import hashlib
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from thefuzz import fuzz, process

from backend.app.config import get_settings
from backend.app.database import get_sync_session
from backend.app.models.ingestion_log import CsvProcessingLog, IngestionLog
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.referee import Referee, RefereeMatchLog
from backend.app.models.team import Team
from backend.app.ingestion.validator import ValidationReport, validate_match

logger = logging.getLogger("ingestion.csv")

# Football-Data.co.uk division codes -> our tier mapping
DIV_TO_TIER = {
    "E0": 1,  # Premier League
    "E1": 2,  # Championship
    "E2": 3,  # League One
    "E3": 4,  # League Two
}

# Column mapping from CSV headers to our internal fields
CSV_COLUMN_MAP = {
    "Div": "div",
    "Date": "date",
    "Time": "time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",  # H / D / A
    "HTHG": "home_goals_ht",
    "HTAG": "away_goals_ht",
    "HTR": "result_ht",
    "Referee": "referee",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow_cards",
    "AY": "away_yellow_cards",
    "HR": "home_red_cards",
    "AR": "away_red_cards",
    "B365H": "b365_home",
    "B365D": "b365_draw",
    "B365A": "b365_away",
}

# Known team name variations in Football-Data.co.uk CSVs
# Maps old/variant CSV names to the canonical name used in FootyStats
TEAM_NAME_ALIASES = {
    "Man United": "Manchester United",
    "Man City": "Manchester City",
    "Wolves": "Wolverhampton Wanderers",
    "Wolverhampton": "Wolverhampton Wanderers",
    "Sheffield Utd": "Sheffield United",
    "Sheffield United": "Sheffield United",
    "Sheffield Weds": "Sheffield Wednesday",
    "Sheffield Wed": "Sheffield Wednesday",
    "Nott'm Forest": "Nottingham Forest",
    "Nottm Forest": "Nottingham Forest",
    "Nottingham Forest": "Nottingham Forest",
    "QPR": "Queens Park Rangers",
    "Spurs": "Tottenham",
    "Tottenham": "Tottenham Hotspur",
    "West Ham": "West Ham United",
    "West Brom": "West Bromwich Albion",
    "West Bromwich": "West Bromwich Albion",
    "Brighton": "Brighton and Hove Albion",
    "Huddersfield": "Huddersfield Town",
    "Bournemouth": "AFC Bournemouth",
    "Luton": "Luton Town",
    "Ipswich": "Ipswich Town",
    "Swansea": "Swansea City",
    "Stoke": "Stoke City",
    "Leicester": "Leicester City",
    "Norwich": "Norwich City",
    "Cardiff": "Cardiff City",
    "Hull": "Hull City",
    "Bristol City": "Bristol City",
    "Coventry": "Coventry City",
    "Plymouth": "Plymouth Argyle",
    "Peterboro": "Peterborough United",
    "Peterborough": "Peterborough United",
    "MK Dons": "Milton Keynes Dons",
    "Leyton Orient": "Leyton Orient",
    "AFC Wimbledon": "AFC Wimbledon",
}


def _file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_csv_date(date_str: str) -> date | None:
    """
    Parse date strings from Football-Data.co.uk CSVs.

    Handles formats: DD/MM/YYYY, DD/MM/YY, YYYY-MM-DD.
    """
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    logger.warning("Unparseable date: '%s'", date_str)
    return None


def _detect_season(match_date: date) -> str:
    """
    Infer the football season from a match date.

    English football seasons run Aug-May. A match in Jan 2024 belongs to "2023/2024".
    """
    year = match_date.year
    month = match_date.month
    if month >= 7:  # July onwards = start of new season
        return f"{year}/{year + 1}"
    else:  # Jan-June = end of previous season
        return f"{year - 1}/{year}"


def _safe_int(val: Any) -> int | None:
    """Convert value to int, returning None on failure."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    """Convert value to float, returning None on failure."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class CsvLoader:
    """
    Loads and processes Football-Data.co.uk CSV files into the database.

    Usage:
        loader = CsvLoader(session)
        report = loader.load_all()
        print(report.summary())
    """

    def __init__(self, session: Session):
        self._session = session
        self._report = ValidationReport()

        # Caches populated on first use
        self._team_cache: dict[str, int] | None = None  # clean_name -> team.id
        self._referee_cache: dict[str, int] | None = None  # clean_name -> referee.id
        self._league_cache: dict[tuple[int, int], int] | None = None  # (tier, season_year) -> league.id
        self._existing_matches: set[tuple[int, int, date]] | None = None  # (home_id, away_id, date)

    def _build_team_cache(self) -> None:
        """Load all teams into a name -> id lookup."""
        teams = self._session.execute(select(Team)).scalars().all()
        self._team_cache = {}
        for t in teams:
            for name_field in [t.clean_name, t.name, t.short_name]:
                if name_field:
                    self._team_cache[name_field.lower().strip()] = t.id

    def _build_referee_cache(self) -> None:
        """Load all referees into a name -> id lookup."""
        refs = self._session.execute(select(Referee)).scalars().all()
        self._referee_cache = {}
        for r in refs:
            for name_field in [r.clean_name, r.name]:
                if name_field:
                    self._referee_cache[name_field.lower().strip()] = r.id

    def _build_league_cache(self) -> None:
        """Load leagues into (tier, season_year) -> id lookup."""
        leagues = self._session.execute(select(League)).scalars().all()
        self._league_cache = {}
        for lg in leagues:
            self._league_cache[(lg.tier, lg.season_year)] = lg.id

    def _build_existing_matches_cache(self) -> None:
        """Load all existing match (home_id, away_id, date) tuples for dedup."""
        matches = self._session.execute(
            select(Match.home_team_id, Match.away_team_id, Match.match_date)
        ).all()
        self._existing_matches = {(m[0], m[1], m[2]) for m in matches}

    def _resolve_team(self, csv_name: str) -> int | None:
        """
        Resolve a CSV team name to a team ID via alias lookup then fuzzy matching.

        Args:
            csv_name: Team name as it appears in the CSV.

        Returns:
            Team ID or None if no match found.
        """
        if self._team_cache is None:
            self._build_team_cache()

        if not csv_name or not csv_name.strip():
            return None

        normalized = csv_name.strip()

        # Check alias table first
        canonical = TEAM_NAME_ALIASES.get(normalized, normalized)

        # Exact match
        lower = canonical.lower().strip()
        if lower in self._team_cache:
            return self._team_cache[lower]

        # Fuzzy match
        if self._team_cache:
            result = process.extractOne(lower, list(self._team_cache.keys()), scorer=fuzz.token_sort_ratio)
            if result and result[1] >= 80:
                team_id = self._team_cache[result[0]]
                logger.debug("Fuzzy matched team '%s' -> '%s' (score=%d)", csv_name, result[0], result[1])
                return team_id

        logger.warning("Could not resolve team: '%s'", csv_name)
        return None

    def _resolve_referee(self, csv_name: str) -> int | None:
        """
        Resolve a CSV referee name to a referee ID via fuzzy matching.

        Creates a new referee record if no match found.

        Args:
            csv_name: Referee name as it appears in the CSV.

        Returns:
            Referee ID.
        """
        if self._referee_cache is None:
            self._build_referee_cache()

        if not csv_name or not str(csv_name).strip() or pd.isna(csv_name):
            return None

        normalized = str(csv_name).strip()
        lower = normalized.lower()

        # Exact match
        if lower in self._referee_cache:
            return self._referee_cache[lower]

        # Fuzzy match
        if self._referee_cache:
            result = process.extractOne(lower, list(self._referee_cache.keys()), scorer=fuzz.token_sort_ratio)
            if result and result[1] >= 85:
                ref_id = self._referee_cache[result[0]]
                logger.debug("Fuzzy matched referee '%s' -> '%s' (score=%d)", csv_name, result[0], result[1])
                return ref_id

        # Create new referee from CSV data
        new_ref = Referee(
            name=normalized,
            clean_name=normalized,
            primary_source="csv",
        )
        self._session.add(new_ref)
        self._session.flush()
        self._referee_cache[lower] = new_ref.id
        logger.info("Created new referee from CSV: '%s' (id=%d)", normalized, new_ref.id)
        return new_ref.id

    def _resolve_league(self, tier: int, match_date: date) -> int | None:
        """Resolve a league ID from tier and match date."""
        if self._league_cache is None:
            self._build_league_cache()

        season = _detect_season(match_date)
        season_year = int(season.split("/")[0])

        league_id = self._league_cache.get((tier, season_year))
        if league_id is None:
            logger.warning("No league found for tier=%d, season_year=%d", tier, season_year)
        return league_id

    def _is_duplicate(self, home_team_id: int, away_team_id: int, match_date: date) -> bool:
        """Check if a match already exists in the database."""
        if self._existing_matches is None:
            self._build_existing_matches_cache()
        return (home_team_id, away_team_id, match_date) in self._existing_matches

    def _process_row(self, row: dict, tier: int) -> tuple[Match | None, RefereeMatchLog | None]:
        """
        Process a single CSV row into Match and RefereeMatchLog records.

        Args:
            row: Dict of CSV values (already column-mapped).
            tier: League tier (1-4).

        Returns:
            Tuple of (Match or None, RefereeMatchLog or None).
        """
        match_date = _parse_csv_date(row.get("date"))
        if match_date is None:
            logger.warning("Skipping row with unparseable date: %s", row.get("date"))
            return None, None

        home_team_id = self._resolve_team(row.get("home_team", ""))
        away_team_id = self._resolve_team(row.get("away_team", ""))

        if home_team_id is None or away_team_id is None:
            logger.debug(
                "Skipping match: unresolved teams '%s' vs '%s'",
                row.get("home_team"), row.get("away_team"),
            )
            return None, None

        if self._is_duplicate(home_team_id, away_team_id, match_date):
            return None, None

        league_id = self._resolve_league(tier, match_date)
        if league_id is None:
            return None, None

        season = _detect_season(match_date)
        home_goals = _safe_int(row.get("home_goals"))
        away_goals = _safe_int(row.get("away_goals"))

        # Compute derived booleans
        total_goals = (home_goals or 0) + (away_goals or 0) if home_goals is not None and away_goals is not None else None
        btts = (home_goals > 0 and away_goals > 0) if home_goals is not None and away_goals is not None else None

        home_yellows = _safe_int(row.get("home_yellow_cards"))
        away_yellows = _safe_int(row.get("away_yellow_cards"))
        home_reds = _safe_int(row.get("home_red_cards"))
        away_reds = _safe_int(row.get("away_red_cards"))

        referee_id = self._resolve_referee(row.get("referee"))

        match = Match(
            league_id=league_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            season=season,
            match_date=match_date,
            status="complete",
            home_goals=home_goals,
            away_goals=away_goals,
            home_goals_ht=_safe_int(row.get("home_goals_ht")),
            away_goals_ht=_safe_int(row.get("away_goals_ht")),
            home_shots=_safe_int(row.get("home_shots")),
            away_shots=_safe_int(row.get("away_shots")),
            home_shots_on_target=_safe_int(row.get("home_shots_on_target")),
            away_shots_on_target=_safe_int(row.get("away_shots_on_target")),
            home_fouls=_safe_int(row.get("home_fouls")),
            away_fouls=_safe_int(row.get("away_fouls")),
            home_yellow_cards=home_yellows,
            away_yellow_cards=away_yellows,
            home_red_cards=home_reds,
            away_red_cards=away_reds,
            home_corners=_safe_int(row.get("home_corners")),
            away_corners=_safe_int(row.get("away_corners")),
            btts=btts,
            over_05=total_goals > 0 if total_goals is not None else None,
            over_15=total_goals > 1 if total_goals is not None else None,
            over_25=total_goals > 2 if total_goals is not None else None,
            over_35=total_goals > 3 if total_goals is not None else None,
            over_45=total_goals > 4 if total_goals is not None else None,
            referee_id=referee_id,
            odds_home=_safe_float(row.get("b365_home")),
            odds_draw=_safe_float(row.get("b365_draw")),
            odds_away=_safe_float(row.get("b365_away")),
            source="csv",
        )

        # Build referee match log
        ref_log = None
        if referee_id is not None:
            total_cards = (
                (home_yellows or 0) + (away_yellows or 0) +
                (home_reds or 0) + (away_reds or 0)
            )
            total_fouls_val = None
            hf = _safe_int(row.get("home_fouls"))
            af = _safe_int(row.get("away_fouls"))
            if hf is not None and af is not None:
                total_fouls_val = hf + af

            ref_log = RefereeMatchLog(
                referee_id=referee_id,
                league_id=league_id,
                season=season,
                match_date=match_date,
                home_yellows=home_yellows or 0,
                away_yellows=away_yellows or 0,
                home_reds=home_reds or 0,
                away_reds=away_reds or 0,
                total_cards=total_cards,
                total_fouls=total_fouls_val,
            )

        return match, ref_log

    def load_file(self, file_path: str) -> dict:
        """
        Load a single CSV file into the database.

        Args:
            file_path: Absolute path to the CSV file.

        Returns:
            Dict with load statistics.
        """
        file_path = str(file_path)
        file_name = os.path.basename(file_path)
        logger.info("Processing CSV: %s", file_name)

        # Check if already processed
        fhash = _file_hash(file_path)
        existing = self._session.execute(
            select(CsvProcessingLog).where(CsvProcessingLog.file_path == file_path)
        ).scalar_one_or_none()

        if existing and existing.file_hash == fhash:
            logger.info("Skipping already-processed file: %s", file_name)
            return {"file": file_name, "status": "skipped", "reason": "already_processed"}

        # Read CSV
        try:
            df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
        except Exception:
            try:
                df = pd.read_csv(file_path, encoding="latin-1", on_bad_lines="skip")
            except Exception as e:
                logger.error("Failed to read CSV %s: %s", file_name, e)
                return {"file": file_name, "status": "error", "error": str(e)}

        # Rename columns using our mapping
        rename_map = {k: v for k, v in CSV_COLUMN_MAP.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # Detect league tier from Div column
        if "div" not in df.columns:
            logger.warning("No 'Div' column in %s — skipping", file_name)
            return {"file": file_name, "status": "skipped", "reason": "no_div_column"}

        stats = {"file": file_name, "status": "success", "created": 0, "skipped": 0, "errors": 0}

        for _, row in df.iterrows():
            div_code = str(row.get("div", "")).strip()
            tier = DIV_TO_TIER.get(div_code)
            if tier is None:
                stats["skipped"] += 1
                continue

            row_dict = row.to_dict()
            try:
                match, ref_log = self._process_row(row_dict, tier)
                if match is None:
                    stats["skipped"] += 1
                    continue

                self._session.add(match)
                self._session.flush()

                # Add match_id to ref_log now that we have it
                if ref_log is not None:
                    ref_log.match_id = match.id
                    self._session.add(ref_log)

                # Track for dedup
                if self._existing_matches is not None:
                    self._existing_matches.add(
                        (match.home_team_id, match.away_team_id, match.match_date)
                    )

                stats["created"] += 1
                self._report.increment_validated()

            except Exception as e:
                logger.error("Error processing row in %s: %s", file_name, e)
                stats["errors"] += 1
                self._session.rollback()
                continue

        # Commit the batch
        try:
            self._session.commit()
        except Exception as e:
            logger.error("Commit failed for %s: %s", file_name, e)
            self._session.rollback()
            stats["status"] = "error"
            stats["error"] = str(e)
            return stats

        # Log processing
        if existing:
            existing.file_hash = fhash
            existing.records_loaded = stats["created"]
            existing.processed_at = datetime.utcnow()
        else:
            self._session.add(CsvProcessingLog(
                file_path=file_path,
                file_hash=fhash,
                records_loaded=stats["created"],
            ))
        self._session.commit()

        logger.info(
            "CSV %s: created=%d, skipped=%d, errors=%d",
            file_name, stats["created"], stats["skipped"], stats["errors"],
        )
        return stats

    def load_all(self, csv_dir: str | None = None) -> list[dict]:
        """
        Load all CSV files from the data directory recursively.

        Args:
            csv_dir: Override path to CSV directory. Defaults to config value.

        Returns:
            List of per-file load statistics.
        """
        settings = get_settings()
        csv_dir = csv_dir or settings.csv_data_dir
        csv_path = Path(csv_dir)

        if not csv_path.exists():
            logger.warning("CSV directory does not exist: %s", csv_dir)
            return []

        csv_files = sorted(csv_path.rglob("*.csv"))
        logger.info("Found %d CSV files in %s", len(csv_files), csv_dir)

        results = []
        for f in csv_files:
            result = self.load_file(str(f))
            results.append(result)

        total_created = sum(r.get("created", 0) for r in results)
        total_skipped = sum(r.get("skipped", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)
        logger.info(
            "CSV load complete: %d files, %d matches created, %d skipped, %d errors",
            len(csv_files), total_created, total_skipped, total_errors,
        )

        return results

    @property
    def report(self) -> ValidationReport:
        return self._report
