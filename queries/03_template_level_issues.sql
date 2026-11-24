-- Which issues are probably template problems instead of page problems?
-- An issue that shows up on half or more of the pages in a section is usually
-- fixed once, in the template, not page by page.
WITH section_size AS (
    SELECT section, COUNT(*) AS pages_in_section
    FROM pages
    WHERE status = 200
    GROUP BY section
)
SELECT
    p.section,
    c.title                                                     AS issue,
    COUNT(DISTINCT p.url)                                       AS pages_affected,
    s.pages_in_section,
    ROUND(100.0 * COUNT(DISTINCT p.url) / s.pages_in_section)   AS pct_of_section
FROM issues AS i
JOIN pages  AS p ON p.url = i.url
JOIN checks AS c ON c.check_id = i.check_id
JOIN section_size AS s ON s.section = p.section
GROUP BY p.section, c.check_id
HAVING s.pages_in_section >= 2
   AND COUNT(DISTINCT p.url) * 2 >= s.pages_in_section
ORDER BY pct_of_section DESC, pages_affected DESC, p.section;
