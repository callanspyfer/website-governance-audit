"""The checks.

Every check has an entry in ``CHECKS`` that says how serious it is, why it
matters, and how to fix it. Reports and docs are generated from that registry,
so the rule, the explanation, and the output never drift apart.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlsplit

from .parse import Page

SEVERITIES = ("critical", "high", "medium", "low")


@dataclass(frozen=True)
class Check:
    id: str
    severity: str
    category: str
    title: str
    why: str
    fix: str


@dataclass(frozen=True)
class Issue:
    url: str
    check_id: str
    detail: str = ""

    @property
    def check(self) -> Check:
        return CHECKS[self.check_id]


@dataclass(frozen=True)
class Thresholds:
    grade_target: float = 8.0  # flag pages that read above this grade level
    title_min: int = 15
    title_max: int = 60
    description_min: int = 50
    description_max: int = 160
    thin_words: int = 100


_C = Check
CHECKS: dict[str, Check] = {
    c.id: c
    for c in [
        # Indexation
        _C("HTTP_ERROR", "critical", "Indexation", "Page returns an error status",
           "Visitors and crawlers hit a dead end. If the URL is in the sitemap, the sitemap is sending search engines to a page that does not exist.",
           "Restore the page, redirect it to the closest live equivalent, or remove it from the sitemap and from internal links."),
        _C("FETCH_FAILED", "critical", "Indexation", "Page could not be fetched",
           "The request timed out or the connection failed, so the page may be unreachable for users too.",
           "Check hosting, DNS, and TLS for this URL, then rerun the audit."),
        _C("ROBOTS_BLOCKED", "high", "Indexation", "URL is blocked by robots.txt",
           "A URL that is listed for crawling but blocked in robots.txt sends search engines two opposite instructions.",
           "Decide whether the page should be crawled. Then either lift the robots.txt rule or remove the URL from the sitemap."),
        _C("NOINDEX_IN_SITEMAP", "critical", "Indexation", "Sitemap lists a noindex page",
           "The sitemap asks search engines to index the page and the page itself says not to. The page stays out of search results.",
           "Remove the noindex directive if the page should rank. Otherwise remove the URL from the sitemap."),
        _C("REDIRECT_CHAIN", "high", "Indexation", "Redirect chain of two or more hops",
           "Each extra hop slows the page down and wastes crawl requests. Long chains can stop being followed.",
           "Point the first URL straight at the final destination in a single redirect."),
        _C("REDIRECT", "medium", "Indexation", "Audited URL redirects",
           "Sitemaps and URL inventories should list final URLs. A redirecting entry means the inventory is out of date.",
           "Replace the URL with its final destination in the sitemap and in internal links."),
        _C("CANONICAL_MISMATCH", "high", "Indexation", "Canonical tag points to a different URL",
           "The page tells search engines that another URL is the real version, so this URL is unlikely to be indexed.",
           "Confirm that is intended. If this page should rank on its own, make the canonical self-referencing."),
        _C("CANONICAL_MISSING", "medium", "Indexation", "No canonical tag",
           "Without a canonical tag, URL variants (tracking parameters, trailing slashes) can be indexed as duplicates.",
           "Add a self-referencing canonical link element to the page template."),
        # Metadata
        _C("TITLE_MISSING", "critical", "Metadata", "Missing title tag",
           "The title is the headline shown in search results and browser tabs, and it is read first by screen readers.",
           "Write a unique title that names the page topic and the organization."),
        _C("TITLE_DUPLICATE", "high", "Metadata", "Title tag is shared with another page",
           "Pages with the same title compete with each other and are hard to tell apart in search results, tabs, and analytics reports.",
           "Give each page a title that describes that page only."),
        _C("TITLE_LENGTH", "low", "Metadata", "Title length is outside the guideline",
           "Very short titles say too little. Long titles are usually cut off in search results.",
           "Aim for roughly 15 to 60 characters, with the most important words first."),
        _C("META_DESC_MISSING", "medium", "Metadata", "Missing meta description",
           "Search engines will pick their own snippet, which is often a poor summary of the page.",
           "Write a one or two sentence summary that states what the visitor can do on the page."),
        _C("META_DESC_DUPLICATE", "medium", "Metadata", "Meta description is shared with another page",
           "A repeated description is usually a template default and tells searchers nothing about this page.",
           "Write a description specific to the page."),
        _C("META_DESC_LENGTH", "low", "Metadata", "Meta description length is outside the guideline",
           "Very short descriptions are uninformative and long ones are usually cut off.",
           "Aim for roughly 50 to 160 characters."),
        _C("H1_MISSING", "high", "Metadata", "No H1 heading",
           "The H1 tells readers, screen reader users, and search engines what the page is about.",
           "Add one H1 that states the page topic."),
        _C("H1_MULTIPLE", "medium", "Metadata", "More than one H1 heading",
           "Several H1s blur the page topic and usually mean a template is misusing heading tags for styling.",
           "Keep one H1 and demote the others to H2 or lower."),
        # Accessibility
        _C("LANG_MISSING", "high", "Accessibility", "No lang attribute on the html element",
           "Screen readers use the page language to choose pronunciation rules. This is WCAG success criterion 3.1.1 (Level A).",
           "Add the language to the html element in the page template, for example lang=\"en\"."),
        _C("IMG_ALT_MISSING", "high", "Accessibility", "Images without an alt attribute",
           "Screen readers fall back to reading the file name. This is WCAG success criterion 1.1.1 (Level A).",
           "Describe each informative image in its alt attribute. Use an empty alt (alt=\"\") for decorative images."),
        _C("LINK_TEXT_EMPTY", "high", "Accessibility", "Links with no text",
           "A link with no text or label is announced only as \"link\", so users cannot tell where it goes.",
           "Add link text, alt text on the linked image, or an aria-label."),
        _C("LINK_TEXT_GENERIC", "medium", "Accessibility", "Links with generic text",
           "Text such as \"click here\" does not describe the destination when read out of context. See WCAG success criterion 2.4.4.",
           "Rewrite the link text to name the destination, for example \"Auto loan rates\"."),
        _C("HEADING_SKIP", "low", "Accessibility", "Heading levels are skipped",
           "Jumping from H2 to H4 breaks the outline that screen reader users navigate by.",
           "Use heading levels in order and style them with CSS."),
        # Content
        _C("READING_GRADE_HIGH", "medium", "Content", "Reading level is above the target",
           "Dense text loses readers. Plain language matters most where the stakes are highest: money, health, and legal topics.",
           "Shorten sentences, swap jargon for everyday words, and lead with the answer."),
        _C("THIN_CONTENT", "low", "Content", "Very little body text",
           "A page with almost no text rarely answers a question well enough to rank or to be cited.",
           "Expand the page, merge it into a stronger page, or mark it noindex if it is only a utility page."),
        # Structured data
        _C("JSONLD_INVALID", "high", "Structured data", "JSON-LD does not parse",
           "A syntax error makes the whole block unreadable, so none of the markup in it counts.",
           "Fix the JSON syntax. Trailing commas and unescaped quotes are the usual causes."),
        _C("JSONLD_MISSING_PROPERTY", "medium", "Structured data", "Structured data is missing an expected property",
           "Incomplete markup gives search engines and AI systems less to work with and can disqualify the page from rich results.",
           "Add the missing property to the JSON-LD block."),
        _C("JSONLD_NONE", "low", "Structured data", "No structured data",
           "Structured data states plainly who published the page and what it is about.",
           "Add JSON-LD that fits the page type, such as Organization, Article, FAQPage, or BreadcrumbList."),
        # Links
        _C("BROKEN_INTERNAL_LINK", "critical", "Links", "Internal links to pages that return an error",
           "Readers hit a dead end and the destination page receives no link value.",
           "Update the link to a live URL or remove it."),
        _C("INTERNAL_LINK_REDIRECT", "low", "Links", "Internal links that go through a redirect",
           "The link still works but adds a hop, and it shows the site's own links are out of date.",
           "Link straight to the final URL."),
        _C("ORPHAN_PAGE", "medium", "Links", "No internal links point to this page",
           "A page that nothing links to is hard for visitors and crawlers to find, even if it is in the sitemap.",
           "Link to it from a relevant parent page or the navigation, or retire it."),
    ]
}

GENERIC_LINK_TEXT = {
    "click here", "here", "read more", "learn more", "more", "more info",
    "more information", "this page", "this link", "link", "details", "continue",
}

# Properties each schema.org type is expected to carry. These are editorial
# expectations for this audit, not a copy of any search engine's requirements.
EXPECTED_PROPERTIES: dict[str, tuple[str, ...]] = {
    "Organization": ("name", "url"),
    "WebSite": ("name", "url"),
    "Person": ("name",),
    "LocalBusiness": ("name", "address", "telephone"),
    "Article": ("headline", "author", "datePublished"),
    "FAQPage": ("mainEntity",),
    "BreadcrumbList": ("itemListElement",),
    "Service": ("name", "provider"),
}
TYPE_ALIASES = {
    "BlogPosting": "Article",
    "NewsArticle": "Article",
    "FinancialService": "LocalBusiness",
    "BankOrCreditUnion": "LocalBusiness",
    "MedicalClinic": "LocalBusiness",
    "MedicalBusiness": "LocalBusiness",
    "Dentist": "LocalBusiness",
    "Physician": "LocalBusiness",
    "LegalService": "LocalBusiness",
    "Attorney": "LocalBusiness",
}


def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def check_page(page: Page, t: Thresholds = Thresholds()) -> list[Issue]:
    """Checks that need only the page itself."""
    issues: list[Issue] = []
    add = lambda check_id, detail="": issues.append(Issue(page.url, check_id, detail))  # noqa: E731

    if page.status == 0:
        if "robots.txt" in page.error:
            add("ROBOTS_BLOCKED", page.error)
        else:
            add("FETCH_FAILED", page.error)
        return issues
    if page.status >= 400:
        add("HTTP_ERROR", f"HTTP {page.status}")
        return issues

    if page.redirect_hops >= 2:
        add("REDIRECT_CHAIN", f"{page.redirect_hops} hops, ends at {page.final_url}")
    elif page.redirect_hops == 1:
        add("REDIRECT", f"Redirects to {page.final_url}")

    if not page.parsed:
        return issues

    indexable = not page.noindex
    if page.noindex and page.in_sitemap:
        add("NOINDEX_IN_SITEMAP", f'meta robots: "{page.robots_meta}"')

    if indexable:
        if not page.canonical:
            add("CANONICAL_MISSING")
        elif page.canonical != page.final_url:
            add("CANONICAL_MISMATCH", f"Canonical is {page.canonical}")

        if not page.title:
            add("TITLE_MISSING")
        elif not t.title_min <= len(page.title) <= t.title_max:
            add("TITLE_LENGTH", f"{len(page.title)} characters")

        if not page.meta_description:
            add("META_DESC_MISSING")
        elif not t.description_min <= len(page.meta_description) <= t.description_max:
            add("META_DESC_LENGTH", f"{len(page.meta_description)} characters")

        if page.jsonld_errors:
            for err in page.jsonld_errors:
                add("JSONLD_INVALID", err)
        elif not page.jsonld:
            add("JSONLD_NONE")
        for node in page.jsonld:
            types = node.get("@type")
            for type_name in types if isinstance(types, list) else [types]:
                if not isinstance(type_name, str):
                    continue
                expected = EXPECTED_PROPERTIES.get(TYPE_ALIASES.get(type_name, type_name), ())
                missing = [p for p in expected if _is_empty(node.get(p))]
                if missing:
                    add("JSONLD_MISSING_PROPERTY", f"{type_name} is missing: {', '.join(missing)}")

        words = page.readability.words
        if words < t.thin_words:
            add("THIN_CONTENT", f"{words} words")

    if not page.h1s:
        add("H1_MISSING")
    elif len(page.h1s) > 1:
        add("H1_MULTIPLE", f"{len(page.h1s)} H1s: " + " | ".join(page.h1s))

    if not page.lang:
        add("LANG_MISSING")
    if page.images_missing_alt:
        add("IMG_ALT_MISSING", f"{page.images_missing_alt} of {page.images_total} images")

    empty = [link.href for link in page.links if not link.text]
    if empty:
        add("LINK_TEXT_EMPTY", f"{len(empty)} link(s): " + ", ".join(sorted(set(empty))[:5]))
    generic = sorted({link.text for link in page.links if link.text.lower().strip(" .>»") in GENERIC_LINK_TEXT})
    if generic:
        add("LINK_TEXT_GENERIC", "Link text used: " + ", ".join(f'"{g}"' for g in generic))

    previous = 0
    for level, text in page.headings:
        if previous and level > previous + 1:
            add("HEADING_SKIP", f'H{previous} is followed by H{level} ("{text[:60]}")')
            break
        previous = level

    grade = page.readability.grade
    if grade is not None and grade > t.grade_target:
        add(
            "READING_GRADE_HIGH",
            f"Grade {grade} against a target of {t.grade_target:g} "
            f"({page.readability.words_per_sentence} words per sentence)",
        )

    return issues


def check_site(pages: list[Page], link_status: dict[str, tuple[int, str]]) -> list[Issue]:
    """Checks that compare pages with each other.

    ``link_status`` maps every internal link target to (status, final_url).
    """
    issues: list[Issue] = []
    live = [p for p in pages if p.parsed]
    indexable = [p for p in live if not p.noindex]

    for attr, check_id in (("title", "TITLE_DUPLICATE"), ("meta_description", "META_DESC_DUPLICATE")):
        groups: dict[str, list[Page]] = defaultdict(list)
        for p in indexable:
            value = getattr(p, attr)
            if value:
                groups[value.lower()].append(p)
        for group in groups.values():
            if len(group) > 1:
                for p in group:
                    others = ", ".join(o.url for o in group if o is not p)
                    issues.append(Issue(p.url, check_id, f'"{getattr(p, attr)}" is also used on {others}'))

    inbound: dict[str, set[str]] = defaultdict(set)
    for p in live:
        broken: list[str] = []
        redirected: list[str] = []
        for link in p.links:
            if not link.internal:
                continue
            status, final_url = link_status.get(link.href, (200, link.href))
            if link.href != p.final_url:
                inbound[link.href].add(p.url)
                inbound[final_url].add(p.url)
            if status >= 400 or status == 0:
                broken.append(f"{link.href} (HTTP {status})" if status else f"{link.href} (no response)")
            elif final_url != link.href:
                redirected.append(f"{link.href} -> {final_url}")
        if broken:
            issues.append(Issue(p.url, "BROKEN_INTERNAL_LINK", "; ".join(sorted(set(broken)))))
        if redirected:
            issues.append(Issue(p.url, "INTERNAL_LINK_REDIRECT", "; ".join(sorted(set(redirected)))))

    if len(live) > 1:
        for p in live:
            if urlsplit(p.final_url).path in ("", "/"):
                continue  # the homepage is the entry point, not an orphan
            linking = (inbound.get(p.url, set()) | inbound.get(p.final_url, set())) - {p.url}
            if not linking:
                issues.append(Issue(p.url, "ORPHAN_PAGE"))

    return issues


def sort_issues(issues: list[Issue]) -> list[Issue]:
    return sorted(issues, key=lambda i: (SEVERITIES.index(i.check.severity), i.check_id, i.url))
