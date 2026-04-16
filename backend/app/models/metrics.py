"""
Derived / calculated metric models.

TeamMetrics: Rolling performance metrics recalculated after each gameweek.
RefereeProfile: Rolling referee behavioural profile recalculated periodically.

These tables are write-heavy (recalculated regularly) and read-heavy (served to UI).
Each row is a point-in-time snapshot — we keep history to allow trend analysis.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class TeamMetrics(Base):
    """Point-in-time team performance metrics. One row per team per gameweek."""

    __tablename__ = "team_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gameweek: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Form ---
    form_last5: Mapped[str | None] = mapped_column(String(10), nullable=True)  # e.g. "WWDLW"
    form_last10: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ppg_last5: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppg_last10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppg_season: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppg_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppg_away: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- xG metrics ---
    xg_for_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_against_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_for_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_against_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_for_away: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_against_away: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_overperformance: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="goals_scored - xG. Positive = overperforming."
    )

    # --- Attacking ---
    goals_scored_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    goals_conceded_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    shots_for_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    shots_against_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Defensive ---
    clean_sheet_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    clean_sheet_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    clean_sheet_away: Mapped[float | None] = mapped_column(Float, nullable=True)
    btts_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    over25_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Patterns ---
    first_goal_scored_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_goal_conceded_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_when_scoring_first: Mapped[float | None] = mapped_column(Float, nullable=True)
    lose_when_conceding_first: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Momentum ---
    momentum_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Composite form + xG trend + results momentum. Range 0-100."
    )
    momentum_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="rising / falling / stable"
    )

    # --- Fatigue ---
    days_since_last_match: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matches_last_14_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fatigue_index: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Higher = more fatigued. 0-1 scale."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- Relationships ---
    team = relationship("Team", back_populates="metrics")

    __table_args__ = (
        Index("ix_team_metrics_team_season_gw", "team_id", "season", "gameweek"),
        Index("ix_team_metrics_team_calc", "team_id", "calculated_at"),
        Index("ix_team_metrics_momentum", "momentum_score"),
    )

    def __repr__(self) -> str:
        return f"<TeamMetrics(team_id={self.team_id}, gw={self.gameweek}, momentum={self.momentum_score})>"


class RefereeProfile(Base):
    """Point-in-time referee behavioural profile. Recalculated after each match block."""

    __tablename__ = "referee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("referees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- Core rates (rolling) ---
    cards_per_match_career: Mapped[float | None] = mapped_column(Float, nullable=True)
    cards_per_match_l20: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Last 20 matches rolling average"
    )
    yellows_per_match_career: Mapped[float | None] = mapped_column(Float, nullable=True)
    yellows_per_match_l20: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Bias scores ---
    home_bias_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_bias_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="home_heavy / away_heavy / neutral"
    )

    # --- Game flow impact ---
    goals_per_match_when_refereeing: Mapped[float | None] = mapped_column(Float, nullable=True)
    over25_rate_when_refereeing: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Penalty profile ---
    penalties_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Volatility ---
    card_volatility_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Std dev of cards per match. High = unpredictable."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- Relationships ---
    referee = relationship("Referee", back_populates="profiles")

    __table_args__ = (
        Index("ix_referee_profiles_ref_calc", "referee_id", "calculated_at"),
    )

    def __repr__(self) -> str:
        return f"<RefereeProfile(referee_id={self.referee_id}, cards_l20={self.cards_per_match_l20})>"
