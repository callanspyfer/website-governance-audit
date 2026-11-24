-- Which pages need the most work?
-- Critical and high issues are counted separately so one broken page
-- outranks a page with a dozen low-severity notes.
SELECT
    p.url,
    SUM(c.severity = 'critical')  AS critical,
    SUM(c.severity = 'high')      AS high,
    SUM(c.severity = 'medium')    AS medium,
    SUM(c.severity = 'low')       AS low,
    COUNT(*)                      AS total
FROM pages AS p
JOIN issues AS i ON i.url = p.url
JOIN checks AS c ON c.check_id = i.check_id
GROUP BY p.url
ORDER BY critical DESC, high DESC, medium DESC, low DESC, p.url
LIMIT 25;
