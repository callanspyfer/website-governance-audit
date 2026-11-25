"""Vercel function: GET /api/audit?url=https://www.example.org/page/

Returns the audit of one live page as JSON. The live demo page calls this.
All of the logic lives in the webaudit package. This file is only the HTTP wrapper.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from webaudit.live import UrlNotAllowed, audit_url  # noqa: E402

# Browsers on these pages may read the response.
ALLOWED_ORIGINS = {
    "https://callanspyfer.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}


def respond(query: str, origin: str = "", **audit_options):
    """Return (status, headers, body) for one request. Kept separate from the
    handler class so it can be tested without a server."""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Vary": "Origin",
    }
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin

    url = (parse_qs(query).get("url") or [""])[0]
    try:
        status, payload = 200, audit_url(url, **audit_options)
    except UrlNotAllowed as exc:
        status, payload = 400, {"error": str(exc)}
    except Exception:
        # Never echo internals to the caller.
        status, payload = 500, {"error": "The audit failed on our side. Try again in a moment."}
    return status, headers, json.dumps(payload).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def _send(self, status, headers, body=b""):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        status, headers, body = respond(urlsplit(self.path).query, self.headers.get("Origin", ""))
        self._send(status, headers, body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        headers = {"Vary": "Origin", "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Max-Age": "86400"}
        if origin in ALLOWED_ORIGINS:
            headers["Access-Control-Allow-Origin"] = origin
        self._send(204, headers)
