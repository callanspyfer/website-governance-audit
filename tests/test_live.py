"""The URL audit and its HTTP wrapper, tested against a server on localhost.

The safety rules get their own tests: by default the tool must refuse to
connect anywhere that is not a public web page.
"""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from conftest import CLEAN_HTML, DEMO_SITE, REPO
from webaudit import live
from webaudit.checks import CHECKS
from webaudit.live import UrlNotAllowed, audit_url, clean_url

PROBLEM_HTML = (DEMO_SITE / "loans" / "auto" / "index.html").read_text(encoding="utf-8")
REDIRECTS = {"/old/": "/clean/", "/hop1/": "/hop2/", "/hop2/": "/clean/", "/to-internal/": "/internal/clean/", "/loop/": "/loop/"}
ROBOTS = "User-agent: *\nDisallow: /private/\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body="", content_type="text/html; charset=utf-8", location=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        path = self.path
        if path == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
        elif path in REDIRECTS:
            self._send(302, location=REDIRECTS[path])
        elif path in ("/clean/", "/private/page/", "/internal/clean/"):
            self._send(200, CLEAN_HTML.replace("https://example.test/checking/", base + path))
        elif path == "/problems/":
            self._send(200, PROBLEM_HTML)
        elif path == "/file.pdf":
            self._send(200, "%PDF-1.7", "application/pdf")
        elif path == "/huge/":
            self._send(200, "<html><body>" + "x" * (live.MAX_BYTES + 500_000))
        else:
            self._send(404, "<html><title>Not found</title></html>")


@pytest.fixture(scope="module")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def audit(url, **options):
    session = requests.Session()
    session.trust_env = False  # never route localhost through a proxy
    return audit_url(url, allow_private_hosts=True, session=session, **options)


def ids(result):
    return [i["check_id"] for i in result["issues"]]


def test_clean_page(site):
    result = audit(site + "/clean/")
    assert result["issues"] == []
    assert result["fetch"] == {
        "requested_url": site + "/clean/", "final_url": site + "/clean/", "status": 200,
        "redirect_hops": 0, "content_type": "text/html; charset=utf-8", "audited": True,
    }
    assert result["checks_run"] + len(result["not_run"]) == len(CHECKS)


def test_problem_page(site):
    result = audit(site + "/problems/")
    assert {"IMG_ALT_MISSING", "LINK_TEXT_EMPTY", "H1_MULTIPLE", "LINK_TEXT_GENERIC"} <= set(ids(result))
    assert result["facts"]["title"] == "Auto Loans | Maplewood Demo Credit Union"


def test_redirects_are_followed_counted_and_reported(site):
    one = audit(site + "/old/")
    assert ids(one) == ["REDIRECT"]
    assert one["fetch"]["redirect_hops"] == 1 and one["fetch"]["final_url"] == site + "/clean/"
    two = audit(site + "/hop1/")
    assert ids(two) == ["REDIRECT_CHAIN"]
    assert two["fetch"]["redirect_hops"] == 2


def test_redirect_loops_stop(site):
    result = audit(site + "/loop/")
    assert ids(result) == ["FETCH_FAILED"]
    assert result["issues"][0]["detail"] == "Too many redirects"


def test_error_status_robots_and_non_html(site):
    assert ids(audit(site + "/missing/")) == ["HTTP_ERROR"]
    blocked = audit(site + "/private/page/")
    assert ids(blocked) == ["ROBOTS_BLOCKED"] and blocked["fetch"]["audited"] is False
    pdf = audit(site + "/file.pdf")
    assert pdf["issues"] == [] and "did not return an HTML page" in pdf["note"]


def test_large_responses_are_cut_off(site):
    result = audit(site + "/huge/")
    assert result["fetch"]["status"] == 200  # truncated, not failed


def test_unreachable_site_is_reported_not_raised():
    result = audit("http://127.0.0.1:9/", timeout=2)
    assert ids(result) == ["FETCH_FAILED"]
    assert "127.0.0.1" not in result["issues"][0]["detail"]  # no connection internals


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/admin", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "http://0.0.0.0/", "http://[::1]/",
    "http://100.64.0.1/", "https://8.8.8.8:8443/", "http://8.8.8.8:22/",
    "file:///etc/passwd", "ftp://8.8.8.8/", "javascript:alert(1)", "https://user:pw@8.8.8.8/", "", "   ",
])
def test_non_public_addresses_are_refused_by_default(url):
    with pytest.raises(UrlNotAllowed):
        audit_url(url)


def test_every_redirect_hop_is_checked(site, monkeypatch):
    # A public-looking page must not be able to redirect the fetch somewhere forbidden.
    def guard(url, allow_private_hosts=False):
        if "/internal/" in url:
            raise UrlNotAllowed("That address is not a public web page.")
    monkeypatch.setattr(live, "assert_allowed", guard)
    with pytest.raises(UrlNotAllowed):
        audit(site + "/to-internal/")


def test_clean_url_accepts_what_people_type():
    assert clean_url("example.org") == "https://example.org/"
    assert clean_url("  HTTPS://Example.org/Page#top ") == "https://example.org/Page"
    with pytest.raises(UrlNotAllowed):
        clean_url("https://" + "a" * 2100 + ".org/")


# ---- the HTTP wrapper deployed to Vercel


def load_api():
    spec = importlib.util.spec_from_file_location("api_audit", REPO / "api" / "audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_returns_the_audit_as_json(site):
    api = load_api()
    session = requests.Session()
    session.trust_env = False
    status, headers, body = api.respond(
        "url=" + site + "/problems/", "https://callanspyfer.github.io",
        allow_private_hosts=True, session=session,
    )
    assert status == 200
    assert headers["Access-Control-Allow-Origin"] == "https://callanspyfer.github.io"
    assert headers["Content-Type"].startswith("application/json")
    assert "IMG_ALT_MISSING" in ids(json.loads(body))


def test_api_refuses_bad_input_with_a_plain_message():
    api = load_api()
    for query in ("", "url=", "url=http://127.0.0.1/", "url=file:///etc/passwd", "other=1"):
        status, headers, body = api.respond(query, "https://callanspyfer.github.io")
        assert status == 400
        assert set(json.loads(body)) == {"error"}


def test_api_only_grants_browser_access_to_known_origins():
    api = load_api()
    _status, headers, _body = api.respond("url=", "https://evil.example")
    assert "Access-Control-Allow-Origin" not in headers


def test_api_hides_internal_errors(monkeypatch):
    api = load_api()
    monkeypatch.setattr(api, "audit_url", lambda *a, **k: 1 / 0)
    status, _headers, body = api.respond("url=https://example.org/")
    assert status == 500
    assert "division" not in body.decode() and "Traceback" not in body.decode()
