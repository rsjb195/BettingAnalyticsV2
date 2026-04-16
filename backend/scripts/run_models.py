"""
Run analytics models: team ratings, model outputs, team metrics, referee profiles.

Usage:
    python -m backend.scripts.run_models
    python -m backend.scripts.run_models --ratings-only
"""

import argparse
import logging
import sys
import time
from datetime import date

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.database import get_sync_session, get_sync_engine, Base
from backend.app.models.league import League
from backend.app.models.match import Match
from backend.app.models.team import Team
from backend.app.models.referee import Referee
from backend.app.analytics.probability import calculate_team_ratings, predict_match, generate_model_output, run_model_for_league
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

        # 1. Run Dixon-Coles model for each league (generates model outputs for upcoming)
        total_outputs = 0
        total_ratings = 0
        for league in leagues:
            ratings = calculate_team_ratings(league.id, session)
            if ratings:
                total_ratings += len(ratings)
                logger.info("League %d (%s %s): %d team ratings calculated.",
                           league.id, league.name, league.season, len(ratings))

                # Run model for upcoming matches
                outputs = run_model_for_league(league.id, session)
                total_outputs += outputs

        # 2. Also generate model outputs for ALL recent completed matches
        #    so the dashboard has data to show
        logger.info("=== Generating model outputs for recent completed matches ===")
        recent_matches = session.execute(
            select(Match).where(
                Match.status == "complete",
                Match.home_goals.isnot(None),
            ).order_by(Match.match_date.desc()).limit(500)
        ).scalars().all()

        # Group by league for ratings
        league_ratings_cache = {}
        league_avg_cache = {}
        generated_recent = 0

        for match in recent_matches:
            lid = match.league_id
            if lid not in league_ratings_cache:
                league_ratings_cache[lid] = calculate_team_ratings(lid, session, reference_date=match.match_date)
                # Calculate avg goals
                completed = session.execute(
                    select(Match).where(
                        Match.league_id == lid,
                        Match.status == "complete",
                        Match.home_goals.isnot(None),
                    )
                ).scalars().all()
                if completed:
                    total_goals = sum((m.home_goals + m.away_goals) for m in completed)
                    league_avg_cache[lid] = total_goals / (2 * len(completed))
                else:
                    league_avg_cache[lid] = 1.35

            ratings = league_ratings_cache[lid]
            if not ratings:
                continue

            predictions = predict_match(
                match.home_team_id,
                match.away_team_id,
                ratings,
                league_avg_goals=league_avg_cache[lid],
            )
            if predictions:
                generate_model_output(match, predictions, session)
                generated_recent += 1

        session.commit()
        logger.info("Generated %d model outputs for recent matches.", generated_recent)

        # 3. Calculate team metrics
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

        # 4. Calculate referee profiles
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
            "║  Model Outputs:       %-6d (upcoming) + %-6d (recent)     ║\n"
            "║  Team Metrics:        %-6d                                 ║\n"
            "║  Referee Profiles:    %-6d                                 ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            int(elapsed) // 60, int(elapsed) % 60,
            total_ratings, total_outputs, generated_recent,
            team_metrics_count, ref_count,
        )

    except Exception as e:
        logger.exception("Model run failed: %s", e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_all_models()
