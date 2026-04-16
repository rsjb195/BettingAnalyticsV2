"""
Run analytics models: team ratings, model outputs, team metrics, referee profiles.

Usage:
    python -m backend.scripts.run_models
"""

import logging
import sys
import time
from datetime import date

from sqlalchemy import select

from backend.app.database import get_sync_session, get_sync_engine, Base
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.team import Team
from backend.app.models.referee import Referee
from backend.app.analytics.probability import calculate_team_ratings, predict_match, generate_model_output
from backend.app.analytics.team_metrics import calculate_team_metrics
from backend.app.analytics.referee_engine import calculate_referee_profile

import backend.app.models  # noqa: F401

logger = logging.getLogger("run_models")


def _setup_logging():
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])


def run_all_models():
    _setup_logging()
    start = time.time()
    session = get_sync_session()

    try:
        leagues = session.execute(select(League)).scalars().all()
        logger.info("Found %d leagues in database.", len(leagues))

        # 1. Calculate ratings and generate model outputs per league
        total_ratings = 0
        generated_total = 0

        for league in leagues:
            ratings = calculate_team_ratings(league.id, session)
            if not ratings:
                continue
            total_ratings += len(ratings)
            logger.info("League %d (%s %s): %d team ratings.",
                       league.id, league.name, league.season, len(ratings))

            # Calculate league average goals
            completed = session.execute(
                select(Match).where(
                    Match.league_id == league.id,
                    Match.status == "complete",
                    Match.home_goals.isnot(None),
                )
            ).scalars().all()

            if not completed:
                continue

            total_goals = sum((m.home_goals + m.away_goals) for m in completed)
            avg_goals = total_goals / (2 * len(completed))

            # Generate model outputs for the most recent 100 matches with odds
            with_odds = [m for m in completed if m.odds_home and m.odds_home > 0]
            recent = sorted(with_odds, key=lambda m: m.match_date, reverse=True)[:100]
            league_generated = 0

            for match in recent:
                predictions = predict_match(
                    match.home_team_id,
                    match.away_team_id,
                    ratings,
                    league_avg_goals=avg_goals,
                )
                if predictions:
                    generate_model_output(match, predictions, session)
                    league_generated += 1

            # Flush per league to avoid huge pending batch
            session.commit()
            generated_total += league_generated
            logger.info("  -> %d model outputs generated.", league_generated)

        logger.info("Total model outputs: %d", generated_total)

        # 2. Calculate team metrics
        logger.info("=== Calculating team metrics ===")
        teams = session.execute(select(Team)).scalars().all()
        team_metrics_count = 0
        for team in teams:
            try:
                calculate_team_metrics(team.id, session)
                team_metrics_count += 1
            except Exception as e:
                logger.debug("Team metrics for %d failed: %s", team.id, e)
        session.commit()
        logger.info("Team metrics calculated for %d teams.", team_metrics_count)

        # 3. Calculate referee profiles
        logger.info("=== Calculating referee profiles ===")
        referees = session.execute(select(Referee)).scalars().all()
        ref_count = 0
        for ref in referees:
            try:
                calculate_referee_profile(ref.id, session)
                ref_count += 1
            except Exception as e:
                logger.debug("Referee profile for %d failed: %s", ref.id, e)
        session.commit()
        logger.info("Referee profiles calculated for %d referees.", ref_count)

        elapsed = time.time() - start
        logger.info(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║              MODEL RUN COMPLETE                            ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  Duration:            %dm %ds                              ║\n"
            "║  Team Ratings:        %-6d                                 ║\n"
            "║  Model Outputs:       %-6d                                 ║\n"
            "║  Team Metrics:        %-6d                                 ║\n"
            "║  Referee Profiles:    %-6d                                 ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            int(elapsed) // 60, int(elapsed) % 60,
            total_ratings, generated_total,
            team_metrics_count, ref_count,
        )

    except Exception as e:
        logger.exception("Model run failed: %s", e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_all_models()
