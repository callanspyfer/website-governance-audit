"""Audit one live page from its address.

This is what the hosted demo calls. Because it fetches whatever address a
visitor types, it is deliberately strict about where it will connect:

* http and https only, on the standard ports
* never to a private, loopback, or link-local address, checked again on every
  redirect hop so a public page cannot bounce the request inside a network
* robots.txt is obeyed
* the response is capped in size and in time
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from .checks import Thresholds, check_page, sort_issues
from .fetch import DEFAULT_USER_AGENT, Response, normalize_url
from .parse import parse_page
from .single import build_result

MAX_REDIRECTS = 5
MAX_BYTES = 2_000_000
MAX_URL_LENGTH = 2000

# Checks that compare pages with each other, so one address is not enough.
NEEDS_A_SITE = (
    "TITLE_DUPLICATE", "META_DESC_DUPLICATE", "BROKEN_INTERNAL_LINK",
    "INTERNAL_LINK_REDIRECT", "ORPHAN_PAGE", "NOINDEX_IN_SITEMAP",
)


class UrlNotAllowed(ValueError):
    """The address is not one this tool will fetch. The message is safe to show."""


def clean_url(raw: str) -> str:
    """Turn what a person typed into a normalized http(s) URL, or refuse it."""
    url = (raw or "").strip()
    if not url:
        raise UrlNotAllowed("Enter a page address, for example https://www.example.org/page/")
    if len(url) > MAX_URL_LENGTH:
        raise UrlNotAllowed("That address is too long.")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise UrlNotAllowed("Only http and https addresses can be audited.")
    if not parts.hostname or "." not in parts.hostname and parts.hostname != "localhost":
        raise UrlNotAllowed("That does not look like a web address.")
    if parts.username or parts.password:
        raise UrlNotAllowed("Addresses that contain a user name or password cannot be audited.")
    return normalize_url(url)


def assert_allowed(url: str, allow_private_hosts: bool = False) -> None:
    """Refuse addresses that are not public web pages."""
    if allow_private_hosts:
        return
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        raise UrlNotAllowed("That address has an invalid port.") from None
    if port not in (None, 80, 443):
        raise UrlNotAllowed("Only pages on the standard web ports can be audited.")
    try:
        resolved = socket.getaddrinfo(parts.hostname, None)
    except (socket.gaierror, UnicodeError):
        raise UrlNotAllowed("That site could not be found. Check the address.") from None
    for info in resolved:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise UrlNotAllowed("That address is not a public web page.")


def _get(session, url, allow_private_hosts, timeout, want_body=True):
    """GET with redirects followed by hand, so every hop is checked first."""
    current, hops = url, 0
    while True:
        assert_allowed(current, allow_private_hosts)
        with session.get(current, timeout=timeout, allow_redirects=False, stream=True) as r:
            location = r.headers.get("Location")
            if r.is_redirect and location:
                hops += 1
                if hops > MAX_REDIRECTS:
                    return Response(url, current, 0, hops, error="Too many redirects")
                current = normalize_url(urljoin(current, location))
                continue
            content_type = r.headers.get("Content-Type", "")
            text = ""
            if want_body:
                body = b""
                for chunk in r.iter_content(65536):
                    body += chunk
                    if len(body) >= MAX_BYTES:
                        break
                text = body[:MAX_BYTES].decode(r.encoding or "utf-8", errors="replace")
            return Response(url, normalize_url(current), r.status_code, hops, text, content_type)


def _robots_allow(session, url, user_agent, allow_private_hosts, timeout) -> bool:
    parts = urlsplit(url)
    try:
        resp = _get(session, f"{parts.scheme}://{parts.netloc}/robots.txt", allow_private_hosts, timeout)
    except Exception:
        return True  # an unreachable robots.txt does not forbid anything
    if resp.status != 200 or not resp.html:
        return True
    parser = RobotFileParser()
    parser.parse(resp.html.splitlines())
    return parser.can_fetch(user_agent, url)


def audit_url(
    url: str,
    grade_target: float = 8.0,
    allow_private_hosts: bool = False,
    timeout: float = 8.0,
    user_agent: str = DEFAULT_USER_AGENT,
    session=None,
) -> dict:
    """Fetch one page and run every check that does not need the rest of the site.

    Raises ``UrlNotAllowed`` for addresses this tool refuses to fetch.
    ``allow_private_hosts`` exists for tests and local development only.
    """
    import requests

    url = clean_url(url)
    assert_allowed(url, allow_private_hosts)
    if session is None:
        session = requests.Session()
    session.headers["User-Agent"] = user_agent

    if not _robots_allow(session, url, user_agent, allow_private_hosts, timeout):
        resp = Response(url, url, 0, error="Blocked by robots.txt")
    else:
        try:
            resp = _get(session, url, allow_private_hosts, timeout)
        except UrlNotAllowed:
            raise
        except requests.RequestException as exc:
            resp = Response(url, url, 0, error=f"{type(exc).__name__}: the site did not respond")
    if resp.status == 200 and not resp.is_html:
        resp.html = ""

    page = parse_page(resp)
    issues = sort_issues(check_page(page, Thresholds(grade_target=grade_target)))
    result = build_result(page, issues, list(NEEDS_A_SITE), url)
    result["fetch"] = {
        "requested_url": url,
        "final_url": resp.final_url,
        "status": resp.status,
        "redirect_hops": resp.redirect_hops,
        "content_type": resp.content_type,
        "audited": page.parsed,
    }
    if resp.status == 200 and not page.parsed:
        result["note"] = "That address did not return an HTML page, so there was nothing to audit."
    return result
