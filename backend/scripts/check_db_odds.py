"""Check what odds values are actually stored in the database."""
from sqlalchemy import select
from backend.app.database import get_sync_session
from backend.app.models.match import Match
import backend.app.models  # noqa

session = get_sync_session()

# Check a few matches
matches = session.execute(
    select(Match).where(Match.league_id == 1).order_by(Match.match_date.desc()).limit(5)
).scalars().all()

for m in matches:
    print(f"Match {m.id} ({m.match_date}): "
          f"odds_home={m.odds_home!r} odds_draw={m.odds_draw!r} odds_away={m.odds_away!r} "
          f"type={type(m.odds_home).__name__}")

# Count matches with non-null, non-zero odds
from sqlalchemy import func, and_
total = session.execute(select(func.count(Match.id))).scalar()
with_odds = session.execute(
    select(func.count(Match.id)).where(
        Match.odds_home.isnot(None),
        Match.odds_home != 0,
    )
).scalar()
print(f"\nTotal matches: {total}")
print(f"Matches with odds (not null, not 0): {with_odds}")

null_odds = session.execute(
    select(func.count(Match.id)).where(Match.odds_home.is_(None))
).scalar()
zero_odds = session.execute(
    select(func.count(Match.id)).where(Match.odds_home == 0)
).scalar()
print(f"Matches with NULL odds: {null_odds}")
print(f"Matches with 0 odds: {zero_odds}")

session.close()
