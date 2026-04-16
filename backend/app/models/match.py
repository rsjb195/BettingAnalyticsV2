"""
Match ORM model.

Core table — stores every match (historical and upcoming) with full stats,
pre-match odds, and pre-match team context snapshots. Raw API/CSV payload
is preserved in the `raw_data` JSONB column for audit and reprocessing.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    footystats_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    home_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    away_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    game_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="upcoming", index=True
    )  # complete / upcoming / live / postponed

    # --- Results ---
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals_ht: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Match stats ---
    home_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_possession: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_possession: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_fouls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_fouls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_corners: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Derived booleans ---
    btts: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    over_05: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    over_15: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    over_25: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    over_35: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    over_45: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # --- Context ---
    referee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("referees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stadium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Pre-match odds ---
    odds_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_draw: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_away: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_over25: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_under25: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_btts_yes: Mapped[float | None] = mapped_column(Float, nullable=True)
    odds_btts_no: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Pre-match team context snapshots ---
    home_ppg_pre: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_ppg_pre: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_form_pre: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "WWDLW"
    away_form_pre: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Source tracking ---
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="footystats"
    )  # footystats / csv
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    league = relationship("League", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    referee = relationship("Referee", back_populates="matches")
    model_outputs = relationship("ModelOutput", back_populates="match", lazy="noload")

    __table_args__ = (
        Index("ix_matches_date_league", "match_date", "league_id"),
        Index("ix_matches_season_league", "season", "league_id"),
        Index("ix_matches_home_away_date", "home_team_id", "away_team_id", "match_date", unique=True),
        Index("ix_matches_status_date", "status", "match_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Match(id={self.id}, date={self.match_date}, "
            f"home_id={self.home_team_id}, away_id={self.away_team_id}, "
            f"score={self.home_goals}-{self.away_goals})>"
        )
