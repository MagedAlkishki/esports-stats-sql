-- Each player's average K/D/A over just their most recent 5 matches
-- (by match date), vs. their career average -- a simple "form" read: is
-- this player trending up or down compared to their overall numbers?
WITH ranked AS (
    SELECT
        pms.player_id,
        pms.kills, pms.deaths, pms.assists,
        m.match_date,
        ROW_NUMBER() OVER (
            PARTITION BY pms.player_id
            ORDER BY m.match_date DESC, m.match_id DESC
        ) AS recency_rank
    FROM player_match_stats pms
    JOIN matches m ON m.match_id = pms.match_id
),
recent_form AS (
    SELECT
        player_id,
        COUNT(*)                         AS recent_matches,
        AVG(kills)                       AS recent_avg_kills,
        AVG(deaths)                      AS recent_avg_deaths,
        AVG(assists)                     AS recent_avg_assists
    FROM ranked
    WHERE recency_rank <= 5
    GROUP BY player_id
),
career AS (
    SELECT
        player_id,
        COUNT(*)      AS career_matches,
        AVG(kills)    AS career_avg_kills,
        AVG(deaths)   AS career_avg_deaths
    FROM player_match_stats
    GROUP BY player_id
)
SELECT
    p.gamertag,
    t.name                                   AS team,
    career.career_matches,
    ROUND(career.career_avg_kills, 1)        AS career_avg_kills,
    ROUND(recent_form.recent_avg_kills, 1)   AS recent5_avg_kills,
    ROUND(recent_form.recent_avg_kills - career.career_avg_kills, 1) AS kills_trend
FROM recent_form
JOIN career ON career.player_id = recent_form.player_id
JOIN players p ON p.player_id = recent_form.player_id
JOIN teams t   ON t.team_id = p.team_id
WHERE career.career_matches >= 5
ORDER BY kills_trend DESC;
