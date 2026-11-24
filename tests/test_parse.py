from webaudit.fetch import normalize_url


def test_extracts_core_fields(make_page):
    page = make_page()
    assert page.title == "Free Checking Accounts | Example CU"
    assert page.meta_description.startswith("Open a free checking account")
    assert page.canonical == "https://example.test/checking/"
    assert page.lang == "en"
    assert page.h1s == ["Free checking"]
    assert page.headings == [(1, "Free checking"), (2, "What you get")]
    assert page.jsonld_types == ["Organization"]
    assert not page.noindex


def test_empty_alt_is_valid_but_missing_alt_is_counted(make_page):
    page = make_page('<html lang="en"><body><img src="a.png" alt=""><img src="b.png"></body></html>')
    assert page.images_total == 2
    assert page.images_missing_alt == 1


def test_links_are_resolved_and_classified(make_page):
    html = """<html><body>
      <a href="../savings/#rates">Savings</a>
      <a href="https://other.test/x">Partner</a>
      <a href="mailto:hi@example.test">Email</a>
      <a href="#top">Top</a>
      <a href="/home/"><img src="logo.png" alt="Example CU home"></a>
    </body></html>"""
    page = make_page(html)
    links = {link.href: link for link in page.links}
    assert set(links) == {
        "https://example.test/savings/",
        "https://other.test/x",
        "https://example.test/home/",
    }
    assert links["https://example.test/savings/"].internal
    assert not links["https://other.test/x"].internal
    assert links["https://example.test/home/"].text == "Example CU home"


def test_jsonld_graph_is_flattened_and_bad_json_is_reported(make_page):
    html = """<html><head>
      <script type="application/ld+json">{"@graph": [{"@type": "FAQPage"}, {"@type": ["Organization", "Dentist"]}]}</script>
      <script type="application/ld+json">{"@type": "Organization",}</script>
    </head><body></body></html>"""
    page = make_page(html)
    assert page.jsonld_types == ["FAQPage", "Organization", "Dentist"]
    assert len(page.jsonld_errors) == 1


def test_navigation_and_headings_are_left_out_of_the_reading_score(make_page):
    html = """<html><body>
      <nav>Home Checking Savings Loans Rates About Contact</nav>
      <main><h1>A heading that is not a sentence</h1><p>One short line.</p></main>
      <footer>Copyright notice and legal text.</footer>
    </body></html>"""
    assert make_page(html).readability.words == 3


def test_error_pages_are_not_parsed(make_page):
    page = make_page("<html><title>Not found</title></html>", status=404)
    assert not page.parsed
    assert page.title == ""


def test_normalize_url():
    assert normalize_url("HTTPS://Example.TEST") == "https://example.test/"
    assert normalize_url("https://example.test/a/?b=1#frag") == "https://example.test/a/?b=1"
