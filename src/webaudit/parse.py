"""Turn one HTML response into the facts the checks need."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .fetch import Response, normalize_url
from .readability import Readability, score

_WS = re.compile(r"\s+")
_BOILERPLATE = ("script", "style", "noscript", "template", "nav", "header", "footer", "aside", "form")
_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def _clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


@dataclass
class Link:
    href: str  # absolute, normalized
    text: str  # visible text, or the alt text of a linked image
    internal: bool


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    redirect_hops: int = 0
    error: str = ""
    in_sitemap: bool = False
    parsed: bool = False  # True when HTML was available and parsed

    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    robots_meta: str = ""
    lang: str = ""
    h1s: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)
    images_total: int = 0
    images_missing_alt: int = 0
    links: list[Link] = field(default_factory=list)
    readability: Readability = field(default_factory=lambda: Readability(0, 0, 0, None))
    jsonld: list[dict] = field(default_factory=list)  # flattened schema.org nodes
    jsonld_errors: list[str] = field(default_factory=list)

    @property
    def noindex(self) -> bool:
        return "noindex" in self.robots_meta.lower()

    @property
    def jsonld_types(self) -> list[str]:
        types: list[str] = []
        for node in self.jsonld:
            t = node.get("@type")
            for name in t if isinstance(t, list) else [t]:
                if isinstance(name, str) and name not in types:
                    types.append(name)
        return types


def _flatten_jsonld(data) -> list[dict]:
    """Return every top-level node, including nodes inside @graph."""
    nodes: list[dict] = []
    if isinstance(data, list):
        for item in data:
            nodes.extend(_flatten_jsonld(item))
    elif isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                nodes.extend(_flatten_jsonld(item))
        else:
            nodes.append(data)
    return nodes


def _body_text(soup: BeautifulSoup) -> str:
    """Body copy: <main>, then <article>, then <body>, minus boilerplate and headings."""
    root = soup.find("main") or soup.find("article") or soup.body or soup
    # Work on a copy so removing boilerplate does not affect link or heading extraction.
    root = BeautifulSoup(str(root), "html.parser")
    # Headings are labels, not prose. Counting each one as a short sentence
    # would make every page look easier to read than its paragraphs are.
    for tag in root.find_all(list(_BOILERPLATE + _HEADINGS)):
        tag.decompose()
    # Block elements become sentence boundaries so list items and table cells
    # without a full stop are not glued to the next sentence.
    for tag in root.find_all(["li", "p", "td", "th", "dt", "dd"]):
        text = _clean(tag.get_text(" "))
        if text and text[-1] not in ".!?":
            tag.append(".")
    return _clean(root.get_text(" "))


def parse_page(resp: Response, in_sitemap: bool = False) -> Page:
    page = Page(
        url=resp.url,
        final_url=resp.final_url,
        status=resp.status,
        redirect_hops=resp.redirect_hops,
        error=resp.error,
        in_sitemap=in_sitemap,
    )
    if resp.status != 200 or not resp.html:
        return page

    soup = BeautifulSoup(resp.html, "html.parser")
    page.parsed = True
    base = resp.final_url
    host = urlsplit(base).netloc.lower()

    html_tag = soup.find("html")
    page.lang = _clean(html_tag.get("lang")) if html_tag else ""

    if soup.title:
        page.title = _clean(soup.title.get_text())

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "description" and not page.meta_description:
            page.meta_description = _clean(meta.get("content"))
        elif name == "robots":
            page.robots_meta = _clean(meta.get("content"))

    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel = rel if isinstance(rel, list) else [rel]
        if "canonical" in [r.lower() for r in rel] and link.get("href"):
            page.canonical = normalize_url(urljoin(base, link["href"]))
            break

    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        level = int(tag.name[1])
        text = _clean(tag.get_text(" "))
        page.headings.append((level, text))
        if level == 1:
            page.h1s.append(text)

    for img in soup.find_all("img"):
        page.images_total += 1
        # alt="" is valid for decorative images. A missing alt attribute is not.
        if img.get("alt") is None:
            page.images_missing_alt += 1

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absolute = normalize_url(urljoin(base, href))
        if urlsplit(absolute).scheme not in ("http", "https"):
            continue
        text = _clean(a.get_text(" "))
        if not text:
            img = a.find("img")
            text = _clean(img.get("alt")) if img else ""
        if not text:
            text = _clean(a.get("aria-label"))
        page.links.append(Link(absolute, text, urlsplit(absolute).netloc.lower() == host))

    for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            page.jsonld.extend(_flatten_jsonld(json.loads(raw)))
        except json.JSONDecodeError as exc:
            page.jsonld_errors.append(f"line {exc.lineno}, column {exc.colno}: {exc.msg}")

    page.readability = score(_body_text(soup))
    return page
