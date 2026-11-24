"""Live-site behaviour, tested against a small server on localhost:
sitemap index handling, redirects, robots.txt, and link status checks."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import CLEAN_HTML
from webaudit.audit import run_audit
from webaudit.fetch import HttpSource


def html_page(path, extra_link=""):
    html = CLEAN_HTML.replace("https://example.test/checking/", "{base}" + path)
    html = html.replace("Free Checking Accounts | Example CU", f"Page {path} | Example Credit Union")
    html = html.replace("Open a free checking account", f"Details for {path}. Open a free checking account")
    html = html.replace('<a href="/savings/">Savings accounts</a>', f'<a href="/">Home page</a> {extra_link}')
    return html


ROUTES = {
    "/": html_page("/", '<a href="/a/">Page A</a> <a href="/old-b/">Page B</a> <a href="/gone/">Old page</a>'),
    "/a/": html_page("/a/"),
    "/b/": html_page("/b/"),
    "/c/": html_page("/c/"),
    "/private/": html_page("/private/"),
}
REDIRECTS = {"/old-b/": "/b/", "/hop1/": "/hop2/", "/hop2/": "/c/"}
ROBOTS = "User-agent: *\nDisallow: /private/\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
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
        elif path == "/sitemap_index.xml":
            self._send(200, f"<sitemapindex><sitemap><loc>{base}/sitemap-pages.xml</loc></sitemap></sitemapindex>", "application/xml")
        elif path == "/sitemap-pages.xml":
            locs = "".join(f"<url><loc>{base}{p}</loc></url>" for p in ["/", "/a/", "/old-b/", "/hop1/", "/private/"])
            self._send(200, f"<urlset>{locs}</urlset>", "application/xml")
        elif path in REDIRECTS:
            self._send(301, location=REDIRECTS[path])
        elif path in ROUTES:
            self._send(200, ROUTES[path].replace("{base}", base))
        else:
            self._send(404, "<html><title>Not found</title></html>")


@pytest.fixture(scope="module")
def result():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    source = HttpSource(sitemap_url=base + "/sitemap_index.xml", delay=0)
    source.session.trust_env = False  # never route localhost through a proxy
    try:
        yield base, run_audit(source)
    finally:
        server.shutdown()


def found(result):
    base, audit = result
    return {(i.url.removeprefix(base), i.check_id) for i in audit.issues}


def test_sitemap_index_is_followed(result):
    base, audit = result
    assert audit.from_sitemap
    assert [p.url.removeprefix(base) for p in audit.pages] == ["/", "/a/", "/old-b/", "/hop1/", "/private/"]


def test_redirects_are_measured(result):
    base, audit = result
    pages = {p.url.removeprefix(base): p for p in audit.pages}
    assert pages["/old-b/"].redirect_hops == 1
    assert pages["/old-b/"].final_url == base + "/b/"
    assert pages["/hop1/"].redirect_hops == 2
    assert ("/old-b/", "REDIRECT") in found(result)
    assert ("/hop1/", "REDIRECT_CHAIN") in found(result)


def test_robots_txt_is_obeyed_and_reported(result):
    base, audit = result
    private = next(p for p in audit.pages if p.url == base + "/private/")
    assert private.status == 0 and not private.parsed
    assert ("/private/", "ROBOTS_BLOCKED") in found(result)


def test_internal_links_are_checked_even_outside_the_sitemap(result):
    issues = {(u, c): None for u, c in found(result)}
    assert ("/", "BROKEN_INTERNAL_LINK") in issues
    assert ("/", "INTERNAL_LINK_REDIRECT") in issues


def test_no_unexpected_findings(result):
    assert found(result) == {
        ("/old-b/", "REDIRECT"),
        ("/hop1/", "REDIRECT_CHAIN"),
        ("/private/", "ROBOTS_BLOCKED"),
        ("/", "BROKEN_INTERNAL_LINK"),
        ("/", "INTERNAL_LINK_REDIRECT"),
        # /hop1/ ends at /c/, and no page links to either URL.
        ("/hop1/", "ORPHAN_PAGE"),
    }
