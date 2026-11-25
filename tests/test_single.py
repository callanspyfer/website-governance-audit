import json

from conftest import CLEAN_HTML, DEMO_SITE, REPO
from webaudit.checks import CHECKS
from webaudit.single import NEEDS_A_SITE, audit_html, audit_html_json


def test_clean_page_has_no_issues_and_reports_facts():
    result = audit_html(CLEAN_HTML, url="https://example.test/checking/")
    assert result["issues"] == []
    assert result["counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    facts = result["facts"]
    assert facts["title"] == "Free Checking Accounts | Example CU"
    assert facts["h1_count"] == 1
    assert facts["images"] == 2 and facts["images_missing_alt"] == 0
    assert facts["structured_data_types"] == ["Organization"]
    assert facts["reading_grade"] is not None


def test_problem_page_from_the_demo_site():
    html = (DEMO_SITE / "loans" / "auto" / "index.html").read_text(encoding="utf-8")
    result = audit_html(html, url="https://www.maplewood-demo-cu.test/loans/auto/")
    found = [i["check_id"] for i in result["issues"]]
    assert found == ["IMG_ALT_MISSING", "LINK_TEXT_EMPTY", "H1_MULTIPLE", "LINK_TEXT_GENERIC"]
    assert result["counts"] == {"critical": 0, "high": 2, "medium": 2, "low": 0}
    for issue in result["issues"]:
        assert issue["why"] and issue["fix"] and issue["title"]


def test_canonical_is_only_compared_when_the_url_is_known():
    with_url = audit_html(CLEAN_HTML, url="https://example.test/somewhere-else/")
    assert [i["check_id"] for i in with_url["issues"]] == ["CANONICAL_MISMATCH"]

    without_url = audit_html(CLEAN_HTML)
    assert without_url["issues"] == []
    assert without_url["url"] == ""
    assert CHECKS["CANONICAL_MISMATCH"].title in without_url["not_run"]


def test_checks_run_and_not_run_account_for_every_check():
    result = audit_html(CLEAN_HTML, url="https://example.test/checking/")
    assert result["checks_run"] + len(result["not_run"]) == len(CHECKS)
    assert len(result["not_run"]) == len(NEEDS_A_SITE)


def test_grade_target_is_passed_through():
    html = (DEMO_SITE / "loans" / "mortgage" / "index.html").read_text(encoding="utf-8")
    strict = [i["check_id"] for i in audit_html(html, grade_target=8)["issues"]]
    loose = [i["check_id"] for i in audit_html(html, grade_target=30)["issues"]]
    assert "READING_GRADE_HIGH" in strict
    assert "READING_GRADE_HIGH" not in loose


def test_empty_and_malformed_input_do_not_crash():
    for html in ("", "   ", "not html at all", "<p>unclosed <b>tags", "<html><head><title>"):
        result = audit_html(html)
        assert isinstance(result["issues"], list)
    assert "TITLE_MISSING" in [i["check_id"] for i in audit_html("")["issues"]]


def test_json_output_round_trips():
    result = json.loads(audit_html_json(CLEAN_HTML, "https://example.test/checking/", 8))
    assert result == audit_html(CLEAN_HTML, "https://example.test/checking/", 8)


def test_live_demo_copy_of_the_sample_report_is_current():
    published = (REPO / "docs" / "sample-report.html").read_bytes()
    source = (REPO / "examples" / "demo-report" / "report.html").read_bytes()
    assert published == source
