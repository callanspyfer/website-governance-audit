import pytest

from conftest import BODY, CLEAN_HTML
from webaudit.checks import CHECKS, SEVERITIES, Thresholds, check_page, check_site


def ids(issues):
    return sorted({i.check_id for i in issues})


def test_clean_page_has_no_issues(make_page):
    assert check_page(make_page()) == []


def test_registry_is_complete():
    for check in CHECKS.values():
        assert check.severity in SEVERITIES
        assert check.title and check.why and check.fix


# Each case changes one thing on the clean page and expects exactly one check to fire.
PAGE_CASES = [
    ("TITLE_MISSING", "<title>Free Checking Accounts | Example CU</title>", ""),
    ("TITLE_LENGTH", "Free Checking Accounts | Example CU</title>", "Checking</title>"),
    ("META_DESC_MISSING", '<meta name="description"', '<meta name="keywords"'),
    ("META_DESC_LENGTH", "with no monthly fee and no minimum balance today.", "now."),
    ("CANONICAL_MISSING", '<link rel="canonical" href="https://example.test/checking/">', ""),
    ("CANONICAL_MISMATCH", 'href="https://example.test/checking/"', 'href="https://example.test/other/"'),
    ("H1_MISSING", "<h1>Free checking</h1>", ""),
    ("H1_MULTIPLE", "<h1>Free checking</h1>", "<h1>Free checking</h1><h1>Second</h1>"),
    ("LANG_MISSING", '<html lang="en">', "<html>"),
    ("IMG_ALT_MISSING", 'alt="A debit card"', ""),
    ("LINK_TEXT_GENERIC", "Savings accounts</a>", "Click here</a>"),
    ("LINK_TEXT_EMPTY", "Savings accounts</a>", "</a>"),
    ("HEADING_SKIP", "<h2>What you get</h2>", "<h4>What you get</h4>"),
    ("THIN_CONTENT", BODY, "Short page."),
    ("JSONLD_NONE", 'type="application/ld+json"', 'type="text/plain"'),
    ("JSONLD_INVALID", '"url": "https://example.test/"}', '"url": "https://example.test/",}'),
    ("JSONLD_MISSING_PROPERTY", '"name": "Example CU", ', ""),
]


@pytest.mark.parametrize("check_id, old, new", PAGE_CASES, ids=[c[0] for c in PAGE_CASES])
def test_each_page_check_fires_alone(make_page, check_id, old, new):
    assert old in CLEAN_HTML
    issues = check_page(make_page(CLEAN_HTML.replace(old, new)))
    assert ids(issues) == [check_id]


def test_reading_grade_respects_the_target(make_page):
    dense = (
        "Applicants seeking conventional financing are generally required to demonstrate "
        "a ratio not exceeding the maximum permissible threshold established under applicable "
        "investor guidelines, inclusive of all recurring monthly obligations. "
    ) * 5
    page = make_page(CLEAN_HTML.replace(BODY, dense))
    assert ids(check_page(page)) == ["READING_GRADE_HIGH"]
    assert check_page(page, Thresholds(grade_target=30)) == []


def test_status_checks(make_page):
    assert ids(check_page(make_page(status=404))) == ["HTTP_ERROR"]
    assert ids(check_page(make_page(status=0, html="", error="ConnectTimeout"))) == ["FETCH_FAILED"]
    assert ids(check_page(make_page(status=0, html="", error="Blocked by robots.txt"))) == ["ROBOTS_BLOCKED"]
    assert ids(check_page(make_page(redirect_hops=1))) == ["REDIRECT"]
    assert ids(check_page(make_page(redirect_hops=3))) == ["REDIRECT_CHAIN"]


def test_noindex_is_only_a_conflict_when_the_sitemap_lists_the_page(make_page):
    html = CLEAN_HTML.replace("<title>", '<meta name="robots" content="noindex"><title>')
    assert ids(check_page(make_page(html, in_sitemap=True))) == ["NOINDEX_IN_SITEMAP"]
    assert check_page(make_page(html, in_sitemap=False)) == []


def test_local_business_subtypes_use_local_business_expectations(make_page):
    html = CLEAN_HTML.replace('"@type": "Organization"', '"@type": "Dentist"')
    (issue,) = check_page(make_page(html))
    assert issue.check_id == "JSONLD_MISSING_PROPERTY"
    assert issue.detail == "Dentist is missing: address, telephone"


def test_duplicate_titles_and_descriptions(make_page):
    a = make_page(url="https://example.test/checking/")
    b = make_page(url="https://example.test/savings/")
    issues = check_site([a, b], {})
    assert ids(issues) == ["META_DESC_DUPLICATE", "ORPHAN_PAGE", "TITLE_DUPLICATE"]
    assert {i.url for i in issues if i.check_id == "TITLE_DUPLICATE"} == {a.url, b.url}


def test_broken_and_redirected_internal_links(make_page):
    page = make_page()
    target = "https://example.test/savings/"
    assert ids(check_site([page], {target: (404, target)})) == ["BROKEN_INTERNAL_LINK"]
    assert ids(check_site([page], {target: (200, "https://example.test/save/")})) == ["INTERNAL_LINK_REDIRECT"]
    assert check_site([page], {target: (200, target)}) == []


def test_orphan_detection_ignores_the_homepage_and_self_links(make_page):
    home = make_page('<html><body><a href="/a/">A</a></body></html>', url="https://example.test/")
    linked = make_page('<html><body><a href="/a/">Self</a></body></html>', url="https://example.test/a/")
    orphan = make_page('<html><body><a href="/b/">Self</a></body></html>', url="https://example.test/b/")
    issues = check_site([home, linked, orphan], {})
    assert [(i.check_id, i.url) for i in issues] == [("ORPHAN_PAGE", orphan.url)]
