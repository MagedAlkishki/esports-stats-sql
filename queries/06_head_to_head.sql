-- Head-to-head match record between every pair of teams that has actually
-- played each other, with the most lopsided rivalries first. Each pair is
-- shown once, from the perspective of whichever team name sorts first
-- alphabetically (team_x / team_y) so there's no duplicate reversed row.
SELECT
    CASE WHEN ta.name < tb.name THEN ta.name ELSE tb.name END AS team_x,
    CASE WHEN ta.name < tb.name THEN tb.name ELSE ta.name END AS team_y,
    COUNT(*)                                                   AS matches_played,
    SUM(
        CASE
            WHEN ta.name < tb.name
                THEN CASE WHEN m.team_a_score > m.team_b_score THEN 1 ELSE 0 END
                ELSE CASE WHEN m.team_b_score > m.team_a_score THEN 1 ELSE 0 END
        END
    )                                                           AS team_x_wins,
    SUM(
        CASE
            WHEN ta.name < tb.name
                THEN CASE WHEN m.team_b_score > m.team_a_score THEN 1 ELSE 0 END
                ELSE CASE WHEN m.team_a_score > m.team_b_score THEN 1 ELSE 0 END
        END
    )                                                           AS team_y_wins
FROM matches m
JOIN teams ta ON ta.team_id = m.team_a_id
JOIN teams tb ON tb.team_id = m.team_b_id
GROUP BY team_x, team_y
ORDER BY matches_played DESC, team_x ASC;
