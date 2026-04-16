# API Reference

Base URL: `http://localhost:8000/api`

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /ticker | Last 20 match results for ticker |
| GET | /performance | P&L tracker data |

## Leagues

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /leagues | List all leagues (filter: tier, season_year) |
| GET | /leagues/{id} | Single league |
| GET | /leagues/{id}/table | Current standings |
| GET | /leagues/{id}/matches | Paginated match list (filter: status) |
| GET | /leagues/{id}/stats | League-level aggregate stats |

## Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /teams | List teams (filter: league_id, season, search) |
| GET | /teams/{id} | Single team profile |
| GET | /teams/{id}/matches | Match history (params: limit, status) |
| GET | /teams/{id}/stats | All raw + derived metrics |
| GET | /teams/{id}/form | Form data for charts (params: last_n) |
| GET | /teams/{id}/players | Squad list with stats |
| GET | /teams/h2h | Head to head (params: home, away) |

## Players

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /players | Paginated list (filter: league_id, team_id, position, search, sort_by) |
| GET | /players/{id} | Full player profile |

## Referees

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /referees | List all (filter: search, min_matches, sort_by) |
| GET | /referees/{id} | Single referee |
| GET | /referees/{id}/profile | Latest calculated profile |
| GET | /referees/{id}/matches | Match log (params: limit) |
| GET | /referees/{id}/impact | Full impact model data |

## Matches

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /matches | Paginated list (filter: league_id, status, date_from, date_to) |
| GET | /matches/{id} | Full match detail with model output |
| GET | /matches/upcoming | Upcoming fixtures (params: days, league_id) |
| GET | /matches/saturday-slate | Saturday 3pm fixtures with model data |
| GET | /matches/model/outputs | Model probability outputs |
| GET | /matches/model/edge | Matches with positive edge (params: min_edge) |

## Accumulator

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /accumulator/build | Auto-build optimal combinations (params: target_odds, min_edge) |
| POST | /accumulator/save | Save an accumulator selection |
| GET | /accumulator/log | History of all accumulators (filter: result) |

## Pagination

All list endpoints support `page` and `per_page` query parameters.
Default: page=1, per_page=50. Maximum per_page: 200.

## Response Format

All responses are JSON. Error responses follow:
```json
{
  "detail": "Error description"
}
```
