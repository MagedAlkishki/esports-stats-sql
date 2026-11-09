-- Per-team, per-map win rate (minimum 2 appearances on that map), so you
-- can see each team's strongest and weakest maps rather than just an
-- overall map pick-rate. A team "appears" on a map once per match in
-- which that map was played, win or lose.
WITH appearances AS (
    SELECT mm.match_id, mm.map_name, m.team_a_id AS team_id, mm.winner_team_id
    FROM match_maps mm
    JOIN matches m ON m.match_id = mm.match_id
    UNION ALL
    SELECT mm.match_id, mm.map_name, m.team_b_id AS team_id, mm.winner_team_id
    FROM match_maps mm
    JOIN matches m ON m.match_id = mm.match_id
)
SELECT
    t.name                                                   AS team,
    a.map_name,
    COUNT(*)                                                 AS appearances,
    SUM(CASE WHEN a.winner_team_id = a.team_id THEN 1 ELSE 0 END) AS wins,
    ROUND(
        100.0 * SUM(CASE WHEN a.winner_team_id = a.team_id THEN 1 ELSE 0 END) / COUNT(*), 1
    )                                                         AS win_rate_pct
FROM appearances a
JOIN teams t ON t.team_id = a.team_id
GROUP BY t.team_id, t.name, a.map_name
HAVING COUNT(*) >= 2
ORDER BY win_rate_pct DESC, appearances DESC, team ASC;
