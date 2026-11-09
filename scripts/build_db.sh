#!/usr/bin/env bash
# Builds esports_stats.sqlite from schema.sql + seed.sql so you can open
# it directly in any SQLite browser, or point `sqlite3 esports_stats.sqlite`
# at it and run the query files by hand.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="esports_stats.sqlite"
rm -f "$OUT"
sqlite3 "$OUT" < schema/schema.sql
sqlite3 "$OUT" < seed/seed.sql
echo "Built $OUT"
echo "Try:  sqlite3 -header -column $OUT < queries/01_team_win_rates.sql"
