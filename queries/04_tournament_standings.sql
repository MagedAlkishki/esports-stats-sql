-- Standings table for a single tournament: 3 points for a match win plus
-- 1 bonus point per map won (so a 2-0 sweep outscores a 2-1 grind, the
-- way most league formats reward dominant wins).
--
-- Swap the tournament_id literal below to view a different tournament.
WITH this_tournament AS (
    SELECT match_id, team_a_id, team_b_id, team_a_score, team_b_score
    FROM matches
    WHERE tournament_id = 1
),
per_team AS (
    SELECT team_a_id AS team_id, team_a_score AS maps_won, team_b_score AS maps_lost,
           CASE WHEN team_a_score > team_b_score THEN 1 ELSE 0 END AS match_won
    FROM this_tournament
    UNION ALL
    SELECT team_b_id AS team_id, team_b_score AS maps_won, team_a_score AS maps_lost,
           CASE WHEN team_b_score > team_a_score THEN 1 ELSE 0 END AS match_won
    FROM this_tournament
)
SELECT
    t.name                                             AS team,
    t.region,
    COUNT(*)                                           AS matches_played,
    SUM(pt.match_won)                                  AS match_wins,
    COUNT(*) - SUM(pt.match_won)                        AS match_losses,
    SUM(pt.maps_won)                                   AS maps_won,
    SUM(pt.maps_lost)                                  AS maps_lost,
    SUM(pt.match_won) * 3 + SUM(pt.maps_won)           AS points
FROM per_team pt
JOIN teams t ON t.team_id = pt.team_id
GROUP BY t.team_id, t.name, t.region
ORDER BY points DESC, match_wins DESC, maps_won DESC;
