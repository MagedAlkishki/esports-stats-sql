-- esports-stats-sql schema
--
-- Models a small competitive-FPS esports league: teams, players, tournaments,
-- best-of-N matches, individual maps within a match, and per-player
-- per-match stat lines. Deliberately normalized (map results and player
-- stats are their own tables, not columns bolted onto `matches`) so that
-- analytical queries have to do real joins and aggregation instead of
-- reading a single flat table.

PRAGMA foreign_keys = ON;

CREATE TABLE teams (
    team_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    region      TEXT NOT NULL CHECK (region IN ('NA', 'EU', 'APAC', 'MENA'))
);

CREATE TABLE players (
    player_id   INTEGER PRIMARY KEY,
    gamertag    TEXT NOT NULL UNIQUE,
    team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    role        TEXT NOT NULL CHECK (role IN ('Entry Fragger', 'Support', 'Anchor', 'Flex', 'IGL'))
);

CREATE TABLE tournaments (
    tournament_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    season        TEXT NOT NULL,
    start_date    TEXT NOT NULL,  -- ISO-8601 (YYYY-MM-DD)
    UNIQUE (name, season)
);

-- A best-of-N match between two teams in a tournament. team_a_score /
-- team_b_score count MAPS won, not rounds -- e.g. a best-of-3 ends 2-0 or
-- 2-1. The individual maps that made up that score live in `match_maps`.
CREATE TABLE matches (
    match_id       INTEGER PRIMARY KEY,
    tournament_id  INTEGER NOT NULL REFERENCES tournaments(tournament_id),
    match_date     TEXT NOT NULL,  -- ISO-8601
    team_a_id      INTEGER NOT NULL REFERENCES teams(team_id),
    team_b_id      INTEGER NOT NULL REFERENCES teams(team_id),
    team_a_score   INTEGER NOT NULL CHECK (team_a_score >= 0),
    team_b_score   INTEGER NOT NULL CHECK (team_b_score >= 0),
    CHECK (team_a_id <> team_b_id)
);

-- One row per map played within a match (a best-of-3 produces 2 or 3 rows).
CREATE TABLE match_maps (
    match_map_id   INTEGER PRIMARY KEY,
    match_id       INTEGER NOT NULL REFERENCES matches(match_id),
    map_order      INTEGER NOT NULL CHECK (map_order >= 1),
    map_name       TEXT NOT NULL,
    winner_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    UNIQUE (match_id, map_order)
);

-- One row per player per match: that player's full-match stat line.
CREATE TABLE player_match_stats (
    stat_id     INTEGER PRIMARY KEY,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    player_id   INTEGER NOT NULL REFERENCES players(player_id),
    kills       INTEGER NOT NULL CHECK (kills >= 0),
    deaths      INTEGER NOT NULL CHECK (deaths >= 0),
    assists     INTEGER NOT NULL CHECK (assists >= 0),
    UNIQUE (match_id, player_id)
);

CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_matches_tournament ON matches(tournament_id);
CREATE INDEX idx_matches_team_a ON matches(team_a_id);
CREATE INDEX idx_matches_team_b ON matches(team_b_id);
CREATE INDEX idx_match_maps_match ON match_maps(match_id);
CREATE INDEX idx_pms_match ON player_match_stats(match_id);
CREATE INDEX idx_pms_player ON player_match_stats(player_id);
