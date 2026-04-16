# Data Dictionary

Comprehensive reference for every database table and column in the Football Quant Analytics Platform.

## Raw Data Tables

### leagues
One row per league-season combination (e.g. "Premier League 2023/2024").

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| footystats_id | INTEGER | FootyStats unique league-season identifier |
| name | VARCHAR(200) | Full league name |
| country | VARCHAR(100) | Country (always "England" for our scope) |
| season | VARCHAR(20) | Season string, e.g. "2023/2024" |
| season_year | INTEGER | Starting year of the season, e.g. 2023 |
| tier | INTEGER | 1=Premier League, 2=Championship, 3=League One, 4=League Two |
| total_matches | INTEGER | Total scheduled matches in the season |
| matches_played | INTEGER | Matches completed so far |
| created_at | TIMESTAMPTZ | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

### teams
One row per team per league-season.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| footystats_id | INTEGER | FootyStats team ID (unique across all records) |
| name | VARCHAR(200) | Full team name from FootyStats |
| clean_name | VARCHAR(200) | Normalised name for display |
| short_name | VARCHAR(50) | Abbreviated name |
| league_id | INTEGER | FK to leagues.id |
| season | VARCHAR(20) | Season string |
| stadium | VARCHAR(200) | Home stadium name |
| city | VARCHAR(100) | City |

### matches
Core table. One row per match (historical and upcoming).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| footystats_id | INTEGER | FootyStats match ID (nullable for CSV-sourced) |
| league_id | INTEGER | FK to leagues.id |
| home_team_id | INTEGER | FK to teams.id |
| away_team_id | INTEGER | FK to teams.id |
| season | VARCHAR(20) | Season string |
| game_week | INTEGER | Gameweek number |
| match_date | DATE | Match date |
| status | VARCHAR(20) | complete / upcoming / live / postponed |
| home_goals | INTEGER | Full-time home goals (null if upcoming) |
| away_goals | INTEGER | Full-time away goals |
| home_goals_ht | INTEGER | Half-time home goals |
| away_goals_ht | INTEGER | Half-time away goals |
| home_xg | FLOAT | Home expected goals |
| away_xg | FLOAT | Away expected goals |
| home_shots - away_corners | INTEGER | Match event statistics |
| btts | BOOLEAN | Both teams scored |
| over_05 - over_45 | BOOLEAN | Total goals thresholds |
| referee_id | INTEGER | FK to referees.id (nullable) |
| odds_home/draw/away | FLOAT | Pre-match 1X2 odds |
| odds_over25/under25 | FLOAT | Over/under 2.5 odds |
| odds_btts_yes/no | FLOAT | BTTS odds |
| home_ppg_pre | FLOAT | Home team PPG snapshot at time of match |
| away_ppg_pre | FLOAT | Away team PPG snapshot |
| source | VARCHAR(20) | "footystats" or "csv" |
| raw_data | JSONB | Full raw API/CSV payload for audit |

### players
One row per player per league-season.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| footystats_id | INTEGER | FootyStats player ID |
| name | VARCHAR(200) | Full name |
| team_id | INTEGER | FK to teams.id |
| league_id | INTEGER | FK to leagues.id |
| position | VARCHAR(50) | Playing position |
| xg/xg_per90/xa/xa_per90 | FLOAT | Expected contribution metrics |
| *_percentile | FLOAT | Percentile rank within the league |

### referees / referee_match_log
See referee documentation in model_methodology.md.

## Derived Tables

### team_metrics
Point-in-time team performance snapshot. One row per team per gameweek.

### referee_profiles
Point-in-time referee behavioural profile.

### model_outputs
Per-match probability calculations from the Dixon-Coles model.

### accumulator_log
Every accumulator selection built, saved, and settled.
