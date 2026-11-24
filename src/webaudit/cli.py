"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audit import run_audit
from .checks import SEVERITIES, Thresholds
from .fetch import DEFAULT_USER_AGENT, HttpSource, LocalSource
from .report import write_all


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="webaudit",
        description="Audit a website for indexation, metadata, accessibility, "
        "plain-language, structured data, and internal link problems.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--sitemap", metavar="URL", help="XML sitemap (or sitemap index) of a live site")
    src.add_argument("--urls", metavar="FILE", help="text file with one URL per line")
    src.add_argument("--dir", metavar="FOLDER", help="folder of HTML files to audit offline")

    p.add_argument("--base-url", default="https://www.example.test/",
                   help="URL the folder is served from (with --dir)")
    p.add_argument("--out", default="audit-report", metavar="FOLDER", help="where to write the report")
    p.add_argument("--max-pages", type=int, default=500, help="stop after this many pages (default 500)")
    p.add_argument("--delay", type=float, default=1.0,
                   help="seconds to wait between requests to a live site (default 1.0)")
    p.add_argument("--grade-target", type=float, default=8.0,
                   help="flag pages that read above this grade level (default 8)")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    p.add_argument("--fail-on", choices=SEVERITIES, metavar="SEVERITY",
                   help="exit with status 1 if any issue at this severity or worse is found "
                        "(critical, high, medium, low). Useful in CI.")
    p.add_argument("--quiet", action="store_true", help="no progress output")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.dir:
        source = LocalSource(args.dir, args.base_url)
    elif args.sitemap:
        source = HttpSource(sitemap_url=args.sitemap, delay=args.delay, user_agent=args.user_agent)
    else:
        lines = Path(args.urls).read_text(encoding="utf-8").splitlines()
        urls = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
        source = HttpSource(urls=urls, delay=args.delay, user_agent=args.user_agent)

    progress = None if args.quiet else (lambda msg: print(msg, file=sys.stderr))
    result = run_audit(
        source,
        thresholds=Thresholds(grade_target=args.grade_target),
        max_pages=args.max_pages,
        progress=progress,
    )
    summary = write_all(result, args.out)

    counts = ", ".join(f"{summary.severity_counts[s]} {s}" for s in SEVERITIES)
    print(f"{len(result.pages)} pages audited, {len(result.issues)} issues ({counts})")
    print(f"Report: {Path(args.out) / 'report.html'}")

    if args.fail_on:
        limit = SEVERITIES.index(args.fail_on)
        if any(summary.severity_counts[s] for s in SEVERITIES[: limit + 1]):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
