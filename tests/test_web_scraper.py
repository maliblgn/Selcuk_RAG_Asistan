import sys

import pytest
from requests.exceptions import SSLError, Timeout

from web_scraper import (
    ContentCleaner,
    ScraperConfig,
    ScrapingError,
    URLValidator,
    WebScraper,
    parse_urls_from_text,
)


class FakeResponse:
    def __init__(self, text, status_code=200, content=None):
        self.text = text
        self.status_code = status_code
        self.content = content if content is not None else text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, text):
        self._text = text
        self.headers = {}

    def get(self, _url, timeout, verify=True):
        assert timeout > 0
        assert isinstance(verify, bool)
        return FakeResponse(self._text)

    def mount(self, *_args, **_kwargs):
        return None


class TimeoutThenSuccessSession(FakeSession):
    def __init__(self, text, fail_count=2):
        super().__init__(text)
        self.fail_count = fail_count
        self.call_count = 0

    def get(self, _url, timeout, verify=True):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise Timeout("simulated timeout")
        return super().get(_url, timeout, verify)


class SSLThenSuccessSession(FakeSession):
    def __init__(self, text):
        super().__init__(text)
        self.call_count = 0

    def get(self, _url, timeout, verify=True):
        self.call_count += 1
        if self.call_count == 1 and verify is True:
            raise SSLError("certificate verify failed")
        return super().get(_url, timeout, verify)


def test_parse_urls_from_text_deduplicate_and_skip_comments():
    text = """
    # yorum
    https://www.selcuk.edu.tr/a
    https://www.selcuk.edu.tr/a

    https://www.selcuk.edu.tr/b
    """
    urls = parse_urls_from_text(text)
    assert urls == [
        "https://www.selcuk.edu.tr/a",
        "https://www.selcuk.edu.tr/b",
    ]


def test_clean_html_text_removes_script_and_style():
    html = """
    <html><head><style>.x{}</style><script>alert('x')</script></head>
    <body><h1>Baslik</h1><p>Govde</p></body></html>
    """
    cleaned = ContentCleaner.clean_html_text(html)
    assert "alert" not in cleaned
    assert "Baslik" in cleaned
    assert "Govde" in cleaned


def test_url_validator_domain_whitelist():
    assert URLValidator.is_allowed_domain("https://www.selcuk.edu.tr/x", ["selcuk.edu.tr"])
    assert not URLValidator.is_allowed_domain("https://example.com/x", ["selcuk.edu.tr"])


def test_split_url_and_selector_parsing():
    url, selector = URLValidator.split_url_and_selector("https://www.selcuk.edu.tr/page|css=.menu")
    assert url == "https://www.selcuk.edu.tr/page"
    assert selector == ".menu"


def test_scrape_url_rejects_outside_domain_when_whitelist_enabled():
    scraper = WebScraper(
        ScraperConfig(allowed_domains=("selcuk.edu.tr",), enable_domain_whitelist=True),
        session=FakeSession("<html>x</html>"),
    )
    with pytest.raises(ScrapingError):
        scraper.scrape_url("https://example.com/policy")


def test_scrape_url_allows_outside_domain_when_whitelist_disabled(monkeypatch):
    html = """
    <html><head><title>Public Site</title></head>
    <body><h1>Policy</h1><p>""" + ("A" * 400) + """</p></body></html>
    """
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    scraper = WebScraper(
        ScraperConfig(allowed_domains=("selcuk.edu.tr",), enable_domain_whitelist=False),
        session=FakeSession(html),
    )

    doc = scraper.scrape_url("https://example.com/policy")
    assert "Policy" in doc.page_content
    assert doc.metadata["source"] == "https://example.com/policy"


def test_scrape_url_rejects_robots(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: False)
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession("<html>x</html>"))
    with pytest.raises(ScrapingError):
        scraper.scrape_url("https://www.selcuk.edu.tr/policy")


def test_scrape_url_success(monkeypatch):
    html = """
    <html><head><title>Test Sayfasi</title></head>
    <body><h1>Yonetmelik</h1><p>""" + ("A" * 400) + """</p></body></html>
    """
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession(html))

    doc = scraper.scrape_url("https://www.selcuk.edu.tr/test")
    assert "Yonetmelik" in doc.page_content
    assert doc.metadata["source"] == "https://www.selcuk.edu.tr/test"
    assert doc.metadata["source_type"] == "web_page"


def test_scrape_urls_collects_errors(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",), min_content_chars=350), session=FakeSession("<html>kisa</html>"))

    docs, errors = scraper.scrape_urls([
        "https://www.selcuk.edu.tr/ok",
        "https://example.com/outside",
    ])
    assert docs == []
    assert len(errors) == 2


def test_extract_pdf_links_supports_relative_and_absolute():
    html = """
    <html><body>
      <a href="/docs/a.pdf">A</a>
      <a href="https://webadmin.selcuk.edu.tr/files/b.pdf">B</a>
      <a href="/docs/a.pdf">A tekrar</a>
      <a href="/docs/not-txt.txt">TXT</a>
    </body></html>
    """
    links = WebScraper.extract_pdf_links(html, "https://www.selcuk.edu.tr/liste")
    assert links == [
        "https://www.selcuk.edu.tr/docs/a.pdf",
        "https://webadmin.selcuk.edu.tr/files/b.pdf",
    ]


def test_extract_pdf_links_encodes_turkish_and_spaces():
    html = """
    <html><body>
      <a href="https://webadmin.selcuk.edu.tr/uploads/contents/main/icerik/2448/Burs Yönergesi 2021.pdf">Burs</a>
      <a href="/contents/main/icerik/2448/Çift Ana Dal Yönergesi.pdf">ÇAP</a>
    </body></html>
    """
    links = WebScraper.extract_pdf_links(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert links == [
        "https://webadmin.selcuk.edu.tr/uploads/contents/main/icerik/2448/Burs%20Y%C3%B6nergesi%202021.pdf",
        "https://selcuk.edu.tr/contents/main/icerik/2448/%C3%87ift%20Ana%20Dal%20Y%C3%B6nergesi.pdf",
    ]


def test_extract_pdf_link_inventory_uses_anchor_text():
    html = """
    <html><body>
      <a href="https://webadmin.selcuk.edu.tr/files/staj.pdf">Staj Yönergesi</a>
    </body></html>
    """
    links = WebScraper.extract_pdf_link_inventory(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert links == [
        {
            "title": "Staj Yönergesi",
            "url": "https://webadmin.selcuk.edu.tr/files/staj.pdf",
            "normalized_url": "https://webadmin.selcuk.edu.tr/files/staj.pdf",
            "domain": "webadmin.selcuk.edu.tr",
            "source_page": "https://selcuk.edu.tr/anasayfa/detay/39874",
        }
    ]


def test_extract_pdf_link_inventory_relative_url_absolute():
    html = '<html><body><a href="/uploads/burs.pdf">Burs</a></body></html>'
    links = WebScraper.extract_pdf_link_inventory(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert links[0]["url"] == "https://selcuk.edu.tr/uploads/burs.pdf"
    assert links[0]["normalized_url"] == "https://selcuk.edu.tr/uploads/burs.pdf"
    assert links[0]["domain"] == "selcuk.edu.tr"


def test_extract_pdf_link_inventory_title_from_filename_when_anchor_empty():
    html = """
    <html><body>
      <a href="/uploads/%C3%87ift%20Ana%20Dal%20Y%C3%B6nergesi_638315843142205508.pdf"></a>
    </body></html>
    """
    links = WebScraper.extract_pdf_link_inventory(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert links[0]["title"] == "Çift Ana Dal Yönergesi"


def test_extract_pdf_link_inventory_deduplicates_normalized_pdf_links():
    html = """
    <html><body>
      <a href="/uploads/a.pdf">A</a>
      <a href="https://selcuk.edu.tr/uploads/a.pdf">A tekrar</a>
    </body></html>
    """
    links = WebScraper.extract_pdf_link_inventory(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert len(links) == 1
    assert links[0]["title"] == "A"


def test_extract_pdf_link_inventory_ignores_non_pdf_links():
    html = """
    <html><body>
      <a href="/uploads/a.docx">DOCX</a>
      <a href="/uploads/page.html">HTML</a>
      <a href="/uploads/a.pdf">PDF</a>
    </body></html>
    """
    links = WebScraper.extract_pdf_link_inventory(html, "https://selcuk.edu.tr/anasayfa/detay/39874")
    assert len(links) == 1
    assert links[0]["normalized_url"] == "https://selcuk.edu.tr/uploads/a.pdf"


def test_scrape_urls_with_linked_pdfs_uses_page_flow(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)

    def fake_page_flow(self, page_url):
        return ["doc-from-page"], [f"warn-{page_url}"]

    monkeypatch.setattr(WebScraper, "scrape_page_linked_pdfs", fake_page_flow)

    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession("<html>x</html>"))
    docs, errors = scraper.scrape_urls_with_linked_pdfs(["https://www.selcuk.edu.tr/list"], include_page_text=False)
    assert docs == ["doc-from-page"]
    assert errors == ["warn-https://www.selcuk.edu.tr/list"]


def test_scrape_urls_with_linked_pdfs_direct_pdf(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(WebScraper, "_pdf_url_to_documents", lambda self, _url: ["pdf-doc"])

    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession("<html>x</html>"))
    docs, errors = scraper.scrape_urls_with_linked_pdfs(["https://www.selcuk.edu.tr/dokuman.pdf"])
    assert docs == ["pdf-doc"]
    assert errors == []


def test_scrape_urls_with_linked_pdfs_rejects_outside_pdf_when_whitelist_enabled():
    scraper = WebScraper(
        ScraperConfig(allowed_domains=("selcuk.edu.tr",), enable_domain_whitelist=True),
        session=FakeSession("<html>x</html>"),
    )
    docs, errors = scraper.scrape_urls_with_linked_pdfs(["https://example.com/dokuman.pdf"])

    assert docs == []
    assert len(errors) == 1
    assert "Whitelist disi PDF domaini" in errors[0]


def test_scrape_urls_with_non_pdf_page_still_returns_content(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    html = "<html><body><main>" + ("Yemekhane menusu " * 30) + "</main></body></html>"
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession(html))

    docs, errors = scraper.scrape_urls_with_linked_pdfs(["https://www.selcuk.edu.tr/yemekhane"])
    assert len(docs) >= 1
    assert any(doc.metadata.get("source_type") == "web_page" for doc in docs)
    assert errors == []


def test_scrape_url_with_selector(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    html = (
        "<html><body>"
        "<div class='menu'>" + ("Yemek " * 40) + "</div>"
        "<div class='noise'>" + ("Gurultu " * 2) + "</div>"
        "</body></html>"
    )
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession(html))
    doc = scraper.scrape_url("https://www.selcuk.edu.tr/yemekhane|css=.menu")

    assert "Yemek" in doc.page_content
    assert doc.metadata.get("selector") == ".menu"


def test_scraper_config_from_env(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST", "true")
    monkeypatch.setenv("WEB_SCRAPER_ALLOWED_DOMAINS", "selcuk.edu.tr, webadmin.selcuk.edu.tr")
    monkeypatch.setenv("WEB_SCRAPER_VERIFY_SSL", "false")
    monkeypatch.setenv("WEB_SCRAPER_TIMEOUT_SEC", "15")

    cfg = ScraperConfig.from_env()
    assert cfg.enable_domain_whitelist is True
    assert cfg.allowed_domains == ("selcuk.edu.tr", "webadmin.selcuk.edu.tr")
    assert cfg.verify_ssl is False
    assert cfg.timeout_sec == 15


def test_request_retry_on_timeout(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    session = TimeoutThenSuccessSession("<html><body>" + ("A" * 600) + "</body></html>", fail_count=2)
    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",), max_retries=3), session=session)

    doc = scraper.scrape_url("https://www.selcuk.edu.tr/test")
    assert "A" in doc.page_content
    assert session.call_count == 3


def test_request_ssl_fallback_to_insecure(monkeypatch):
    monkeypatch.setattr(URLValidator, "is_allowed_by_robots", lambda *_args, **_kwargs: True)
    html = "<html><body>" + ("A" * 600) + "</body></html>"
    session = SSLThenSuccessSession(html)
    scraper = WebScraper(
        ScraperConfig(
            allowed_domains=("selcuk.edu.tr",),
            verify_ssl=True,
            allow_insecure_ssl_fallback=True,
            max_retries=3,
        ),
        session=session,
    )

    doc = scraper.scrape_url("https://www.selcuk.edu.tr/test")
    assert "A" in doc.page_content
    assert session.call_count == 2


def test_extract_text_from_pdf_ocr_fallback(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "kisa"

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage()]

    class FakePdf2ImageModule:
        @staticmethod
        def convert_from_bytes(_content):
            return [object()]

    class FakeTesseractModule:
        @staticmethod
        def image_to_string(_image, lang="eng"):
            assert lang == "tur"
            return "B" * 220

    monkeypatch.setattr("web_scraper.PdfReader", FakeReader)
    monkeypatch.setitem(sys.modules, "pdf2image", FakePdf2ImageModule)
    monkeypatch.setitem(sys.modules, "pytesseract", FakeTesseractModule)

    scraper = WebScraper(ScraperConfig(allowed_domains=("selcuk.edu.tr",)), session=FakeSession("<html>x</html>"))
    page_texts, method = scraper.extract_text_from_pdf(b"fake-pdf", "https://www.selcuk.edu.tr/test.pdf")
    assert method == "ocr"
    assert len("\n".join(page_texts).strip()) >= 100
