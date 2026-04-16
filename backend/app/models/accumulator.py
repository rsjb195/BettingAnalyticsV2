"""
Accumulator log and model output ORM models.

AccumulatorLog: Every accumulator considered, saved, or settled.
ModelOutput: Per-match probability and edge calculations from our model.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class AccumulatorLog(Base):
    """
    Records every accumulator selection — built, saved, and settled.

    The `legs` column is a JSONB array where each element contains:
      {
        "match_id": int,
        "home_team": str,
        "away_team": str,
        "selection": "home" | "draw" | "away",
        "odds": float,
        "our_probability": float,
        "edge_pct": float
      }
    """

    __tablename__ = "accumulator_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    slate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    legs: Mapped[list] = mapped_column(JSONB, nullable=False)
    target_odds: Mapped[float] = mapped_column(Float, nullable=False)
    actual_odds: Mapped[float] = mapped_column(Float, nullable=False)

    our_probability: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Product of individual leg probabilities"
    )
    stake: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    potential_return: Mapped[float] = mapped_column(Float, nullable=False)

    result: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # win / loss / pending / partial
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_return: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)

    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        Index("ix_accumulator_log_result", "result"),
        Index("ix_accumulator_log_date_result", "slate_date", "result"),
    )

    def __repr__(self) -> str:
        return (
            f"<AccumulatorLog(id={self.id}, date={self.slate_date}, "
            f"odds={self.actual_odds}, result={self.result})>"
        )


class ModelOutput(Base):
    """
    Per-match model probabilities and edge calculations.

    One row per match per model run. Allows tracking model version changes
    and re-runs with different parameters.
    """

    __tablename__ = "model_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- Our model probabilities ---
    our_home_prob: Mapped[float] = mapped_column(Float, nullable=False)
    our_draw_prob: Mapped[float] = mapped_column(Float, nullable=False)
    our_away_prob: Mapped[float] = mapped_column(Float, nullable=False)

    # --- Our fair odds (1 / probability) ---
    our_home_odds: Mapped[float] = mapped_column(Float, nullable=False)
    our_draw_odds: Mapped[float] = mapped_column(Float, nullable=False)
    our_away_odds: Mapped[float] = mapped_column(Float, nullable=False)

    # --- Market odds at time of generation ---
    market_home_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_draw_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_away_odds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Edge = our_prob - implied_market_prob ---
    home_edge_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_edge_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_edge_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Best value ---
    best_value_outcome: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="home / draw / away / none"
    )
    confidence_rating: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="1-10 scale based on data quality and model uncertainty"
    )

    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="dixon_coles_v1")

    # --- Relationships ---
    match = relationship("Match", back_populates="model_outputs")

    __table_args__ = (
        Index("ix_model_outputs_match_version", "match_id", "model_version"),
        Index("ix_model_outputs_generated", "generated_at"),
        Index("ix_model_outputs_best_value", "best_value_outcome"),
    )

    def __repr__(self) -> str:
        return (
            f"<ModelOutput(match_id={self.match_id}, "
            f"H={self.our_home_prob:.2f}, D={self.our_draw_prob:.2f}, A={self.our_away_prob:.2f})>"
        )
