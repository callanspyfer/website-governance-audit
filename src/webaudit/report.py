"""Write the audit out as CSV, SQLite, Markdown, and a self-contained HTML report."""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from .audit import AuditResult
from .checks import CHECKS, SEVERITIES, Check, Issue
from .parse import Page

PAGE_COLUMNS = [
    "url", "section", "final_url", "status", "redirect_hops", "in_sitemap", "indexable",
    "title", "title_length", "meta_description", "meta_description_length",
    "canonical", "lang", "h1_count", "h1", "word_count", "reading_grade",
    "words_per_sentence", "images", "images_missing_alt", "internal_links_out",
    "external_links_out", "jsonld_types", "issue_count", "worst_severity",
]
ISSUE_COLUMNS = ["severity", "category", "check_id", "check", "url", "detail", "fix"]
MAX_URLS_PER_CHECK = 25  # the reports list this many; issues.csv has all of them


def _page_row(page: Page, issues: list[Issue]) -> dict:
    severities = [i.check.severity for i in issues]
    worst = min(severities, key=SEVERITIES.index) if severities else ""
    segments = [seg for seg in urlsplit(page.url).path.split("/") if seg]
    return {
        "url": page.url,
        # First folder of the path, so results can be grouped by site section.
        "section": f"/{segments[0]}/" if segments else "/",
        "final_url": page.final_url,
        "status": page.status,
        "redirect_hops": page.redirect_hops,
        "in_sitemap": int(page.in_sitemap),
        "indexable": int(page.parsed and not page.noindex),
        "title": page.title,
        "title_length": len(page.title),
        "meta_description": page.meta_description,
        "meta_description_length": len(page.meta_description),
        "canonical": page.canonical,
        "lang": page.lang,
        "h1_count": len(page.h1s),
        "h1": page.h1s[0] if page.h1s else "",
        "word_count": page.readability.words,
        "reading_grade": "" if page.readability.grade is None else page.readability.grade,
        "words_per_sentence": page.readability.words_per_sentence or "",
        "images": page.images_total,
        "images_missing_alt": page.images_missing_alt,
        "internal_links_out": sum(1 for link in page.links if link.internal),
        "external_links_out": sum(1 for link in page.links if not link.internal),
        "jsonld_types": ", ".join(page.jsonld_types),
        "issue_count": len(issues),
        "worst_severity": worst,
    }


def _issue_row(issue: Issue) -> dict:
    c = issue.check
    return {
        "severity": c.severity,
        "category": c.category,
        "check_id": c.id,
        "check": c.title,
        "url": issue.url,
        "detail": issue.detail,
        "fix": c.fix,
    }


@dataclass
class CheckSummary:
    check: Check
    issues: list[Issue]

    @property
    def pages_affected(self) -> int:
        return len({i.url for i in self.issues})


@dataclass
class Summary:
    site: str
    result: AuditResult
    page_rows: list[dict]
    by_check: list[CheckSummary]  # most serious and most widespread first
    severity_counts: dict[str, int]
    clean_pages: int


def summarize(result: AuditResult) -> Summary:
    by_url: dict[str, list[Issue]] = defaultdict(list)
    grouped: dict[str, list[Issue]] = defaultdict(list)
    for issue in result.issues:
        by_url[issue.url].append(issue)
        grouped[issue.check_id].append(issue)

    by_check = [CheckSummary(CHECKS[cid], items) for cid, items in grouped.items()]
    by_check.sort(key=lambda s: (SEVERITIES.index(s.check.severity), -s.pages_affected, s.check.id))

    counts = Counter(i.check.severity for i in result.issues)
    page_rows = [_page_row(p, by_url.get(p.url, [])) for p in result.pages]
    site = urlsplit(result.pages[0].url).netloc if result.pages else ""
    return Summary(
        site=site,
        result=result,
        page_rows=page_rows,
        by_check=by_check,
        severity_counts={s: counts.get(s, 0) for s in SEVERITIES},
        clean_pages=sum(1 for r in page_rows if r["issue_count"] == 0),
    )


# ---------------------------------------------------------------- CSV / SQLite


def write_csv(summary: Summary, out: Path) -> None:
    with (out / "pages.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAGE_COLUMNS)
        writer.writeheader()
        writer.writerows(summary.page_rows)
    with (out / "issues.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ISSUE_COLUMNS)
        writer.writeheader()
        writer.writerows(_issue_row(i) for i in summary.result.issues)


def write_sqlite(summary: Summary, out: Path) -> None:
    db_path = out / "audit.sqlite"
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """CREATE TABLE pages (
                url TEXT PRIMARY KEY, section TEXT, final_url TEXT, status INTEGER, redirect_hops INTEGER,
                in_sitemap INTEGER, indexable INTEGER, title TEXT, title_length INTEGER,
                meta_description TEXT, meta_description_length INTEGER, canonical TEXT,
                lang TEXT, h1_count INTEGER, h1 TEXT, word_count INTEGER, reading_grade REAL,
                words_per_sentence REAL, images INTEGER, images_missing_alt INTEGER,
                internal_links_out INTEGER, external_links_out INTEGER, jsonld_types TEXT,
                issue_count INTEGER, worst_severity TEXT)"""
        )
        con.execute(
            """CREATE TABLE checks (
                check_id TEXT PRIMARY KEY, severity TEXT, severity_rank INTEGER,
                category TEXT, title TEXT, why TEXT, fix TEXT)"""
        )
        con.execute(
            """CREATE TABLE issues (
                url TEXT REFERENCES pages(url), check_id TEXT REFERENCES checks(check_id),
                detail TEXT)"""
        )
        con.executemany(
            f"INSERT INTO pages VALUES ({','.join('?' * len(PAGE_COLUMNS))})",
            [[None if r[c] == "" and c in ("reading_grade", "words_per_sentence") else r[c]
              for c in PAGE_COLUMNS] for r in summary.page_rows],
        )
        con.executemany(
            "INSERT INTO checks VALUES (?,?,?,?,?,?,?)",
            [(c.id, c.severity, SEVERITIES.index(c.severity) + 1, c.category, c.title, c.why, c.fix)
             for c in CHECKS.values()],
        )
        con.executemany(
            "INSERT INTO issues VALUES (?,?,?)",
            [(i.url, i.check_id, i.detail) for i in summary.result.issues],
        )
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------- Markdown


def _path(url: str) -> str:
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _md_cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _scope_note(result: AuditResult) -> list[str]:
    notes = []
    if result.truncated:
        notes.append(f"{result.truncated} URL(s) were skipped because of the page limit.")
    if result.links_unchecked:
        notes.append(f"{result.links_unchecked} internal link target(s) were not checked because of the link limit.")
    return notes


def render_markdown(s: Summary) -> str:
    r = s.result
    total = len(r.issues)
    lines = [
        f"# Website governance audit: {s.site}",
        "",
        f"Generated {r.generated_at}. Source: {'XML sitemap' if r.from_sitemap else 'URL list'}.",
        "",
        "## Summary",
        "",
        f"- Pages audited: **{len(r.pages)}**",
        f"- Pages with no issues: **{s.clean_pages}**",
        f"- Issues found: **{total}**",
        "",
        "| Severity | Issues |",
        "| --- | ---: |",
    ]
    lines += [f"| {sev.capitalize()} | {s.severity_counts[sev]} |" for sev in SEVERITIES]
    lines += [f"\n> {note}" for note in _scope_note(r)]

    lines += [
        "",
        "## What to fix first",
        "",
        "Ordered by severity, then by how many pages are affected.",
        "",
        "| # | Severity | Issue | Pages | Fix |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for n, cs in enumerate(s.by_check, 1):
        c = cs.check
        lines.append(
            f"| {n} | {c.severity.capitalize()} | {_md_cell(c.title)} | {cs.pages_affected} | {_md_cell(c.fix)} |"
        )

    lines += ["", "## Findings"]
    for cs in s.by_check:
        c = cs.check
        lines += [
            "",
            f"### {c.title}",
            "",
            f"**{c.severity.capitalize()}** · {c.category} · `{c.id}` · {cs.pages_affected} page(s)",
            "",
            f"Why it matters: {c.why}",
            "",
        ]
        for issue in cs.issues[:MAX_URLS_PER_CHECK]:
            detail = f": {issue.detail}" if issue.detail else ""
            lines.append(f"- `{_path(issue.url)}`{detail}")
        if len(cs.issues) > MAX_URLS_PER_CHECK:
            lines.append(f"- and {len(cs.issues) - MAX_URLS_PER_CHECK} more in `issues.csv`")

    scored = sorted(
        (row for row in s.page_rows if row["reading_grade"] != ""),
        key=lambda row: -row["reading_grade"],
    )
    if scored:
        lines += [
            "",
            "## Reading level by page",
            "",
            f"Flesch-Kincaid grade level of the main content. Target: grade {r.thresholds.grade_target:g} or lower.",
            "",
            "| Page | Grade | Words per sentence | Words |",
            "| --- | ---: | ---: | ---: |",
        ]
        for row in scored:
            flag = " (above target)" if row["reading_grade"] > r.thresholds.grade_target else ""
            lines.append(
                f"| `{_path(row['url'])}` | {row['reading_grade']}{flag} | {row['words_per_sentence']} | {row['word_count']} |"
            )

    lines += [
        "",
        "## Files",
        "",
        "- `pages.csv`: one row per page with every measured field",
        "- `issues.csv`: one row per issue, with the fix",
        "- `audit.sqlite`: the same data as tables (`pages`, `issues`, `checks`) for SQL analysis",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------- HTML

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b2330;--muted:#5b6676;--line:#dfe3ea;
--critical:#b3261e;--high:#b45309;--medium:#1d5fa8;--low:#4b5563;--ok:#1f7a4d}
@media (prefers-color-scheme:dark){:root{--bg:#12161d;--card:#1a2029;--ink:#e8ecf2;--muted:#9aa5b5;
--line:#2c3441;--critical:#ff8a80;--high:#f5b560;--medium:#7fb5f0;--low:#aab3c0;--ok:#6fcf97}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:40px 20px 72px}
a{color:var(--medium)}
h1{font-size:1.9rem;line-height:1.2;margin:0 0 6px}
h2{font-size:1.3rem;margin:44px 0 12px}
h3{font-size:1.05rem;margin:0 0 6px}
p{margin:0 0 12px}
.muted{color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.tile .n{font-size:2rem;font-weight:700;line-height:1.1}
.tile .l{color:var(--muted);font-size:.9rem}
.tile.critical{border-top:4px solid var(--critical)}.tile.high{border-top:4px solid var(--high)}
.tile.medium{border-top:4px solid var(--medium)}.tile.low{border-top:4px solid var(--low)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:12px 0}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.93rem}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td.num,th.num{text-align:right;white-space:nowrap}
.pill{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:1px 10px;font-size:.78rem;font-weight:700;white-space:nowrap}
.pill.critical{color:var(--critical)}.pill.high{color:var(--high)}.pill.medium{color:var(--medium)}.pill.low{color:var(--low)}
code{font:.88em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;word-break:break-all}
ul.urls{margin:10px 0 0;padding-left:20px}ul.urls li{margin:4px 0}
.meta{color:var(--muted);font-size:.88rem;margin-bottom:8px}
.bar{height:8px;border-radius:4px;background:var(--line);min-width:120px}
.bar span{display:block;height:8px;border-radius:4px;background:var(--ok)}
.bar.over span{background:var(--high)}
footer{margin-top:48px;color:var(--muted);font-size:.88rem}
"""


def render_html(s: Summary) -> str:
    r = s.result
    e = escape
    out: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="robots" content="noindex">',
        f"<title>Website governance audit: {e(s.site)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>Website governance audit: {e(s.site)}</h1>",
        f'<p class="muted">Generated {e(r.generated_at)}. '
        f"Source: {'XML sitemap' if r.from_sitemap else 'URL list'}.</p>",
        '<div class="tiles">',
        f'<div class="tile"><div class="n">{len(r.pages)}</div><div class="l">Pages audited</div></div>',
        f'<div class="tile"><div class="n">{s.clean_pages}</div><div class="l">Pages with no issues</div></div>',
    ]
    for sev in SEVERITIES:
        out.append(
            f'<div class="tile {sev}"><div class="n">{s.severity_counts[sev]}</div>'
            f'<div class="l">{sev.capitalize()} issues</div></div>'
        )
    out.append("</div>")
    out += [f'<p class="muted">{e(note)}</p>' for note in _scope_note(r)]

    out += [
        "<h2>What to fix first</h2>",
        '<p class="muted">Ordered by severity, then by how many pages are affected.</p>',
        '<div class="card scroll"><table>',
        '<thead><tr><th class="num">#</th><th>Severity</th><th>Issue</th>'
        '<th class="num">Pages</th><th>Fix</th></tr></thead><tbody>',
    ]
    for n, cs in enumerate(s.by_check, 1):
        c = cs.check
        out.append(
            f'<tr><td class="num">{n}</td><td><span class="pill {c.severity}">{c.severity.capitalize()}</span></td>'
            f'<td><a href="#{c.id}">{e(c.title)}</a></td><td class="num">{cs.pages_affected}</td>'
            f"<td>{e(c.fix)}</td></tr>"
        )
    out.append("</tbody></table></div>")

    out.append("<h2>Findings</h2>")
    for cs in s.by_check:
        c = cs.check
        out += [
            f'<section class="card" id="{c.id}">',
            f"<h3>{e(c.title)}</h3>",
            f'<div class="meta"><span class="pill {c.severity}">{c.severity.capitalize()}</span> '
            f"{e(c.category)} · <code>{c.id}</code> · {cs.pages_affected} page(s)</div>",
            f"<p><strong>Why it matters:</strong> {e(c.why)}</p>",
            f"<p><strong>Fix:</strong> {e(c.fix)}</p>",
            '<ul class="urls">',
        ]
        for issue in cs.issues[:MAX_URLS_PER_CHECK]:
            detail = f": {e(issue.detail)}" if issue.detail else ""
            out.append(f"<li><code>{e(_path(issue.url))}</code>{detail}</li>")
        if len(cs.issues) > MAX_URLS_PER_CHECK:
            out.append(f"<li>and {len(cs.issues) - MAX_URLS_PER_CHECK} more in <code>issues.csv</code></li>")
        out += ["</ul>", "</section>"]

    scored = sorted(
        (row for row in s.page_rows if row["reading_grade"] != ""),
        key=lambda row: -row["reading_grade"],
    )
    if scored:
        target = r.thresholds.grade_target
        scale = max(max(row["reading_grade"] for row in scored), target) or 1
        out += [
            "<h2>Reading level by page</h2>",
            f'<p class="muted">Flesch-Kincaid grade level of the main content. Target: grade {target:g} or lower.</p>',
            '<div class="card scroll"><table>',
            '<thead><tr><th>Page</th><th class="num">Grade</th><th></th>'
            '<th class="num">Words per sentence</th><th class="num">Words</th></tr></thead><tbody>',
        ]
        for row in scored:
            over = row["reading_grade"] > target
            width = round(100 * row["reading_grade"] / scale)
            label = f'{row["reading_grade"]}' + (" (above target)" if over else "")
            out.append(
                f'<tr><td><code>{e(_path(row["url"]))}</code></td><td class="num">{label}</td>'
                f'<td><div class="bar{" over" if over else ""}"><span style="width:{width}%"></span></div></td>'
                f'<td class="num">{row["words_per_sentence"]}</td><td class="num">{row["word_count"]}</td></tr>'
            )
        out.append("</tbody></table></div>")

    out += [
        "<footer>Full data: <code>pages.csv</code>, <code>issues.csv</code>, <code>audit.sqlite</code>. "
        "Generated by website-governance-audit.</footer>",
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(out) + "\n"


def write_all(result: AuditResult, out_dir: str | Path) -> Summary:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = summarize(result)
    write_csv(summary, out)
    write_sqlite(summary, out)
    (out / "report.md").write_text(render_markdown(summary), encoding="utf-8")
    (out / "report.html").write_text(render_html(summary), encoding="utf-8")
    return summary
