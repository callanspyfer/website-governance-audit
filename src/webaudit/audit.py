"""Run the audit: fetch pages, parse them, check links, apply the checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .checks import Issue, Thresholds, check_page, check_site, sort_issues
from .parse import Page, parse_page


@dataclass
class AuditResult:
    pages: list[Page]
    issues: list[Issue]
    thresholds: Thresholds
    from_sitemap: bool
    truncated: int = 0  # seed URLs skipped because of --max-pages
    links_unchecked: int = 0  # internal link targets skipped because of the link cap
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )


def run_audit(
    source,
    thresholds: Thresholds = Thresholds(),
    max_pages: int = 500,
    max_link_checks: int = 1000,
    progress: Callable[[str], None] | None = None,
) -> AuditResult:
    say = progress or (lambda _msg: None)

    seeds, from_sitemap = source.seed_urls()
    seeds = list(dict.fromkeys(seeds))
    truncated = max(0, len(seeds) - max_pages)
    seeds = seeds[:max_pages]
    say(f"Auditing {len(seeds)} URL(s)" + (f" ({truncated} skipped by --max-pages)" if truncated else ""))

    pages: list[Page] = []
    for i, url in enumerate(seeds, 1):
        say(f"  [{i}/{len(seeds)}] {url}")
        pages.append(parse_page(source.get(url), in_sitemap=from_sitemap))

    # Every internal link target needs a status. Pages already fetched supply
    # their own. Anything else gets one request.
    link_status: dict[str, tuple[int, str]] = {}
    for p in pages:
        link_status[p.url] = (p.status, p.final_url)
    targets = sorted(
        {link.href for p in pages for link in p.links if link.internal} - set(link_status)
    )
    unchecked = max(0, len(targets) - max_link_checks)
    targets = targets[:max_link_checks]
    if targets:
        say(f"Checking {len(targets)} internal link target(s) outside the audited set")
    for url in targets:
        resp = source.status(url)
        link_status[url] = (resp.status, resp.final_url)

    issues: list[Issue] = []
    for p in pages:
        issues.extend(check_page(p, thresholds))
    issues.extend(check_site(pages, link_status))

    return AuditResult(
        pages=pages,
        issues=sort_issues(issues),
        thresholds=thresholds,
        from_sitemap=from_sitemap,
        truncated=truncated,
        links_unchecked=unchecked,
    )
