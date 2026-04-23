"""
One-time cleanup: replace -1 sentinel values with NULL in match stats columns.

FootyStats API uses -1 to indicate "data unavailable". These were stored
as-is during bootstrap. This script converts them all to NULL.

Usage:
    python -m backend.scripts.clean_sentinel_values
"""
import logging
import sys
from sqlalchemy import text
from backend.app.database import get_sync_engine
import backend.app.models  # noqa

logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("clean_sentinels")

INT_COLS = [
    "home_shots", "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "home_fouls", "away_fouls",
    "home_yellow_cards", "away_yellow_cards",
    "home_red_cards", "away_red_cards",
    "home_corners", "away_corners",
    "home_goals_ht", "away_goals_ht",
    "attendance",
]

FLOAT_COLS = [
    "home_possession", "away_possession",
    "home_xg", "away_xg",
]


def clean():
    engine = get_sync_engine()
    with engine.begin() as conn:
        total = 0
        for col in INT_COLS:
            result = conn.execute(
                text(f"UPDATE matches SET {col} = NULL WHERE {col} = -1")
            )
            if result.rowcount:
                logger.info("  %-30s  %d rows cleared", col, result.rowcount)
                total += result.rowcount

        for col in FLOAT_COLS:
            result = conn.execute(
                text(f"UPDATE matches SET {col} = NULL WHERE {col} = -1.0")
            )
            if result.rowcount:
                logger.info("  %-30s  %d rows cleared", col, result.rowcount)
                total += result.rowcount

    logger.info("\nDone. %d total -1 values replaced with NULL.", total)


if __name__ == "__main__":
    clean()
