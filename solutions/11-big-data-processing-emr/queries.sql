-- Lab 11 analysis in Athena (workgroup cq-da-11)
SELECT COUNT(*) AS sessions,
       COUNT_IF(converted) AS converted_sessions,
       ROUND(100.0 * COUNT_IF(converted) / COUNT(*), 2) AS conversion_pct,
       ROUND(AVG(duration_s), 1) AS avg_duration_s,
       ROUND(AVG(events), 2) AS avg_events
FROM riverbend_emr.sessions;

SELECT device, COUNT(*) AS sessions,
       ROUND(100.0 * COUNT_IF(converted) / COUNT(*), 2) AS conversion_pct,
       ROUND(AVG(duration_s), 1) AS avg_duration_s
FROM riverbend_emr.sessions
GROUP BY device
ORDER BY conversion_pct DESC;

SELECT dt, COUNT(*) AS sessions FROM riverbend_emr.sessions
WHERE dt IN (DATE '2024-06-01', DATE '2024-06-14', DATE '2024-06-15')
GROUP BY dt ORDER BY dt;

SELECT COUNT(*) AS bounce_sessions FROM riverbend_emr.sessions WHERE events = 1;
