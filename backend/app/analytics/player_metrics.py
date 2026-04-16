"""
Player metrics module.

Placeholder for advanced player-level analytics. Currently the platform
ingests player stats directly from FootyStats. This module provides
utility functions for player data access and filtering.
"""

import logging

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.app.models.player import Player

logger = logging.getLogger("analytics.player_metrics")


def get_top_scorers(league_id: int, session: Session, limit: int = 20) -> list[dict]:
    """Return top scorers for a league."""
    players = session.execute(
        select(Player)
        .where(Player.league_id == league_id)
        .order_by(desc(Player.goals))
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": p.id,
            "name": p.clean_name or p.name,
            "team_id": p.team_id,
            "goals": p.goals,
            "xg": p.xg,
            "xg_per90": p.xg_per90,
            "appearances": p.appearances,
        }
        for p in players
    ]


def get_top_assists(league_id: int, session: Session, limit: int = 20) -> list[dict]:
    """Return top assist providers for a league."""
    players = session.execute(
        select(Player)
        .where(Player.league_id == league_id)
        .order_by(desc(Player.assists))
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": p.id,
            "name": p.clean_name or p.name,
            "team_id": p.team_id,
            "assists": p.assists,
            "xa": p.xa,
            "xa_per90": p.xa_per90,
            "appearances": p.appearances,
        }
        for p in players
    ]


def get_highest_rated(league_id: int, session: Session, limit: int = 20) -> list[dict]:
    """Return highest rated players for a league."""
    players = session.execute(
        select(Player)
        .where(Player.league_id == league_id, Player.appearances >= 5)
        .order_by(desc(Player.rating))
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": p.id,
            "name": p.clean_name or p.name,
            "team_id": p.team_id,
            "rating": p.rating,
            "position": p.position,
            "appearances": p.appearances,
            "goals": p.goals,
            "assists": p.assists,
        }
        for p in players
    ]
