-- ============================================================================
-- Football Quant Analytics Platform — PostgreSQL Schema
-- ============================================================================
-- This file is the authoritative DDL reference. The live database is managed
-- by SQLAlchemy ORM models + Alembic migrations. Use this file for:
--   1. Manual review / auditing of table structure
--   2. Fresh database provisioning without Alembic
--   3. Documentation
--
-- Naming conventions:
--   pk_<table>           — primary keys
--   uq_<table>_<col>     — unique constraints
--   fk_<table>_<col>_<ref> — foreign keys
--   ix_<col(s)>          — indexes
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- RAW DATA TABLES (append-only ingestion targets)
-- ============================================================================

CREATE TABLE IF NOT EXISTS leagues (
    id                SERIAL PRIMARY KEY,
    footystats_id     INTEGER NOT NULL UNIQUE,
    name              VARCHAR(200) NOT NULL,
    country           VARCHAR(100) NOT NULL DEFAULT 'England',
    season            VARCHAR(20) NOT NULL,           -- e.g. '2023/2024'
    season_year       INTEGER NOT NULL,               -- e.g. 2023
    tier              INTEGER NOT NULL,               -- 1=PL, 2=Champ, 3=L1, 4=L2
    total_matches     INTEGER,
    matches_played    INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_leagues_footystats_id ON leagues (footystats_id);
CREATE INDEX IF NOT EXISTS ix_leagues_country_season ON leagues (country, season_year);
CREATE INDEX IF NOT EXISTS ix_leagues_tier_season ON leagues (tier, season_year);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teams (
    id                SERIAL PRIMARY KEY,
    footystats_id     INTEGER NOT NULL UNIQUE,
    name              VARCHAR(200) NOT NULL,
    clean_name        VARCHAR(200),
    short_name        VARCHAR(50),
    league_id         INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    season            VARCHAR(20) NOT NULL,
    stadium           VARCHAR(200),
    city              VARCHAR(100),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_teams_footystats_id ON teams (footystats_id);
CREATE INDEX IF NOT EXISTS ix_teams_league_season ON teams (league_id, season);
CREATE INDEX IF NOT EXISTS ix_teams_clean_name ON teams (clean_name);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS referees (
    id                    SERIAL PRIMARY KEY,
    footystats_id         INTEGER UNIQUE,
    name                  VARCHAR(200) NOT NULL,
    clean_name            VARCHAR(200),
    total_matches         INTEGER NOT NULL DEFAULT 0,
    total_yellows         INTEGER NOT NULL DEFAULT 0,
    total_reds            INTEGER NOT NULL DEFAULT 0,
    avg_yellows_per_match FLOAT,
    avg_reds_per_match    FLOAT,
    avg_cards_per_match   FLOAT,
    avg_fouls_per_match   FLOAT,
    home_yellow_rate      FLOAT,
    away_yellow_rate      FLOAT,
    home_bias_score       FLOAT,           -- ratio home_yellows/away_yellows normalised
    penalties_per_match   FLOAT,
    home_penalty_rate     FLOAT,
    away_penalty_rate     FLOAT,
    primary_source        VARCHAR(20) NOT NULL DEFAULT 'footystats',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_referees_footystats_id ON referees (footystats_id);
CREATE INDEX IF NOT EXISTS ix_referees_clean_name ON referees (clean_name);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS matches (
    id                     SERIAL PRIMARY KEY,
    footystats_id          INTEGER UNIQUE,
    league_id              INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    home_team_id           INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id           INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season                 VARCHAR(20) NOT NULL,
    game_week              INTEGER,
    match_date             DATE NOT NULL,
    status                 VARCHAR(20) NOT NULL DEFAULT 'upcoming',

    -- Results
    home_goals             INTEGER,
    away_goals             INTEGER,
    home_goals_ht          INTEGER,
    away_goals_ht          INTEGER,

    -- Match stats
    home_xg                FLOAT,
    away_xg                FLOAT,
    home_shots             INTEGER,
    away_shots             INTEGER,
    home_shots_on_target   INTEGER,
    away_shots_on_target   INTEGER,
    home_possession        FLOAT,
    away_possession        FLOAT,
    home_fouls             INTEGER,
    away_fouls             INTEGER,
    home_yellow_cards      INTEGER,
    away_yellow_cards      INTEGER,
    home_red_cards         INTEGER,
    away_red_cards         INTEGER,
    home_corners           INTEGER,
    away_corners           INTEGER,

    -- Derived booleans
    btts                   BOOLEAN,
    over_05                BOOLEAN,
    over_15                BOOLEAN,
    over_25                BOOLEAN,
    over_35                BOOLEAN,
    over_45                BOOLEAN,

    -- Context
    referee_id             INTEGER REFERENCES referees(id) ON DELETE SET NULL,
    stadium                VARCHAR(200),
    attendance             INTEGER,

    -- Pre-match odds
    odds_home              FLOAT,
    odds_draw              FLOAT,
    odds_away              FLOAT,
    odds_over25            FLOAT,
    odds_under25           FLOAT,
    odds_btts_yes          FLOAT,
    odds_btts_no           FLOAT,

    -- Pre-match team context snapshots
    home_ppg_pre           FLOAT,
    away_ppg_pre           FLOAT,
    home_form_pre          VARCHAR(20),
    away_form_pre          VARCHAR(20),

    -- Source tracking
    source                 VARCHAR(20) NOT NULL DEFAULT 'footystats',
    raw_data               JSONB,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_matches_footystats_id ON matches (footystats_id);
CREATE INDEX IF NOT EXISTS ix_matches_league_id ON matches (league_id);
CREATE INDEX IF NOT EXISTS ix_matches_home_team_id ON matches (home_team_id);
CREATE INDEX IF NOT EXISTS ix_matches_away_team_id ON matches (away_team_id);
CREATE INDEX IF NOT EXISTS ix_matches_match_date ON matches (match_date);
CREATE INDEX IF NOT EXISTS ix_matches_status ON matches (status);
CREATE INDEX IF NOT EXISTS ix_matches_btts ON matches (btts);
CREATE INDEX IF NOT EXISTS ix_matches_over_25 ON matches (over_25);
CREATE INDEX IF NOT EXISTS ix_matches_referee_id ON matches (referee_id);
CREATE INDEX IF NOT EXISTS ix_matches_date_league ON matches (match_date, league_id);
CREATE INDEX IF NOT EXISTS ix_matches_season_league ON matches (season, league_id);
CREATE INDEX IF NOT EXISTS ix_matches_status_date ON matches (status, match_date);
CREATE UNIQUE INDEX IF NOT EXISTS ix_matches_home_away_date ON matches (home_team_id, away_team_id, match_date);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS players (
    id                          SERIAL PRIMARY KEY,
    footystats_id               INTEGER NOT NULL UNIQUE,
    name                        VARCHAR(200) NOT NULL,
    clean_name                  VARCHAR(200),
    team_id                     INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    league_id                   INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    season                      VARCHAR(20) NOT NULL,
    position                    VARCHAR(50),
    age                         INTEGER,
    nationality                 VARCHAR(100),

    -- Performance
    appearances                 INTEGER DEFAULT 0,
    minutes_played              INTEGER DEFAULT 0,
    goals                       INTEGER DEFAULT 0,
    assists                     INTEGER DEFAULT 0,
    yellow_cards                INTEGER DEFAULT 0,
    red_cards                   INTEGER DEFAULT 0,

    -- Advanced
    xg                          FLOAT,
    xg_per90                    FLOAT,
    xa                          FLOAT,
    xa_per90                    FLOAT,
    shots                       INTEGER,
    shots_on_target             INTEGER,
    shot_conversion_rate        FLOAT,
    key_passes                  INTEGER,
    passes_per90                FLOAT,
    aerial_duels_won            INTEGER,
    aerial_duels_won_pct        FLOAT,
    rating                      FLOAT,

    -- Percentile ranks
    xg_per90_percentile         FLOAT,
    rating_percentile           FLOAT,
    aerial_won_per90_percentile FLOAT,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_players_footystats_id ON players (footystats_id);
CREATE INDEX IF NOT EXISTS ix_players_team_id ON players (team_id);
CREATE INDEX IF NOT EXISTS ix_players_league_id ON players (league_id);
CREATE INDEX IF NOT EXISTS ix_players_team_season ON players (team_id, season);
CREATE INDEX IF NOT EXISTS ix_players_league_season ON players (league_id, season);
CREATE INDEX IF NOT EXISTS ix_players_position ON players (position);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS referee_match_log (
    id                  SERIAL PRIMARY KEY,
    referee_id          INTEGER NOT NULL REFERENCES referees(id) ON DELETE CASCADE,
    match_id            INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    league_id           INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    season              VARCHAR(20) NOT NULL,
    match_date          DATE NOT NULL,
    home_yellows        INTEGER NOT NULL DEFAULT 0,
    away_yellows        INTEGER NOT NULL DEFAULT 0,
    home_reds           INTEGER NOT NULL DEFAULT 0,
    away_reds           INTEGER NOT NULL DEFAULT 0,
    total_cards         INTEGER NOT NULL DEFAULT 0,
    total_fouls         INTEGER,
    penalties_awarded   INTEGER NOT NULL DEFAULT 0,
    home_penalties      INTEGER NOT NULL DEFAULT 0,
    away_penalties      INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_referee_match_log_referee_id ON referee_match_log (referee_id);
CREATE INDEX IF NOT EXISTS ix_referee_match_log_match_id ON referee_match_log (match_id);
CREATE INDEX IF NOT EXISTS ix_referee_match_log_league_id ON referee_match_log (league_id);
CREATE INDEX IF NOT EXISTS ix_referee_match_log_match_date ON referee_match_log (match_date);
CREATE INDEX IF NOT EXISTS ix_referee_match_log_ref_date ON referee_match_log (referee_id, match_date);
CREATE UNIQUE INDEX IF NOT EXISTS ix_referee_match_log_ref_match ON referee_match_log (referee_id, match_id);


-- ============================================================================
-- DERIVED / CALCULATED TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS team_metrics (
    id                          SERIAL PRIMARY KEY,
    team_id                     INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    league_id                   INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    season                      VARCHAR(20) NOT NULL,
    calculated_at               TIMESTAMPTZ NOT NULL,
    gameweek                    INTEGER,

    -- Form
    form_last5                  VARCHAR(10),
    form_last10                 VARCHAR(20),
    ppg_last5                   FLOAT,
    ppg_last10                  FLOAT,
    ppg_season                  FLOAT,
    ppg_home                    FLOAT,
    ppg_away                    FLOAT,

    -- xG metrics
    xg_for_avg                  FLOAT,
    xg_against_avg              FLOAT,
    xg_for_home                 FLOAT,
    xg_against_home             FLOAT,
    xg_for_away                 FLOAT,
    xg_against_away             FLOAT,
    xg_overperformance          FLOAT,

    -- Attacking
    goals_scored_avg            FLOAT,
    goals_conceded_avg          FLOAT,
    shots_for_avg               FLOAT,
    shots_against_avg           FLOAT,
    conversion_rate             FLOAT,

    -- Defensive
    clean_sheet_rate            FLOAT,
    clean_sheet_home            FLOAT,
    clean_sheet_away            FLOAT,
    btts_rate                   FLOAT,
    over25_rate                 FLOAT,

    -- Patterns
    first_goal_scored_rate      FLOAT,
    first_goal_conceded_rate    FLOAT,
    win_when_scoring_first      FLOAT,
    lose_when_conceding_first   FLOAT,

    -- Momentum
    momentum_score              FLOAT,
    momentum_direction          VARCHAR(10),

    -- Fatigue
    days_since_last_match       INTEGER,
    matches_last_14_days        INTEGER,
    fatigue_index               FLOAT,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_team_metrics_team_id ON team_metrics (team_id);
CREATE INDEX IF NOT EXISTS ix_team_metrics_league_id ON team_metrics (league_id);
CREATE INDEX IF NOT EXISTS ix_team_metrics_team_season_gw ON team_metrics (team_id, season, gameweek);
CREATE INDEX IF NOT EXISTS ix_team_metrics_team_calc ON team_metrics (team_id, calculated_at);
CREATE INDEX IF NOT EXISTS ix_team_metrics_momentum ON team_metrics (momentum_score);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS referee_profiles (
    id                                 SERIAL PRIMARY KEY,
    referee_id                         INTEGER NOT NULL REFERENCES referees(id) ON DELETE CASCADE,
    calculated_at                      TIMESTAMPTZ NOT NULL,
    cards_per_match_career             FLOAT,
    cards_per_match_l20                FLOAT,
    yellows_per_match_career           FLOAT,
    yellows_per_match_l20              FLOAT,
    home_bias_score                    FLOAT,
    home_bias_direction                VARCHAR(10),
    goals_per_match_when_refereeing    FLOAT,
    over25_rate_when_refereeing        FLOAT,
    penalties_per_match                FLOAT,
    card_volatility_score              FLOAT,
    created_at                         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_referee_profiles_referee_id ON referee_profiles (referee_id);
CREATE INDEX IF NOT EXISTS ix_referee_profiles_ref_calc ON referee_profiles (referee_id, calculated_at);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS accumulator_log (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    slate_date          DATE NOT NULL,
    legs                JSONB NOT NULL,
    target_odds         FLOAT NOT NULL,
    actual_odds         FLOAT NOT NULL,
    our_probability     FLOAT NOT NULL,
    stake               FLOAT NOT NULL DEFAULT 50.0,
    potential_return     FLOAT NOT NULL,
    result              VARCHAR(20) NOT NULL DEFAULT 'pending',
    settled_at          TIMESTAMPTZ,
    actual_return       FLOAT DEFAULT 0.0,
    notes               VARCHAR(1000)
);

CREATE INDEX IF NOT EXISTS ix_accumulator_log_slate_date ON accumulator_log (slate_date);
CREATE INDEX IF NOT EXISTS ix_accumulator_log_result ON accumulator_log (result);
CREATE INDEX IF NOT EXISTS ix_accumulator_log_date_result ON accumulator_log (slate_date, result);

-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_outputs (
    id                  SERIAL PRIMARY KEY,
    match_id            INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    our_home_prob       FLOAT NOT NULL,
    our_draw_prob       FLOAT NOT NULL,
    our_away_prob       FLOAT NOT NULL,
    our_home_odds       FLOAT NOT NULL,
    our_draw_odds       FLOAT NOT NULL,
    our_away_odds       FLOAT NOT NULL,
    market_home_odds    FLOAT,
    market_draw_odds    FLOAT,
    market_away_odds    FLOAT,
    home_edge_pct       FLOAT,
    draw_edge_pct       FLOAT,
    away_edge_pct       FLOAT,
    best_value_outcome  VARCHAR(10),
    confidence_rating   FLOAT,
    model_version       VARCHAR(50) NOT NULL DEFAULT 'dixon_coles_v1'
);

CREATE INDEX IF NOT EXISTS ix_model_outputs_match_id ON model_outputs (match_id);
CREATE INDEX IF NOT EXISTS ix_model_outputs_match_version ON model_outputs (match_id, model_version);
CREATE INDEX IF NOT EXISTS ix_model_outputs_generated ON model_outputs (generated_at);
CREATE INDEX IF NOT EXISTS ix_model_outputs_best_value ON model_outputs (best_value_outcome);

-- ============================================================================
-- UTILITY TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS ingestion_log (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,       -- 'footystats', 'csv', 'bootstrap'
    operation       VARCHAR(100) NOT NULL,      -- 'league_matches', 'csv_load', etc.
    status          VARCHAR(20) NOT NULL,       -- 'success', 'failure', 'partial'
    records_processed INTEGER DEFAULT 0,
    records_created   INTEGER DEFAULT 0,
    records_updated   INTEGER DEFAULT 0,
    records_skipped   INTEGER DEFAULT 0,
    error_message     TEXT,
    details           JSONB,
    started_at        TIMESTAMPTZ NOT NULL,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ingestion_log_source ON ingestion_log (source);
CREATE INDEX IF NOT EXISTS ix_ingestion_log_status ON ingestion_log (status);
CREATE INDEX IF NOT EXISTS ix_ingestion_log_started ON ingestion_log (started_at);

-- Tracks which CSV files have been processed to prevent re-processing
CREATE TABLE IF NOT EXISTS csv_processing_log (
    id              SERIAL PRIMARY KEY,
    file_path       VARCHAR(500) NOT NULL UNIQUE,
    file_hash       VARCHAR(64) NOT NULL,       -- SHA-256 of file content
    records_loaded  INTEGER NOT NULL DEFAULT 0,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_csv_processing_log_path ON csv_processing_log (file_path);
