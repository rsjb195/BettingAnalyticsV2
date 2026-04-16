"""
Player ORM model.

Stores per-season player statistics sourced from FootyStats.
Includes both raw counting stats and advanced per-90 / percentile metrics.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    footystats_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    clean_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Performance ---
    appearances: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)

    # --- Advanced ---
    xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_per90: Mapped[float | None] = mapped_column(Float, nullable=True)
    xa: Mapped[float | None] = mapped_column(Float, nullable=True)
    xa_per90: Mapped[float | None] = mapped_column(Float, nullable=True)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shot_conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_passes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passes_per90: Mapped[float | None] = mapped_column(Float, nullable=True)
    aerial_duels_won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aerial_duels_won_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Percentile ranks (from FootyStats) ---
    xg_per90_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    aerial_won_per90_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    team = relationship("Team", back_populates="players")
    league = relationship("League", back_populates="players")

    __table_args__ = (
        Index("ix_players_team_season", "team_id", "season"),
        Index("ix_players_league_season", "league_id", "season"),
        Index("ix_players_position", "position"),
    )

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name='{self.name}', team_id={self.team_id})>"
