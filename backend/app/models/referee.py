"""
Referee and RefereeMatchLog ORM models.

Two tables:
  - referees: career-aggregate stats, recalculated periodically.
  - referee_match_log: per-match granular record of every game officiated.

The match log is the source of truth; aggregate columns on referees are
derived from it for fast querying.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Referee(Base):
    __tablename__ = "referees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    footystats_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    clean_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    # --- Career aggregates (recalculated from referee_match_log) ---
    total_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_yellows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_yellows_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_reds_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cards_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_fouls_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Home / Away bias ---
    home_yellow_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_yellow_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_bias_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Ratio home_yellows/away_yellows, normalised. >1 = more home cards."
    )

    # --- Penalty data ---
    penalties_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_penalty_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_penalty_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Source ---
    primary_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="footystats"
    )  # footystats / csv

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    match_log = relationship("RefereeMatchLog", back_populates="referee", lazy="noload")
    matches = relationship("Match", back_populates="referee", lazy="noload")
    profiles = relationship("RefereeProfile", back_populates="referee", lazy="noload")

    def __repr__(self) -> str:
        return f"<Referee(id={self.id}, name='{self.name}', matches={self.total_matches})>"


class RefereeMatchLog(Base):
    """Per-match record of a referee's performance. Append-only."""

    __tablename__ = "referee_match_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("referees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    home_yellows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    away_yellows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    home_reds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    away_reds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_fouls: Mapped[int | None] = mapped_column(Integer, nullable=True)

    penalties_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    home_penalties: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    away_penalties: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- Relationships ---
    referee = relationship("Referee", back_populates="match_log")

    __table_args__ = (
        Index("ix_referee_match_log_ref_date", "referee_id", "match_date"),
        Index("ix_referee_match_log_ref_match", "referee_id", "match_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<RefereeMatchLog(referee_id={self.referee_id}, match_id={self.match_id}, cards={self.total_cards})>"
