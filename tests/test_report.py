import csv
import sqlite3

import pytest

from conftest import DEMO_BASE, DEMO_SITE, REPO
from webaudit.audit import run_audit
from webaudit.cli import main
from webaudit.fetch import LocalSource
from webaudit.report import ISSUE_COLUMNS, PAGE_COLUMNS, write_all


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    out = tmp_path_factory.mktemp("report")
    result = run_audit(LocalSource(DEMO_SITE, DEMO_BASE))
    return out, result, write_all(result, out)


def test_all_outputs_are_written(report):
    out, _result, _summary = report
    for name in ("pages.csv", "issues.csv", "audit.sqlite", "report.md", "report.html"):
        assert (out / name).stat().st_size > 0


def test_csv_files_match_the_audit(report):
    out, result, _summary = report
    pages = list(csv.DictReader((out / "pages.csv").open(encoding="utf-8")))
    issues = list(csv.DictReader((out / "issues.csv").open(encoding="utf-8")))
    assert list(pages[0]) == PAGE_COLUMNS
    assert list(issues[0]) == ISSUE_COLUMNS
    assert len(pages) == len(result.pages)
    assert len(issues) == len(result.issues)
    assert sum(int(p["issue_count"]) for p in pages) == len(issues)
    mortgage = next(p for p in pages if p["url"].endswith("/loans/mortgage/"))
    assert mortgage["section"] == "/loans/"
    assert float(mortgage["reading_grade"]) > 12


def test_summary_counts_add_up(report):
    _out, result, summary = report
    assert sum(summary.severity_counts.values()) == len(result.issues)
    assert sum(len(cs.issues) for cs in summary.by_check) == len(result.issues)
    assert summary.clean_pages == 1  # only the homepage is clean
    ranks = [cs.check.severity for cs in summary.by_check]
    assert ranks == sorted(ranks, key=["critical", "high", "medium", "low"].index)


@pytest.mark.parametrize("query", sorted((REPO / "queries").glob("*.sql")), ids=lambda p: p.name)
def test_every_sql_query_runs_and_returns_rows(report, query):
    out, _result, _summary = report
    con = sqlite3.connect(out / "audit.sqlite")
    try:
        rows = con.execute(query.read_text(encoding="utf-8")).fetchall()
    finally:
        con.close()
    assert rows


def test_sql_and_report_agree(report):
    out, result, _summary = report
    con = sqlite3.connect(out / "audit.sqlite")
    try:
        critical = con.execute(
            "SELECT COUNT(*) FROM issues JOIN checks USING (check_id) WHERE severity = 'critical'"
        ).fetchone()[0]
        unscored = con.execute("SELECT COUNT(*) FROM pages WHERE reading_grade IS NULL").fetchone()[0]
    finally:
        con.close()
    assert critical == sum(1 for i in result.issues if i.check.severity == "critical")
    assert unscored == sum(1 for p in result.pages if p.readability.grade is None)


def test_html_report_escapes_page_content(tmp_path, make_page):
    from webaudit.audit import AuditResult
    from webaudit.checks import Thresholds, check_page

    page = make_page(
        '<html lang="en"><head><title>x</title></head><body>'
        "<h1>One</h1><h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1></body></html>"
    )
    result = AuditResult([page], check_page(page), Thresholds(), from_sitemap=False)
    write_all(result, tmp_path)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_cli_exit_codes(tmp_path, capsys):
    args = ["--dir", str(DEMO_SITE), "--base-url", DEMO_BASE, "--out", str(tmp_path), "--quiet"]
    assert main(args) == 0
    assert "11 pages audited, 20 issues (3 critical, 7 high, 7 medium, 3 low)" in capsys.readouterr().out
    assert main(args + ["--fail-on", "critical"]) == 1
