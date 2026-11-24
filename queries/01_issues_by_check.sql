-- Which problems are most serious and most widespread?
-- This is the "what to fix first" table from the report.
SELECT
    c.severity,
    c.category,
    c.title                AS issue,
    COUNT(DISTINCT i.url)  AS pages_affected,
    COUNT(*)               AS occurrences
FROM issues AS i
JOIN checks AS c ON c.check_id = i.check_id
GROUP BY c.check_id
ORDER BY c.severity_rank, pages_affected DESC, c.title;
