"""Audit one page from its HTML, with no network access.

This is the entry point for anything that already has the markup in hand:
a CMS preview, a pull request check, or the in-browser demo, which runs this
same function through Pyodide.
"""

from __future__ import annotations

import json

from .checks import CHECKS, SEVERITIES, Thresholds, check_page, sort_issues
from .fetch import Response, normalize_url
from .parse import parse_page

PLACEHOLDER_URL = "https://www.example.test/page/"

# Checks that need more than one page, or a live request, to mean anything.
NEEDS_A_SITE = (
    "TITLE_DUPLICATE", "META_DESC_DUPLICATE", "BROKEN_INTERNAL_LINK",
    "INTERNAL_LINK_REDIRECT", "ORPHAN_PAGE", "HTTP_ERROR", "FETCH_FAILED",
    "ROBOTS_BLOCKED", "REDIRECT", "REDIRECT_CHAIN", "NOINDEX_IN_SITEMAP",
)


def audit_html(html: str, url: str | None = None, grade_target: float = 8.0) -> dict:
    """Run every page-level check on one HTML document.

    ``url`` is the address the page is served from. It is used to resolve
    relative links and to compare against the canonical tag. Without it the
    canonical comparison is skipped, because there is nothing to compare to.
    """
    known_url = bool(url and url.strip())
    page_url = normalize_url(url) if known_url else PLACEHOLDER_URL
    page = parse_page(Response(url=page_url, final_url=page_url, status=200, html=html or " "))

    not_run = list(NEEDS_A_SITE)
    issues = check_page(page, Thresholds(grade_target=grade_target))
    if not known_url:
        issues = [i for i in issues if i.check_id != "CANONICAL_MISMATCH"]
        not_run.append("CANONICAL_MISMATCH")
    issues = sort_issues(issues)

    counts = {s: 0 for s in SEVERITIES}
    for issue in issues:
        counts[issue.check.severity] += 1

    r = page.readability
    return {
        "url": page_url if known_url else "",
        "counts": counts,
        "checks_run": len(CHECKS) - len(not_run),
        "issues": [
            {
                "check_id": i.check_id,
                "severity": i.check.severity,
                "category": i.check.category,
                "title": i.check.title,
                "detail": i.detail,
                "why": i.check.why,
                "fix": i.check.fix,
            }
            for i in issues
        ],
        "facts": {
            "title": page.title,
            "title_length": len(page.title),
            "meta_description_length": len(page.meta_description),
            "canonical": page.canonical,
            "lang": page.lang,
            "noindex": page.noindex,
            "h1_count": len(page.h1s),
            "word_count": r.words,
            "reading_grade": r.grade,
            "words_per_sentence": r.words_per_sentence,
            "images": page.images_total,
            "images_missing_alt": page.images_missing_alt,
            "internal_links": sum(1 for link in page.links if link.internal),
            "external_links": sum(1 for link in page.links if not link.internal),
            "structured_data_types": page.jsonld_types,
        },
        "not_run": [CHECKS[check_id].title for check_id in not_run],
    }


def audit_html_json(html: str, url: str | None = None, grade_target: float = 8.0) -> str:
    """Same as ``audit_html`` but returns JSON, for callers outside Python."""
    return json.dumps(audit_html(html, url, grade_target))
