"""
Data validation module for ingested records.

Validates data integrity before writing to the database. Logs validation
failures to allow manual review without blocking the ingestion pipeline.
"""

import logging
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("ingestion.validator")


class ValidationError:
    """Structured validation failure record."""

    def __init__(self, source: str, entity_type: str, entity_id: Any, field: str, message: str):
        self.source = source
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.field = field
        self.message = message
        self.timestamp = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<ValidationError({self.entity_type}:{self.entity_id} {self.field}: {self.message})>"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field": self.field,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationReport:
    """Accumulates validation errors across an ingestion run."""

    def __init__(self):
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self._records_validated = 0

    def add_error(self, error: ValidationError) -> None:
        self.errors.append(error)
        logger.warning("Validation ERROR: %s", error)

    def add_warning(self, error: ValidationError) -> None:
        self.warnings.append(error)
        logger.debug("Validation WARNING: %s", error)

    def increment_validated(self) -> None:
        self._records_validated += 1

    @property
    def records_validated(self) -> int:
        return self._records_validated

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> dict:
        return {
            "records_validated": self._records_validated,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "error_details": [e.to_dict() for e in self.errors[:50]],
        }


def validate_match(data: dict, source: str = "footystats") -> tuple[bool, list[ValidationError]]:
    """
    Validate a match record before database insertion.

    Args:
        data: Dict of match fields.
        source: Data source identifier.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors: list[ValidationError] = []
    entity_id = data.get("footystats_id") or data.get("id")

    # Required fields
    for field in ["home_team_id", "away_team_id", "league_id", "match_date", "season"]:
        if data.get(field) is None:
            errors.append(ValidationError(source, "match", entity_id, field, f"Required field '{field}' is missing"))

    # Date validation
    match_date = data.get("match_date")
    if match_date:
        if isinstance(match_date, str):
            try:
                match_date = date.fromisoformat(match_date)
            except ValueError:
                errors.append(ValidationError(source, "match", entity_id, "match_date", f"Invalid date format: {match_date}"))
        if isinstance(match_date, date) and match_date.year < 1990:
            errors.append(ValidationError(source, "match", entity_id, "match_date", f"Date suspiciously old: {match_date}"))

    # Goal sanity
    for field in ["home_goals", "away_goals"]:
        val = data.get(field)
        if val is not None and (not isinstance(val, int) or val < 0 or val > 30):
            errors.append(ValidationError(source, "match", entity_id, field, f"Goal count out of range: {val}"))

    # Odds sanity
    for field in ["odds_home", "odds_draw", "odds_away"]:
        val = data.get(field)
        if val is not None and (val <= 0 or val > 1000):
            errors.append(ValidationError(source, "match", entity_id, field, f"Odds out of range: {val}"))

    # xG sanity
    for field in ["home_xg", "away_xg"]:
        val = data.get(field)
        if val is not None and (val < 0 or val > 15):
            errors.append(ValidationError(source, "match", entity_id, field, f"xG out of range: {val}"))

    # Same-team check
    if data.get("home_team_id") and data.get("away_team_id"):
        if data["home_team_id"] == data["away_team_id"]:
            errors.append(ValidationError(source, "match", entity_id, "teams", "Home and away team are the same"))

    return len(errors) == 0, errors


def validate_team(data: dict, source: str = "footystats") -> tuple[bool, list[ValidationError]]:
    """Validate a team record."""
    errors: list[ValidationError] = []
    entity_id = data.get("footystats_id") or data.get("id")

    if not data.get("name"):
        errors.append(ValidationError(source, "team", entity_id, "name", "Team name is required"))

    if not data.get("league_id"):
        errors.append(ValidationError(source, "team", entity_id, "league_id", "League ID is required"))

    return len(errors) == 0, errors


def validate_player(data: dict, source: str = "footystats") -> tuple[bool, list[ValidationError]]:
    """Validate a player record."""
    errors: list[ValidationError] = []
    entity_id = data.get("footystats_id") or data.get("id")

    if not data.get("name") and not data.get("full_name"):
        errors.append(ValidationError(source, "player", entity_id, "name", "Player name is required"))

    age = data.get("age")
    if age is not None and (age < 14 or age > 55):
        errors.append(ValidationError(source, "player", entity_id, "age", f"Age out of range: {age}"))

    return len(errors) == 0, errors


def validate_referee(data: dict, source: str = "footystats") -> tuple[bool, list[ValidationError]]:
    """Validate a referee record."""
    errors: list[ValidationError] = []
    entity_id = data.get("footystats_id") or data.get("id")

    if not data.get("name"):
        errors.append(ValidationError(source, "referee", entity_id, "name", "Referee name is required"))

    avg_cards = data.get("avg_cards_per_match")
    if avg_cards is not None and (avg_cards < 0 or avg_cards > 20):
        errors.append(ValidationError(source, "referee", entity_id, "avg_cards_per_match", f"Avg cards out of range: {avg_cards}"))

    return len(errors) == 0, errors
