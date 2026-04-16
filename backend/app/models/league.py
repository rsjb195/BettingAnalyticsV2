"""
League ORM model.

Represents a single league-season combination (e.g. Premier League 2023/24).
FootyStats treats each season of a league as a distinct entity with its own league_id.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    footystats_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="England")
    season: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2023/2024"
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)  # e.g. 2023
    tier: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1=PL, 2=Championship, 3=League One, 4=League Two"
    )
    total_matches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matches_played: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    teams = relationship("Team", back_populates="league", lazy="selectin")
    matches = relationship("Match", back_populates="league", lazy="noload")
    players = relationship("Player", back_populates="league", lazy="noload")

    __table_args__ = (
        Index("ix_leagues_country_season", "country", "season_year"),
        Index("ix_leagues_tier_season", "tier", "season_year"),
    )

    def __repr__(self) -> str:
        return f"<League(id={self.id}, name='{self.name}', season='{self.season}', tier={self.tier})>"
