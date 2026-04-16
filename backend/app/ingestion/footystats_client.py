"""
FootyStats API async client.

Production-grade client with:
  - Exponential backoff on 429 / 5xx responses
  - Rate limiting (1 req/sec safe default for Serious tier)
  - TTL caching for immutable data (league list, completed matches)
  - Full request/response logging
  - Typed Pydantic response models
  - Automatic pagination
  - Dry-run mode
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, Field

from backend.app.config import get_settings

logger = logging.getLogger("ingestion.footystats")

# ---------------------------------------------------------------------------
# Response models — typed representations of FootyStats API responses
# ---------------------------------------------------------------------------


class FSLeague(BaseModel):
    """FootyStats league record."""
    id: int = Field(..., alias="id")
    name: str = ""
    country: str = ""
    season: str = ""
    season_year: int | None = Field(None, alias="year")
    total_matches: int | None = None
    matches_played: int | None = None
    image: str | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSTeam(BaseModel):
    """FootyStats team record."""
    id: int
    name: str = ""
    clean_name: str = ""
    short_name: str = ""
    stadium_name: str | None = None
    city: str | None = None
    league_id: int | None = None
    season: str = ""
    image: str | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSMatch(BaseModel):
    """FootyStats match record (list-level data)."""
    id: int
    league_id: int | None = None
    homeID: int | None = None
    awayID: int | None = None
    home_name: str = ""
    away_name: str = ""
    season: str = ""
    game_week: int | None = None
    date_unix: int | None = None
    status: str = ""
    homeGoalCount: int | None = None
    awayGoalCount: int | None = None
    home_goals_ht: int | None = Field(None, alias="ht_goals_team_a")
    away_goals_ht: int | None = Field(None, alias="ht_goals_team_b")
    home_xg: float | None = Field(None, alias="team_a_xg")
    away_xg: float | None = Field(None, alias="team_b_xg")
    home_shots: int | None = None
    away_shots: int | None = None
    home_shotsOnTarget: int | None = None
    away_shotsOnTarget: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None
    home_fouls: int | None = None
    away_fouls: int | None = None
    home_yellow_cards: int | None = None
    away_yellow_cards: int | None = None
    home_red_cards: int | None = None
    away_red_cards: int | None = None
    home_corners: int | None = None
    away_corners: int | None = None
    btts_potential: float | None = None
    o25_potential: float | None = None
    referee_id: int | None = None
    stadium_name: str | None = None
    attendance: int | None = None
    odds_ft_1: float | None = None
    odds_ft_x: float | None = None
    odds_ft_2: float | None = None
    odds_over25: float | None = None
    odds_under25: float | None = None
    odds_btts_yes: float | None = None
    odds_btts_no: float | None = None
    home_ppg: float | None = None
    away_ppg: float | None = None
    pre_match_home_ppg: float | None = None
    pre_match_away_ppg: float | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSMatchDetail(FSMatch):
    """FootyStats match detail (single match with H2H and full stats)."""
    h2h: list[dict] | None = None
    scoring_first: dict | None = None
    card_timings: dict | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSPlayer(BaseModel):
    """FootyStats player record."""
    id: int
    full_name: str = ""
    known_as: str = ""
    team_id: int | None = None
    league_id: int | None = None
    season: str = ""
    position: str = ""
    age: int | None = None
    nationality: str = ""
    appearances_overall: int | None = 0
    minutes_played_overall: int | None = 0
    goals_overall: int | None = 0
    assists_overall: int | None = 0
    yellow_cards_overall: int | None = 0
    red_cards_overall: int | None = 0
    xg: float | None = None
    xg_per90: float | None = None
    xa: float | None = None
    xa_per90: float | None = None
    shots_overall: int | None = None
    shots_on_target_overall: int | None = None
    shot_conversion_rate_overall: float | None = None
    key_passes_per90_overall: float | None = None
    passes_per90_overall: float | None = None
    aerial_duels_won: int | None = None
    aerial_duels_won_percentage: float | None = None
    rating: float | None = None
    xg_per90_percentile: float | None = None
    rating_percentile: float | None = None
    aerial_won_per90_percentile: float | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSReferee(BaseModel):
    """FootyStats referee record."""
    id: int
    name: str = ""
    clean_name: str = ""
    total_matches: int | None = 0
    total_yellows: int | None = 0
    total_reds: int | None = 0
    avg_yellows: float | None = None
    avg_reds: float | None = None
    avg_cards: float | None = None
    avg_fouls: float | None = None
    home_yellow_rate: float | None = None
    away_yellow_rate: float | None = None
    penalties_per_match: float | None = None
    home_penalty_rate: float | None = None
    away_penalty_rate: float | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSLeagueTable(BaseModel):
    """FootyStats league table entry."""
    team_id: int | None = None
    team_name: str = ""
    position: int | None = None
    played: int | None = None
    wins: int | None = None
    draws: int | None = None
    losses: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    goal_difference: int | None = None
    points: int | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSBTTSStats(BaseModel):
    """FootyStats BTTS stats for a league."""
    team_id: int | None = None
    team_name: str = ""
    btts_percentage: float | None = None
    btts_count: int | None = None
    matches: int | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSOver25Stats(BaseModel):
    """FootyStats Over 2.5 stats for a league."""
    team_id: int | None = None
    team_name: str = ""
    over25_percentage: float | None = None
    over25_count: int | None = None
    matches: int | None = None

    class Config:
        populate_by_name = True
        extra = "allow"


class FSTeamLastX(BaseModel):
    """FootyStats team last X matches stats."""
    team_id: int | None = None
    team_name: str = ""
    last_matches: list[dict] = []
    stats: dict = {}

    class Config:
        populate_by_name = True
        extra = "allow"


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


class _TTLCache:
    """Simple in-memory TTL cache keyed by request fingerprint."""

    def __init__(self, default_ttl_seconds: int = 86400):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl_seconds

    def _key(self, endpoint: str, params: dict) -> str:
        raw = f"{endpoint}|{sorted(params.items())}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, endpoint: str, params: dict) -> Any | None:
        key = self._key(endpoint, params)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, data = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return data

    def set(self, endpoint: str, params: dict, data: Any, ttl: int | None = None) -> None:
        key = self._key(endpoint, params)
        ttl = ttl or self._default_ttl
        self._store[key] = (time.time() + ttl, data)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FootyStatsClient:
    """
    Async client for the FootyStats (football-data-api.com) API.

    Usage:
        async with FootyStatsClient() as client:
            leagues = await client.get_league_list()

    Features:
        - Exponential backoff on 429 and 5xx
        - Rate limiter: 1 request per second (configurable)
        - Response caching with TTL for immutable data
        - Full request logging (endpoint, status, duration)
        - Dry-run mode (logs but does not hit the API)
    """

    MAX_RETRIES = 5
    BACKOFF_BASE = 2.0
    BACKOFF_MAX = 60.0

    def __init__(self, dry_run: bool = False):
        settings = get_settings()
        self._api_key = settings.footystats_api_key
        self._base_url = settings.footystats_base_url.rstrip("/")
        self._request_delay = settings.footystats_request_delay
        self._dry_run = dry_run
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0.0
        self._cache = _TTLCache(default_ttl_seconds=settings.cache_ttl_hours * 3600)
        self._request_count = 0

    async def __aenter__(self) -> "FootyStatsClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Core request machinery
    # ------------------------------------------------------------------

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            await asyncio.sleep(self._request_delay - elapsed)
        self._last_request_time = time.time()

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        *,
        cache_ttl: int | None = None,
        use_cache: bool = True,
    ) -> dict | list:
        """
        Execute a GET request with retry, rate limiting, caching, and logging.

        Args:
            endpoint: API path (e.g. "/league-list").
            params: Query parameters (key is auto-appended).
            cache_ttl: Override cache TTL in seconds. None = use default.
            use_cache: Whether to check/populate cache for this request.

        Returns:
            Parsed JSON response body (dict or list).

        Raises:
            httpx.HTTPStatusError: On non-retryable 4xx errors.
            RuntimeError: After exhausting all retries.
        """
        if params is None:
            params = {}
        params["key"] = self._api_key

        # Check cache
        if use_cache:
            cached = self._cache.get(endpoint, params)
            if cached is not None:
                logger.debug("Cache HIT for %s", endpoint)
                return cached

        # Dry-run mode
        if self._dry_run:
            logger.info("[DRY RUN] Would request %s with params %s", endpoint, {k: v for k, v in params.items() if k != "key"})
            return {}

        if self._client is None:
            raise RuntimeError("Client not initialised. Use 'async with FootyStatsClient() as client:'")

        last_exc: Exception | None = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            await self._rate_limit()
            start = time.time()
            try:
                response = await self._client.get(endpoint, params=params)
                duration_ms = (time.time() - start) * 1000
                self._request_count += 1

                logger.debug(
                    "API %s %s -> %d (%.0fms) [req #%d]",
                    "GET", endpoint, response.status_code, duration_ms, self._request_count,
                )

                if response.status_code == 429:
                    wait = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                    logger.warning(
                        "Rate limited (429) on %s. Backing off %.1fs (attempt %d/%d)",
                        endpoint, wait, attempt, self.MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    wait = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                    logger.warning(
                        "Server error %d on %s. Backing off %.1fs (attempt %d/%d)",
                        response.status_code, endpoint, wait, attempt, self.MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                # FootyStats wraps most responses in a {"data": [...]} envelope
                if isinstance(data, dict) and "data" in data:
                    result = data["data"]
                else:
                    result = data

                # Populate cache
                if use_cache:
                    self._cache.set(endpoint, params, result, ttl=cache_ttl)

                return result

            except httpx.TimeoutException as exc:
                wait = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                logger.warning(
                    "Timeout on %s. Backing off %.1fs (attempt %d/%d)",
                    endpoint, wait, attempt, self.MAX_RETRIES,
                )
                last_exc = exc
                await asyncio.sleep(wait)
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    logger.error("Client error %d on %s: %s", exc.response.status_code, endpoint, exc.response.text[:500])
                    raise
                last_exc = exc
                wait = min(self.BACKOFF_BASE ** attempt, self.BACKOFF_MAX)
                await asyncio.sleep(wait)
                continue

        raise RuntimeError(
            f"Failed to fetch {endpoint} after {self.MAX_RETRIES} retries. Last error: {last_exc}"
        )

    # ------------------------------------------------------------------
    # Typed API methods
    # ------------------------------------------------------------------

    async def get_league_list(self) -> list[FSLeague]:
        """
        Fetch all available leagues.

        Cached for 24h — league list is quasi-static.

        Returns:
            List of FSLeague objects.
        """
        data = await self._request("/league-list", cache_ttl=86400)
        if not isinstance(data, list):
            logger.error("Unexpected league-list response type: %s", type(data))
            return []
        return [FSLeague(**item) if isinstance(item, dict) else item for item in data]

    async def get_country_list(self) -> list[dict]:
        """Fetch all available countries."""
        data = await self._request("/country-list", cache_ttl=86400)
        return data if isinstance(data, list) else []

    async def get_league_matches(
        self, league_id: int, *, season_id: int | None = None, page: int | None = None
    ) -> list[FSMatch]:
        """
        Fetch all matches for a league (with automatic pagination).

        Args:
            league_id: FootyStats league ID.
            season_id: Optional season filter.
            page: Manual page override. If None, fetches all pages automatically.

        Returns:
            List of FSMatch objects for the league.
        """
        params: dict[str, Any] = {"league_id": league_id}
        if season_id is not None:
            params["season_id"] = season_id

        if page is not None:
            params["page"] = page
            data = await self._request("/league-matches", params)
            if not isinstance(data, list):
                return []
            return [FSMatch(**m) if isinstance(m, dict) else m for m in data]

        # Auto-paginate: fetch pages until we get an empty response
        all_matches: list[FSMatch] = []
        current_page = 1
        while True:
            params["page"] = current_page
            data = await self._request("/league-matches", params, use_cache=False)
            if not isinstance(data, list) or len(data) == 0:
                break
            all_matches.extend(FSMatch(**m) if isinstance(m, dict) else m for m in data)
            logger.info(
                "League %d page %d: fetched %d matches (total so far: %d)",
                league_id, current_page, len(data), len(all_matches),
            )
            current_page += 1

        return all_matches

    async def get_league_teams(self, league_id: int) -> list[FSTeam]:
        """
        Fetch all teams for a league-season.

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSTeam objects.
        """
        data = await self._request("/league-teams", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSTeam(**t) if isinstance(t, dict) else t for t in data]

    async def get_league_players(self, league_id: int) -> list[FSPlayer]:
        """
        Fetch all players for a league-season.

        May return a large dataset (500+ players per league).

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSPlayer objects.
        """
        data = await self._request("/league-players", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSPlayer(**p) if isinstance(p, dict) else p for p in data]

    async def get_league_referees(self, league_id: int) -> list[FSReferee]:
        """
        Fetch all referees for a league-season.

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSReferee objects.
        """
        data = await self._request("/league-referees", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSReferee(**r) if isinstance(r, dict) else r for r in data]

    async def get_league_stats(self, league_id: int) -> dict:
        """Fetch league-level aggregate statistics."""
        data = await self._request("/league-stats", {"league_id": league_id})
        return data if isinstance(data, dict) else {}

    async def get_league_table(self, league_id: int) -> list[FSLeagueTable]:
        """
        Fetch the current league table/standings.

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSLeagueTable entries ordered by position.
        """
        data = await self._request("/league-table", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSLeagueTable(**e) if isinstance(e, dict) else e for e in data]

    async def get_match_details(self, match_id: int) -> FSMatchDetail | None:
        """
        Fetch full match details including H2H and odds.

        Completed matches are cached indefinitely (immutable once final).

        Args:
            match_id: FootyStats match ID.

        Returns:
            FSMatchDetail or None if not found.
        """
        data = await self._request(
            "/match", {"match_id": match_id}, cache_ttl=86400 * 365
        )
        if not data:
            return None
        if isinstance(data, list):
            data = data[0] if data else {}
        return FSMatchDetail(**data) if isinstance(data, dict) else None

    async def get_todays_matches(self) -> list[FSMatch]:
        """Fetch all matches scheduled for today."""
        data = await self._request("/todays-matches", use_cache=False)
        if not isinstance(data, list):
            return []
        return [FSMatch(**m) if isinstance(m, dict) else m for m in data]

    async def get_team_stats(self, team_id: int) -> dict:
        """
        Fetch full statistics for a specific team.

        Args:
            team_id: FootyStats team ID.

        Returns:
            Raw stats dict (structure varies by team).
        """
        data = await self._request("/team", {"team_id": team_id})
        return data if isinstance(data, dict) else {}

    async def get_team_last_x(self, team_id: int) -> FSTeamLastX | None:
        """
        Fetch a team's last X match stats.

        Args:
            team_id: FootyStats team ID.

        Returns:
            FSTeamLastX or None.
        """
        data = await self._request("/team-last-x-stats", {"team_id": team_id})
        if not data:
            return None
        return FSTeamLastX(**data) if isinstance(data, dict) else None

    async def get_player_stats(self, player_id: int) -> dict:
        """
        Fetch detailed stats for a single player.

        Args:
            player_id: FootyStats player ID.

        Returns:
            Raw stats dict.
        """
        data = await self._request("/player-stats", {"player_id": player_id})
        return data if isinstance(data, dict) else {}

    async def get_referee_stats(self, referee_id: int) -> dict:
        """
        Fetch detailed stats for a single referee.

        Args:
            referee_id: FootyStats referee ID.

        Returns:
            Raw stats dict.
        """
        data = await self._request("/referee", {"referee_id": referee_id})
        return data if isinstance(data, dict) else {}

    async def get_btts_stats(self, league_id: int) -> list[FSBTTSStats]:
        """
        Fetch BTTS (Both Teams To Score) statistics for a league.

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSBTTSStats per team.
        """
        data = await self._request("/btts-stats", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSBTTSStats(**s) if isinstance(s, dict) else s for s in data]

    async def get_over25_stats(self, league_id: int) -> list[FSOver25Stats]:
        """
        Fetch Over 2.5 goals statistics for a league.

        Args:
            league_id: FootyStats league ID.

        Returns:
            List of FSOver25Stats per team.
        """
        data = await self._request("/over25-stats", {"league_id": league_id})
        if not isinstance(data, list):
            return []
        return [FSOver25Stats(**s) if isinstance(s, dict) else s for s in data]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def discover_english_leagues(self) -> dict[int, list[FSLeague]]:
        """
        Discover FootyStats league IDs for all 4 English tiers across available seasons.

        Returns:
            Dict mapping tier (1-4) to list of FSLeague objects (one per season).
        """
        all_leagues = await self.get_league_list()
        settings = get_settings()

        tier_keywords = {
            1: ["premier league"],
            2: ["championship", "efl championship"],
            3: ["league one", "efl league one", "league 1"],
            4: ["league two", "efl league two", "league 2"],
        }

        result: dict[int, list[FSLeague]] = {1: [], 2: [], 3: [], 4: []}

        for league in all_leagues:
            if not isinstance(league, FSLeague):
                continue
            if league.country.lower() != "england":
                continue
            league_name_lower = league.name.lower()
            for tier, keywords in tier_keywords.items():
                if any(kw in league_name_lower for kw in keywords):
                    result[tier].append(league)
                    break

        for tier, leagues in result.items():
            result[tier] = sorted(leagues, key=lambda l: l.season_year or 0, reverse=True)
            logger.info(
                "Tier %d (%s): found %d season(s) — %s",
                tier,
                settings.english_league_tiers.get(tier, "?"),
                len(leagues),
                [l.season for l in leagues[:5]],
            )

        return result

    @property
    def request_count(self) -> int:
        """Total API requests made this session."""
        return self._request_count

    @property
    def cache_size(self) -> int:
        """Current number of cached entries."""
        return self._cache.size
