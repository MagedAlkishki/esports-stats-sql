-- Top 10 players by career kill/death ratio, minimum 5 matches played
-- (so a single lucky match doesn't rank someone with 2 games above
-- someone with a long, consistently strong record).
SELECT
    p.gamertag,
    t.name                                            AS team,
    p.role,
    COUNT(*)                                           AS matches_played,
    SUM(pms.kills)                                      AS total_kills,
    SUM(pms.deaths)                                     AS total_deaths,
    SUM(pms.assists)                                    AS total_assists,
    ROUND(1.0 * SUM(pms.kills) / MAX(SUM(pms.deaths), 1), 2) AS kd_ratio
FROM player_match_stats pms
JOIN players p ON p.player_id = pms.player_id
JOIN teams t   ON t.team_id = p.team_id
GROUP BY p.player_id, p.gamertag, t.name, p.role
HAVING COUNT(*) >= 5
ORDER BY kd_ratio DESC, total_kills DESC
LIMIT 10;
