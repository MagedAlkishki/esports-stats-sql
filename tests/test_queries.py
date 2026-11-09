"""Correctness tests for esports-stats-sql.

Philosophy: for each analytical query, don't just check "it returns rows
without crashing" -- independently recompute the expected answer straight
from the raw table rows in Python, using different logic than the SQL
query itself, and assert the two agree. That way a bug in the SQL (a bad
join, an off-by-one in a window function, double-counting a map) gets
caught even though the "reference implementation" and the query were
never derived from each other.

Also tests schema-level integrity constraints directly (foreign keys,
CHECK constraints, UNIQUE constraints) by attempting invalid inserts and
asserting they're rejected.

Run with:  python3 tests/test_queries.py
"""
import collections
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fresh_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript((ROOT / "schema" / "schema.sql").read_text())
    conn.executescript((ROOT / "seed" / "seed.sql").read_text())
    return conn


def run_query_file(conn: sqlite3.Connection, filename: str):
    sql = (ROOT / "queries" / filename).read_text()
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


class SchemaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_connection()

    def tearDown(self):
        self.conn.close()

    def test_foreign_keys_are_actually_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO players (player_id, gamertag, team_id, role) "
                "VALUES (9999, 'Ghost', 999999, 'Flex')"
            )

    def test_role_check_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO players (player_id, gamertag, team_id, role) "
                "VALUES (9999, 'Ghost', 1, 'Mid Laner')"
            )

    def test_region_check_constraint(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO teams (team_id, name, region) VALUES (999, 'Rogue Signal', 'LATAM')"
            )

    def test_match_cannot_be_a_team_against_itself(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO matches (match_id, tournament_id, match_date, team_a_id, team_b_id, "
                "team_a_score, team_b_score) VALUES (9999, 1, '2025-01-01', 1, 1, 2, 0)"
            )

    def test_negative_kills_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO player_match_stats (stat_id, match_id, player_id, kills, deaths, assists) "
                "VALUES (99999, 1, 1, -5, 10, 2)"
            )

    def test_duplicate_player_stat_line_for_same_match_rejected(self):
        # player_id 1 already has a stat line for match_id 1 via the seed data.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO player_match_stats (stat_id, match_id, player_id, kills, deaths, assists) "
                "VALUES (99999, 1, 1, 20, 10, 5)"
            )

    def test_tournament_name_season_pair_must_be_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO tournaments (tournament_id, name, season, start_date) "
                "VALUES (999, 'Ember Circuit', '2025 Split 1', '2026-01-01')"
            )

    def test_seed_counts_match_expectations(self):
        # Pins the dataset shape so a future seed regeneration that silently
        # drops rows (or a schema change that breaks a FK mid-load) is caught.
        counts = {
            "teams": 6,
            "players": 30,
            "tournaments": 2,
            "matches": 30,
        }
        for table, expected in counts.items():
            actual = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            self.assertEqual(actual, expected, f"{table} row count")
        # match_maps and player_match_stats depend on random map outcomes,
        # so check structural invariants instead of an exact count.
        map_count = self.conn.execute("SELECT COUNT(*) FROM match_maps").fetchone()[0]
        self.assertGreaterEqual(map_count, 30 * 2)  # at least 2 maps per match
        self.assertLessEqual(map_count, 30 * 3)     # at most 3 (best-of-3)
        stat_count = self.conn.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()[0]
        self.assertEqual(stat_count, 30 * 10)  # 5 players per side * 2 sides per match


class QueryCorrectnessTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_connection()
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def _raw_matches(self):
        return self.conn.execute(
            "SELECT match_id, team_a_id, team_b_id, team_a_score, team_b_score, tournament_id "
            "FROM matches"
        ).fetchall()

    def _raw_teams(self):
        return {r["team_id"]: r["name"] for r in self.conn.execute("SELECT team_id, name FROM teams")}

    def test_team_win_rates(self):
        teams = self._raw_teams()
        matches = self._raw_matches()

        played = collections.Counter()
        won = collections.Counter()
        for m in matches:
            played[m["team_a_id"]] += 1
            played[m["team_b_id"]] += 1
            if m["team_a_score"] > m["team_b_score"]:
                won[m["team_a_id"]] += 1
            else:
                won[m["team_b_id"]] += 1

        expected = {}
        for team_id in teams:
            p, w = played[team_id], won[team_id]
            expected[teams[team_id]] = (p, w, round(100.0 * w / p, 1) if p else 0.0)

        cols, rows = run_query_file(self.conn, "01_team_win_rates.sql")
        idx = {c: i for i, c in enumerate(cols)}
        self.assertEqual(len(rows), len(teams))
        for row in rows:
            name = row[idx["name"]]
            p, w, pct = expected[name]
            self.assertEqual(row[idx["matches_played"]], p, name)
            self.assertEqual(row[idx["matches_won"]], w, name)
            self.assertAlmostEqual(row[idx["win_rate_pct"]], pct, places=1, msg=name)

        # Results must be sorted descending by win_rate_pct.
        pcts = [row[idx["win_rate_pct"]] for row in rows]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_top_fraggers_by_kd(self):
        stats = self.conn.execute(
            "SELECT player_id, kills, deaths FROM player_match_stats"
        ).fetchall()
        gamertags = {
            r["player_id"]: r["gamertag"]
            for r in self.conn.execute("SELECT player_id, gamertag FROM players")
        }

        kills = collections.Counter()
        deaths = collections.Counter()
        matches = collections.Counter()
        for s in stats:
            kills[s["player_id"]] += s["kills"]
            deaths[s["player_id"]] += s["deaths"]
            matches[s["player_id"]] += 1

        eligible = [pid for pid in matches if matches[pid] >= 5]
        expected_best = max(
            eligible, key=lambda pid: (kills[pid] / max(deaths[pid], 1), kills[pid])
        )

        cols, rows = run_query_file(self.conn, "02_top_fraggers_by_kd.sql")
        idx = {c: i for i, c in enumerate(cols)}
        self.assertLessEqual(len(rows), 10)
        self.assertGreater(len(rows), 0)
        top_row = rows[0]
        self.assertEqual(top_row[idx["gamertag"]], gamertags[expected_best])
        expected_kd = round(kills[expected_best] / max(deaths[expected_best], 1), 2)
        self.assertAlmostEqual(top_row[idx["kd_ratio"]], expected_kd, places=2)

        # Every returned player must really have >= 5 matches (the HAVING clause).
        for row in rows:
            self.assertGreaterEqual(row[idx["matches_played"]], 5)

        # Results must be sorted descending by kd_ratio.
        kds = [row[idx["kd_ratio"]] for row in rows]
        self.assertEqual(kds, sorted(kds, reverse=True))

    def test_map_win_rates_appearance_math(self):
        # Independently recompute, for every (team, map) pair, how many
        # times that team played the map and how many times it won, by
        # walking match_maps + matches directly (no SQL reused from the
        # query under test).
        maps = self.conn.execute(
            "SELECT mm.match_id, mm.map_name, mm.winner_team_id, m.team_a_id, m.team_b_id "
            "FROM match_maps mm JOIN matches m ON m.match_id = mm.match_id"
        ).fetchall()
        teams = self._raw_teams()

        appearances = collections.Counter()
        wins = collections.Counter()
        for row in maps:
            for side in (row["team_a_id"], row["team_b_id"]):
                key = (side, row["map_name"])
                appearances[key] += 1
                if row["winner_team_id"] == side:
                    wins[key] += 1

        cols, rows = run_query_file(self.conn, "03_map_win_rates.sql")
        idx = {c: i for i, c in enumerate(cols)}
        name_to_id = {v: k for k, v in teams.items()}

        seen = 0
        for row in rows:
            key = (name_to_id[row[idx["team"]]], row[idx["map_name"]])
            self.assertEqual(row[idx["appearances"]], appearances[key], key)
            self.assertEqual(row[idx["wins"]], wins[key], key)
            self.assertGreaterEqual(appearances[key], 2)  # HAVING clause
            seen += 1
        self.assertGreater(seen, 0)

        # Cross-check total appearance count: every match_maps row
        # contributes exactly 2 appearances (one per side).
        self.assertEqual(sum(appearances.values()), len(maps) * 2)

    def test_tournament_standings_points_formula(self):
        matches = [m for m in self._raw_matches() if m["tournament_id"] == 1]
        teams = self._raw_teams()

        points = collections.Counter()
        match_wins = collections.Counter()
        maps_won = collections.Counter()
        for m in matches:
            points[m["team_a_id"]] += m["team_a_score"]
            points[m["team_b_id"]] += m["team_b_score"]
            maps_won[m["team_a_id"]] += m["team_a_score"]
            maps_won[m["team_b_id"]] += m["team_b_score"]
            if m["team_a_score"] > m["team_b_score"]:
                points[m["team_a_id"]] += 3
                match_wins[m["team_a_id"]] += 1
            else:
                points[m["team_b_id"]] += 3
                match_wins[m["team_b_id"]] += 1

        cols, rows = run_query_file(self.conn, "04_tournament_standings.sql")
        idx = {c: i for i, c in enumerate(cols)}
        name_to_id = {v: k for k, v in teams.items()}

        total_points_seen = 0
        for row in rows:
            tid = name_to_id[row[idx["team"]]]
            self.assertEqual(row[idx["points"]], points[tid], row[idx["team"]])
            self.assertEqual(row[idx["match_wins"]], match_wins[tid], row[idx["team"]])
            self.assertEqual(row[idx["maps_won"]], maps_won[tid], row[idx["team"]])
            total_points_seen += row[idx["points"]]

        # Sanity: standings must be sorted descending by points.
        pts = [row[idx["points"]] for row in rows]
        self.assertEqual(pts, sorted(pts, reverse=True))
        self.assertEqual(len(rows), 6)  # all 6 teams play in every tournament here

    def test_head_to_head_symmetry_and_totals(self):
        matches = self._raw_matches()
        teams = self._raw_teams()

        pair_totals = collections.Counter()
        pair_wins = collections.defaultdict(lambda: collections.Counter())
        for m in matches:
            a, b = teams[m["team_a_id"]], teams[m["team_b_id"]]
            x, y = sorted([a, b])
            pair_totals[(x, y)] += 1
            winner_name = a if m["team_a_score"] > m["team_b_score"] else b
            pair_wins[(x, y)][winner_name] += 1

        cols, rows = run_query_file(self.conn, "06_head_to_head.sql")
        idx = {c: i for i, c in enumerate(cols)}

        seen_pairs = set()
        for row in rows:
            x, y = row[idx["team_x"]], row[idx["team_y"]]
            self.assertLess(x, y, "team_x/team_y should be alphabetically ordered")
            seen_pairs.add((x, y))
            total = row[idx["matches_played"]]
            self.assertEqual(total, pair_totals[(x, y)])
            self.assertEqual(row[idx["team_x_wins"]] + row[idx["team_y_wins"]], total)
            self.assertEqual(row[idx["team_x_wins"]], pair_wins[(x, y)].get(x, 0))
            self.assertEqual(row[idx["team_y_wins"]], pair_wins[(x, y)].get(y, 0))

        self.assertEqual(seen_pairs, set(pair_totals.keys()))

    def test_player_form_matches_manual_recent5_average(self):
        # Pick one player with >= 5 matches and manually recompute their
        # recent-5 average kills by sorting their own rows by match date.
        players_with_enough = self.conn.execute(
            "SELECT player_id FROM player_match_stats GROUP BY player_id HAVING COUNT(*) >= 5 LIMIT 1"
        ).fetchone()
        player_id = players_with_enough["player_id"]

        rows = self.conn.execute(
            "SELECT pms.kills, m.match_date, m.match_id "
            "FROM player_match_stats pms JOIN matches m ON m.match_id = pms.match_id "
            "WHERE pms.player_id = ? ",
            (player_id,),
        ).fetchall()
        rows_sorted = sorted(rows, key=lambda r: (r["match_date"], r["match_id"]), reverse=True)
        recent5 = rows_sorted[:5]
        expected_avg = round(sum(r["kills"] for r in recent5) / len(recent5), 1)

        gamertag = self.conn.execute(
            "SELECT gamertag FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()["gamertag"]

        cols, result_rows = run_query_file(self.conn, "05_player_form_last_5.sql")
        idx = {c: i for i, c in enumerate(cols)}
        match = [r for r in result_rows if r[idx["gamertag"]] == gamertag]
        self.assertEqual(len(match), 1)
        self.assertAlmostEqual(match[0][idx["recent5_avg_kills"]], expected_avg, places=1)


if __name__ == "__main__":
    # Fail loudly (non-zero exit) on any failure, for CI / scripted use.
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]))
    sys.exit(0 if result.wasSuccessful() else 1)
