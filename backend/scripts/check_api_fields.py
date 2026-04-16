"""Quick diagnostic to check what fields the FootyStats API actually returns for matches."""
import asyncio
import json
from backend.app.ingestion.footystats_client import FootyStatsClient
from backend.app.database import get_sync_session
from backend.app.models.league import League
from sqlalchemy import select

async def check():
    session = get_sync_session()
    league = session.execute(select(League).limit(1)).scalar_one_or_none()
    if not league:
        print("No leagues found")
        return
    print(f"Using league: {league.name} (fs_id={league.footystats_id})")

    async with FootyStatsClient() as client:
        # Get raw response for one page of matches
        data = await client._request("/league-matches", {"league_id": league.footystats_id, "page": 1})
        if isinstance(data, list) and data:
            match = data[0]
            print(f"\nFirst match keys ({len(match)} fields):")
            for k, v in sorted(match.items()):
                if v is not None and v != "" and v != 0:
                    print(f"  {k} = {v}")

            # Specifically look for odds-related fields
            print("\n--- Odds-related fields ---")
            for k, v in sorted(match.items()):
                if 'odd' in k.lower() or 'prob' in k.lower() or 'line' in k.lower():
                    print(f"  {k} = {v}")
        else:
            print("No match data returned")

    session.close()

asyncio.run(check())
