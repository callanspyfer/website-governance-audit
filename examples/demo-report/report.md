# Website governance audit: www.maplewood-demo-cu.test

Generated 2026-11-24 19:36 UTC. Source: XML sitemap.

## Summary

- Pages audited: **11**
- Pages with no issues: **1**
- Issues found: **20**

| Severity | Issues |
| --- | ---: |
| Critical | 3 |
| High | 7 |
| Medium | 7 |
| Low | 3 |

## What to fix first

Ordered by severity, then by how many pages are affected.

| # | Severity | Issue | Pages | Fix |
| ---: | --- | --- | ---: | --- |
| 1 | Critical | Internal links to pages that return an error | 1 | Update the link to a live URL or remove it. |
| 2 | Critical | Page returns an error status | 1 | Restore the page, redirect it to the closest live equivalent, or remove it from the sitemap and from internal links. |
| 3 | Critical | Sitemap lists a noindex page | 1 | Remove the noindex directive if the page should rank. Otherwise remove the URL from the sitemap. |
| 4 | High | Title tag is shared with another page | 2 | Give each page a title that describes that page only. |
| 5 | High | Canonical tag points to a different URL | 1 | Confirm that is intended. If this page should rank on its own, make the canonical self-referencing. |
| 6 | High | Images without an alt attribute | 1 | Describe each informative image in its alt attribute. Use an empty alt (alt="") for decorative images. |
| 7 | High | JSON-LD does not parse | 1 | Fix the JSON syntax. Trailing commas and unescaped quotes are the usual causes. |
| 8 | High | No lang attribute on the html element | 1 | Add the language to the html element in the page template, for example lang="en". |
| 9 | High | Links with no text | 1 | Add link text, alt text on the linked image, or an aria-label. |
| 10 | Medium | No canonical tag | 1 | Add a self-referencing canonical link element to the page template. |
| 11 | Medium | More than one H1 heading | 1 | Keep one H1 and demote the others to H2 or lower. |
| 12 | Medium | Structured data is missing an expected property | 1 | Add the missing property to the JSON-LD block. |
| 13 | Medium | Links with generic text | 1 | Rewrite the link text to name the destination, for example "Auto loan rates". |
| 14 | Medium | Missing meta description | 1 | Write a one or two sentence summary that states what the visitor can do on the page. |
| 15 | Medium | No internal links point to this page | 1 | Link to it from a relevant parent page or the navigation, or retire it. |
| 16 | Medium | Reading level is above the target | 1 | Shorten sentences, swap jargon for everyday words, and lead with the answer. |
| 17 | Low | Heading levels are skipped | 1 | Use heading levels in order and style them with CSS. |
| 18 | Low | No structured data | 1 | Add JSON-LD that fits the page type, such as Organization, Article, FAQPage, or BreadcrumbList. |
| 19 | Low | Very little body text | 1 | Expand the page, merge it into a stronger page, or mark it noindex if it is only a utility page. |

## Findings

### Internal links to pages that return an error

**Critical** · Links · `BROKEN_INTERNAL_LINK` · 1 page(s)

Why it matters: Readers hit a dead end and the destination page receives no link value.

- `/blog/first-time-home-buyer-guide/`: https://www.maplewood-demo-cu.test/blog/2019-rate-update/ (HTTP 404)

### Page returns an error status

**Critical** · Indexation · `HTTP_ERROR` · 1 page(s)

Why it matters: Visitors and crawlers hit a dead end. If the URL is in the sitemap, the sitemap is sending search engines to a page that does not exist.

- `/branches/`: HTTP 404

### Sitemap lists a noindex page

**Critical** · Indexation · `NOINDEX_IN_SITEMAP` · 1 page(s)

Why it matters: The sitemap asks search engines to index the page and the page itself says not to. The page stays out of search results.

- `/rates/`: meta robots: "noindex, nofollow"

### Title tag is shared with another page

**High** · Metadata · `TITLE_DUPLICATE` · 2 page(s)

Why it matters: Pages with the same title compete with each other and are hard to tell apart in search results, tabs, and analytics reports.

- `/checking/`: "Free Checking Accounts | Maplewood Demo Credit Union" is also used on https://www.maplewood-demo-cu.test/savings/
- `/savings/`: "Free Checking Accounts | Maplewood Demo Credit Union" is also used on https://www.maplewood-demo-cu.test/checking/

### Canonical tag points to a different URL

**High** · Indexation · `CANONICAL_MISMATCH` · 1 page(s)

Why it matters: The page tells search engines that another URL is the real version, so this URL is unlikely to be indexed.

- `/checking/student/`: Canonical is https://www.maplewood-demo-cu.test/checking/

### Images without an alt attribute

**High** · Accessibility · `IMG_ALT_MISSING` · 1 page(s)

Why it matters: Screen readers fall back to reading the file name. This is WCAG success criterion 1.1.1 (Level A).

- `/loans/auto/`: 1 of 2 images

### JSON-LD does not parse

**High** · Structured data · `JSONLD_INVALID` · 1 page(s)

Why it matters: A syntax error makes the whole block unreadable, so none of the markup in it counts.

- `/about/`: line 7, column 25: Illegal trailing comma before end of object

### No lang attribute on the html element

**High** · Accessibility · `LANG_MISSING` · 1 page(s)

Why it matters: Screen readers use the page language to choose pronunciation rules. This is WCAG success criterion 3.1.1 (Level A).

- `/about/`

### Links with no text

**High** · Accessibility · `LINK_TEXT_EMPTY` · 1 page(s)

Why it matters: A link with no text or label is announced only as "link", so users cannot tell where it goes.

- `/loans/auto/`: 1 link(s): https://www.maplewood-demo-cu.test/loans/mortgage/

### No canonical tag

**Medium** · Indexation · `CANONICAL_MISSING` · 1 page(s)

Why it matters: Without a canonical tag, URL variants (tracking parameters, trailing slashes) can be indexed as duplicates.

- `/blog/first-time-home-buyer-guide/`

### More than one H1 heading

**Medium** · Metadata · `H1_MULTIPLE` · 1 page(s)

Why it matters: Several H1s blur the page topic and usually mean a template is misusing heading tags for styling.

- `/loans/auto/`: 2 H1s: Auto loans | Get pre-approved today

### Structured data is missing an expected property

**Medium** · Structured data · `JSONLD_MISSING_PROPERTY` · 1 page(s)

Why it matters: Incomplete markup gives search engines and AI systems less to work with and can disqualify the page from rich results.

- `/blog/first-time-home-buyer-guide/`: BlogPosting is missing: author, datePublished

### Links with generic text

**Medium** · Accessibility · `LINK_TEXT_GENERIC` · 1 page(s)

Why it matters: Text such as "click here" does not describe the destination when read out of context. See WCAG success criterion 2.4.4.

- `/loans/auto/`: Link text used: "click here"

### Missing meta description

**Medium** · Metadata · `META_DESC_MISSING` · 1 page(s)

Why it matters: Search engines will pick their own snippet, which is often a poor summary of the page.

- `/savings/`

### No internal links point to this page

**Medium** · Links · `ORPHAN_PAGE` · 1 page(s)

Why it matters: A page that nothing links to is hard for visitors and crawlers to find, even if it is in the sitemap.

- `/disclosures/`

### Reading level is above the target

**Medium** · Content · `READING_GRADE_HIGH` · 1 page(s)

Why it matters: Dense text loses readers. Plain language matters most where the stakes are highest: money, health, and legal topics.

- `/loans/mortgage/`: Grade 19.5 against a target of 8 (23.7 words per sentence)

### Heading levels are skipped

**Low** · Accessibility · `HEADING_SKIP` · 1 page(s)

Why it matters: Jumping from H2 to H4 breaks the outline that screen reader users navigate by.

- `/loans/mortgage/`: H2 is followed by H4 ("Private mortgage insurance considerations")

### No structured data

**Low** · Structured data · `JSONLD_NONE` · 1 page(s)

Why it matters: Structured data states plainly who published the page and what it is about.

- `/disclosures/`

### Very little body text

**Low** · Content · `THIN_CONTENT` · 1 page(s)

Why it matters: A page with almost no text rarely answers a question well enough to rank or to be cited.

- `/disclosures/`: 10 words

## Reading level by page

Flesch-Kincaid grade level of the main content. Target: grade 8 or lower.

| Page | Grade | Words per sentence | Words |
| --- | ---: | ---: | ---: |
| `/loans/mortgage/` | 19.5 (above target) | 23.7 | 213 |
| `/checking/student/` | 3.4 | 8.7 | 139 |
| `/checking/` | 3.1 | 7.0 | 133 |
| `/savings/` | 3.1 | 8.3 | 124 |
| `/about/` | 2.6 | 9.0 | 126 |
| `/` | 2.4 | 9.3 | 167 |
| `/blog/first-time-home-buyer-guide/` | 1.6 | 8.7 | 173 |
| `/loans/auto/` | 0.9 | 8.2 | 123 |

## Files

- `pages.csv`: one row per page with every measured field
- `issues.csv`: one row per issue, with the fix
- `audit.sqlite`: the same data as tables (`pages`, `issues`, `checks`) for SQL analysis
