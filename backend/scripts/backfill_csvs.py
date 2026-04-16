"""
Standalone CSV backfill script.

Processes all CSV files in the data directory without running the full bootstrap.
Useful for loading additional historical data after initial setup.

Usage:
    python -m backend.scripts.backfill_csvs
    python -m backend.scripts.backfill_csvs --dir /path/to/csvs
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from backend.app.config import get_settings
from backend.app.database import get_sync_session
from backend.app.ingestion.csv_loader import CsvLoader
from backend.app.models.ingestion_log import IngestionLog

import backend.app.models  # noqa: F401

logger = logging.getLogger("backfill_csvs")


def main():
    parser = argparse.ArgumentParser(description="Backfill database from CSV files")
    parser.add_argument("--dir", type=str, default=None, help="Path to CSV directory")
    args = parser.parse_args()

    import os
    os.makedirs("logs", exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/backfill_csvs.log", mode="a"),
        ],
    )

    start_time = time.time()
    logger.info("Starting CSV backfill...")

    session = get_sync_session()

    ingestion_log = IngestionLog(
        source="csv",
        operation="backfill_csvs",
        status="running",
        started_at=datetime.utcnow(),
    )
    session.add(ingestion_log)
    session.commit()

    try:
        loader = CsvLoader(session)
        results = loader.load_all(csv_dir=args.dir)

        total_created = sum(r.get("created", 0) for r in results)
        total_skipped = sum(r.get("skipped", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)

        ingestion_log.status = "success"
        ingestion_log.completed_at = datetime.utcnow()
        ingestion_log.records_processed = total_created + total_skipped + total_errors
        ingestion_log.records_created = total_created
        ingestion_log.records_skipped = total_skipped
        ingestion_log.details = {"files": len(results), "results": results}
        session.commit()

        elapsed = time.time() - start_time
        logger.info(
            "CSV backfill complete in %.1fs. Created=%d, Skipped=%d, Errors=%d",
            elapsed, total_created, total_skipped, total_errors,
        )

    except Exception as e:
        logger.exception("CSV backfill failed: %s", e)
        ingestion_log.status = "failure"
        ingestion_log.error_message = str(e)
        ingestion_log.completed_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
