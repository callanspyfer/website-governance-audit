"""Page sources.

Two ways to get pages into the audit:

* ``HttpSource`` reads a live site from an XML sitemap or a URL list. It
  obeys robots.txt, identifies itself, and waits between requests.
* ``LocalSource`` reads a folder of HTML files (a static build, an export,
  or the demo site in ``examples/``) and maps it onto a base URL.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

DEFAULT_USER_AGENT = (
    "website-governance-audit/0.1 (+https://github.com/callanspyfer/website-governance-audit)"
)


@dataclass
class Response:
    url: str  # URL that was requested
    final_url: str  # URL after redirects
    status: int  # HTTP status, or 0 when the request never completed
    redirect_hops: int = 0
    html: str = ""
    content_type: str = "text/html"
    error: str = ""

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower()


def normalize_url(url: str) -> str:
    """Lowercase the scheme and host, drop the fragment, default the path to /."""
    url, _fragment = urldefrag(url.strip())
    parts = urlsplit(url)
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page URLs, child sitemap URLs) from sitemap XML."""
    root = ET.fromstring(xml_text.strip())
    is_index = root.tag.endswith("sitemapindex")
    locs = [
        el.text.strip()
        for el in root.iter()
        if el.tag.endswith("loc") and el.text and el.text.strip()
    ]
    return ([], locs) if is_index else (locs, [])


class LocalSource:
    """Audit a folder of HTML files as if it were served from ``base_url``."""

    def __init__(self, root: str | Path, base_url: str):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Not a folder: {root}")
        self.base_url = normalize_url(base_url if base_url.endswith("/") else base_url + "/")

    def _path_for(self, url: str) -> Path | None:
        parts = urlsplit(url)
        if parts.netloc.lower() != urlsplit(self.base_url).netloc:
            return None
        rel = parts.path.lstrip("/")
        candidate = (self.root / rel).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            return None  # never read outside the audited folder
        if parts.path.endswith("/") or candidate.is_dir():
            candidate = candidate / "index.html"
        return candidate if candidate.is_file() else None

    def _url_for(self, path: Path) -> str:
        rel = path.relative_to(self.root).as_posix()
        if rel == "index.html":
            rel = ""
        elif rel.endswith("/index.html"):
            rel = rel[: -len("index.html")]
        return normalize_url(urljoin(self.base_url, rel))

    def seed_urls(self) -> tuple[list[str], bool]:
        """Return (URLs, came_from_sitemap)."""
        sitemap = self.root / "sitemap.xml"
        if sitemap.is_file():
            urls, _children = parse_sitemap(sitemap.read_text(encoding="utf-8"))
            return [normalize_url(u) for u in urls], True
        files = sorted(self.root.rglob("*.html"))
        return [self._url_for(p) for p in files], False

    def get(self, url: str) -> Response:
        url = normalize_url(url)
        path = self._path_for(url)
        if path is None:
            return Response(url, url, 404, error="No file for this URL")
        html = path.read_text(encoding="utf-8", errors="replace")
        return Response(url, url, 200, html=html)

    def status(self, url: str) -> Response:
        """Status only, for link checks. The file is not read."""
        url = normalize_url(url)
        return Response(url, url, 200 if self._path_for(url) else 404)


class HttpSource:
    """Audit a live site. Polite by default: robots.txt, a delay, a clear user agent."""

    def __init__(
        self,
        sitemap_url: str | None = None,
        urls: list[str] | None = None,
        delay: float = 1.0,
        timeout: float = 15.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        import requests  # imported here so local audits work without it

        self.sitemap_url = sitemap_url
        self.urls = urls or []
        self.delay = delay
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                self._wait()
                r = self.session.get(origin + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    parser.parse(r.text.splitlines())
                else:
                    parser = None  # no robots.txt means nothing is disallowed
            except Exception:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(self.user_agent, url)

    def seed_urls(self) -> tuple[list[str], bool]:
        if not self.sitemap_url:
            return [normalize_url(u) for u in self.urls], False
        found: list[str] = []
        queue = [self.sitemap_url]
        seen: set[str] = set()
        while queue:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            self._wait()
            r = self.session.get(sm, timeout=self.timeout)
            r.raise_for_status()
            urls, children = parse_sitemap(r.text)
            found.extend(urls)
            queue.extend(children)
        return list(dict.fromkeys(normalize_url(u) for u in found)), True

    def _request(self, url: str, body: bool) -> Response:
        url = normalize_url(url)
        if not self._allowed(url):
            return Response(url, url, 0, error="Blocked by robots.txt")
        try:
            self._wait()
            # stream=True defers the download, so a status check on a large
            # PDF costs one round trip and no body.
            with self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True) as r:
                content_type = r.headers.get("Content-Type", "")
                html = r.text if body and "html" in content_type.lower() else ""
                return Response(
                    url=url,
                    final_url=normalize_url(r.url),
                    status=r.status_code,
                    redirect_hops=len(r.history),
                    html=html,
                    content_type=content_type,
                )
        except Exception as exc:  # DNS failure, timeout, TLS error, redirect loop
            return Response(url, url, 0, error=f"{type(exc).__name__}: {exc}")

    def get(self, url: str) -> Response:
        return self._request(url, body=True)

    def status(self, url: str) -> Response:
        """Status and final URL only, for link checks."""
        return self._request(url, body=False)
