from pathlib import Path

import pytest

from webaudit.fetch import Response
from webaudit.parse import parse_page

REPO = Path(__file__).resolve().parents[1]
DEMO_SITE = REPO / "examples" / "demo-site"
DEMO_BASE = "https://www.maplewood-demo-cu.test"

BODY = " ".join(["We keep each sentence short and clear so it is easy to read."] * 12)

CLEAN_HTML = f"""<!doctype html>
<html lang="en">
<head>
<title>Free Checking Accounts | Example CU</title>
<meta name="description" content="Open a free checking account with no monthly fee and no minimum balance today.">
<link rel="canonical" href="https://example.test/checking/">
<script type="application/ld+json">
{{"@context": "https://schema.org", "@type": "Organization", "name": "Example CU", "url": "https://example.test/"}}
</script>
</head>
<body>
<nav><a href="/">Home</a></nav>
<main>
<h1>Free checking</h1>
<h2>What you get</h2>
<p>{BODY}</p>
<img src="/a.png" alt="A debit card">
<img src="/divider.png" alt="">
<p><a href="/savings/">Savings accounts</a></p>
</main>
</body>
</html>"""


@pytest.fixture
def make_page():
    """Parse an HTML string as if it had been fetched from ``url``."""

    def _make(html=CLEAN_HTML, url="https://example.test/checking/", in_sitemap=True, **overrides):
        fields = dict(url=url, final_url=url, status=200, html=html)
        fields.update(overrides)
        return parse_page(Response(**fields), in_sitemap=in_sitemap)

    return _make
