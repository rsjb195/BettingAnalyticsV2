"""
Team ORM model.

Represents a team in a specific league-season. The same club may appear multiple
times across different seasons, each linked to the season's league record.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    footystats_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    clean_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    league_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    stadium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    league = relationship("League", back_populates="teams")
    home_matches = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team", lazy="noload"
    )
    away_matches = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team", lazy="noload"
    )
    players = relationship("Player", back_populates="team", lazy="noload")
    metrics = relationship("TeamMetrics", back_populates="team", lazy="noload")

    __table_args__ = (
        Index("ix_teams_league_season", "league_id", "season"),
        Index("ix_teams_clean_name", "clean_name"),
    )

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}', season='{self.season}')>"
