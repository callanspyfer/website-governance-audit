"""End-to-end run against the demo site.

The demo site has one known problem planted for almost every check. This test
pins the full list, so a change that adds a false positive or loses a real
finding fails here.
"""

from conftest import DEMO_BASE, DEMO_SITE
from webaudit.audit import run_audit
from webaudit.fetch import LocalSource

EXPECTED = {
    ("/branches/", "HTTP_ERROR"),
    ("/rates/", "NOINDEX_IN_SITEMAP"),
    ("/blog/first-time-home-buyer-guide/", "BROKEN_INTERNAL_LINK"),
    ("/blog/first-time-home-buyer-guide/", "CANONICAL_MISSING"),
    ("/blog/first-time-home-buyer-guide/", "JSONLD_MISSING_PROPERTY"),
    ("/checking/", "TITLE_DUPLICATE"),
    ("/savings/", "TITLE_DUPLICATE"),
    ("/savings/", "META_DESC_MISSING"),
    ("/checking/student/", "CANONICAL_MISMATCH"),
    ("/loans/auto/", "H1_MULTIPLE"),
    ("/loans/auto/", "IMG_ALT_MISSING"),
    ("/loans/auto/", "LINK_TEXT_EMPTY"),
    ("/loans/auto/", "LINK_TEXT_GENERIC"),
    ("/loans/mortgage/", "READING_GRADE_HIGH"),
    ("/loans/mortgage/", "HEADING_SKIP"),
    ("/about/", "LANG_MISSING"),
    ("/about/", "JSONLD_INVALID"),
    ("/disclosures/", "ORPHAN_PAGE"),
    ("/disclosures/", "THIN_CONTENT"),
    ("/disclosures/", "JSONLD_NONE"),
}


def run():
    return run_audit(LocalSource(DEMO_SITE, DEMO_BASE))


def test_demo_site_findings_are_exactly_the_planted_problems():
    result = run()
    found = {(i.url.removeprefix(DEMO_BASE), i.check_id) for i in result.issues}
    assert found == EXPECTED
    assert len(result.issues) == len(EXPECTED)  # no duplicates


def test_demo_site_scope():
    result = run()
    assert result.from_sitemap
    assert len(result.pages) == 11
    home = next(p for p in result.pages if p.url == DEMO_BASE + "/")
    assert home.jsonld_types == ["Organization"]


def test_issues_are_sorted_most_serious_first():
    severities = [i.check.severity for i in run().issues]
    order = ["critical", "high", "medium", "low"]
    assert severities == sorted(severities, key=order.index)


def test_max_pages_limits_the_run_and_reports_what_was_skipped():
    result = run_audit(LocalSource(DEMO_SITE, DEMO_BASE), max_pages=3)
    assert len(result.pages) == 3
    assert result.truncated == 8


def test_local_source_cannot_read_outside_its_folder():
    source = LocalSource(DEMO_SITE, DEMO_BASE)
    assert source.get(DEMO_BASE + "/../../README.md").status == 404
    assert source.get(DEMO_BASE + "/%2e%2e/%2e%2e/README.md").status == 404
