-- Where is the hardest content to read?
-- Only pages long enough to score have a reading_grade.
SELECT
    section,
    COUNT(*)                            AS pages_scored,
    ROUND(AVG(reading_grade), 1)        AS avg_grade,
    MAX(reading_grade)                  AS hardest_page_grade,
    ROUND(AVG(words_per_sentence), 1)   AS avg_words_per_sentence,
    SUM(word_count)                     AS total_words
FROM pages
WHERE reading_grade IS NOT NULL
GROUP BY section
ORDER BY avg_grade DESC;
