-- Team win rate (by match, not by map) across all tournaments.
-- A "win" is the team with the higher map-score in a match; since
-- team_a_score <> team_b_score is guaranteed by best-of-N play, every
-- match has exactly one winner.
SELECT
    t.team_id,
    t.name,
    t.region,
    COUNT(*)                                                   AS matches_played,
    SUM(
        CASE
            WHEN (m.team_a_id = t.team_id AND m.team_a_score > m.team_b_score)
              OR (m.team_b_id = t.team_id AND m.team_b_score > m.team_a_score)
            THEN 1 ELSE 0
        END
    )                                                           AS matches_won,
    ROUND(
        100.0 * SUM(
            CASE
                WHEN (m.team_a_id = t.team_id AND m.team_a_score > m.team_b_score)
                  OR (m.team_b_id = t.team_id AND m.team_b_score > m.team_a_score)
                THEN 1 ELSE 0
            END
        ) / COUNT(*), 1
    )                                                           AS win_rate_pct
FROM teams t
JOIN matches m ON t.team_id IN (m.team_a_id, m.team_b_id)
GROUP BY t.team_id, t.name, t.region
ORDER BY win_rate_pct DESC, matches_played DESC;
