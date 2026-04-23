"""
Settle pending accumulators based on completed match results.

Run this any time after match results are in to resolve pending accas.

Usage:
    python -m backend.scripts.settle_accumulators
"""
import logging
import sys
from datetime import datetime

from sqlalchemy import select

from backend.app.database import get_sync_session
from backend.app.models.accumulator import AccumulatorLog
from backend.app.models.match import Match
import backend.app.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("settle")


def settle():
    session = get_sync_session()
    try:
        pending = session.execute(
            select(AccumulatorLog).where(AccumulatorLog.result == "pending")
        ).scalars().all()

        logger.info("Pending accumulators: %d", len(pending))
        if not pending:
            return

        match_ids = {leg["match_id"] for a in pending for leg in (a.legs or []) if leg.get("match_id")}
        matches = {
            m.id: m
            for m in session.execute(select(Match).where(Match.id.in_(match_ids))).scalars().all()
        }

        settled_wins = 0
        settled_losses = 0
        still_pending = 0
        now = datetime.utcnow()

        for acca in pending:
            legs = acca.legs or []
            leg_results = []
            all_complete = True

            for leg in legs:
                match = matches.get(leg.get("match_id"))
                if match is None or match.status != "complete" or match.home_goals is None:
                    all_complete = False
                    break
                hg, ag = match.home_goals, match.away_goals
                sel = leg.get("selection")
                if sel == "home":
                    leg_results.append(hg > ag)
                elif sel == "away":
                    leg_results.append(ag > hg)
                elif sel == "draw":
                    leg_results.append(hg == ag)
                else:
                    leg_results.append(False)

            if not all_complete:
                still_pending += 1
                logger.info(
                    "  Acca #%d (%s) — still pending (matches not complete)", acca.id, acca.slate_date
                )
                continue

            acca.settled_at = now
            if all(leg_results):
                acca.result = "win"
                acca.actual_return = round(acca.stake * acca.actual_odds, 2)
                settled_wins += 1
                logger.info("  Acca #%d (%s) — WIN @ %.1f → return $%.2f",
                            acca.id, acca.slate_date, acca.actual_odds, acca.actual_return)
            else:
                acca.result = "loss"
                acca.actual_return = 0.0
                settled_losses += 1
                losing = [
                    f"{l['home_team']} v {l['away_team']} ({l['selection']})"
                    for l, r in zip(legs, leg_results) if not r
                ]
                logger.info("  Acca #%d (%s) — LOSS. Failed legs: %s",
                            acca.id, acca.slate_date, "; ".join(losing))

        session.commit()
        logger.info(
            "\n"
            "╔══════════════════════════════════════╗\n"
            "║       ACCUMULATOR SETTLEMENT         ║\n"
            "╠══════════════════════════════════════╣\n"
            "║  Wins:          %-22d║\n"
            "║  Losses:        %-22d║\n"
            "║  Still pending: %-22d║\n"
            "╚══════════════════════════════════════╝",
            settled_wins, settled_losses, still_pending,
        )

    finally:
        session.close()


if __name__ == "__main__":
    settle()
