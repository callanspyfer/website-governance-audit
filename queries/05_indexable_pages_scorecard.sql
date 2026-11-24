-- One row per indexable page: does it have the basics?
-- 1 means yes. Sort puts the least complete pages first.
SELECT
    url,
    title <> ''                              AS has_title,
    meta_description <> ''                   AS has_description,
    canonical = final_url                    AS canonical_is_self,
    h1_count = 1                             AS has_one_h1,
    lang <> ''                               AS has_lang,
    images_missing_alt = 0                   AS all_images_have_alt,
    jsonld_types <> ''                       AS has_structured_data,
    (title <> '') + (meta_description <> '') + (canonical = final_url)
      + (h1_count = 1) + (lang <> '') + (images_missing_alt = 0)
      + (jsonld_types <> '')                 AS score_out_of_7
FROM pages
WHERE indexable = 1
ORDER BY score_out_of_7, url;
