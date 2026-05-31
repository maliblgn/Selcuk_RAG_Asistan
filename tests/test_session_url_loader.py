from session_sources.safety import validate_url_safety
from session_sources.models import SessionChunk, SessionSource, utc_now
from session_sources.url_loader import extract_html_text, load_url_source


def test_private_and_unsupported_urls_are_blocked():
    assert not validate_url_safety("file:///tmp/test.txt").ok
    assert not validate_url_safety("http://127.0.0.1:8000").ok
    assert not validate_url_safety("http://localhost:8000").ok


def test_html_text_extraction_removes_script_and_keeps_content():
    title, text = extract_html_text("""
    <html><head><title>Test</title><script>secret()</script></head>
    <body><nav>Menu</nav><h1>Ana Başlık</h1><p>Bu sayfa başvuru şartlarını açıklar.</p></body></html>
    """)

    assert title == "Test"
    assert "secret" not in text
    assert "başvuru şartlarını" in text


class _FakeResponse:
    status_code = 200
    url = "https://example.edu/page"
    headers = {"content-type": "text/html; charset=utf-8"}
    encoding = "utf-8"

    def raise_for_status(self):
        return None

    class raw:
        @staticmethod
        def read(_size, decode_content=True):
            return (
                "<html><title>Duyuru</title><body><h1>Duyuru Başlığı</h1>"
                "<p>Bu sayfa başvuru şartları ve belge teslim sürecini açıklar. "
                "Adaylar gerekli belgeleri belirtilen tarihler arasında sisteme yükler ve "
                "sonuçlar resmi duyuru sayfası üzerinden takip edilir.</p></body></html>"
            ).encode("utf-8")


class _FakePdfResponse:
    status_code = 200
    url = "https://example.edu/docs/form.pdf"
    headers = {"content-type": "application/pdf"}
    encoding = "utf-8"

    def raise_for_status(self):
        return None

    class raw:
        @staticmethod
        def read(_size, decode_content=True):
            return b"%PDF fake content"


def test_load_url_source_success(monkeypatch):
    monkeypatch.setattr("session_sources.url_loader.validate_url_safety", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.validate_final_url", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.robots_allowed", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.requests.get", lambda *a, **k: _FakeResponse())

    result = load_url_source("https://example.edu/page")

    assert result.source.status == "ready"
    assert result.chunks
    assert result.source.source_type == "url"


def test_load_pdf_url_source_success(monkeypatch):
    monkeypatch.setattr("session_sources.url_loader.validate_url_safety", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.validate_final_url", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.robots_allowed", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.requests.get", lambda *a, **k: _FakePdfResponse())

    def _fake_pdf_source(_content, filename):
        source = SessionSource(
            id="pdf1",
            source_type="pdf",
            title=filename,
            original_name_or_url=filename,
            created_at=utc_now(),
            document_count=1,
            chunk_count=1,
            source_label=f"PDF: {filename}",
        )
        chunk = SessionChunk(
            chunk_id="c1",
            source_id="pdf1",
            text="Başvuru formu ve transkript teslim edilir.",
            metadata={"source_type": "pdf", "page_number": 1},
        )
        return source, [chunk]

    monkeypatch.setattr("session_sources.url_loader.build_pdf_session_source", _fake_pdf_source)

    result = load_url_source("https://example.edu/docs/form.pdf")

    assert result.source.status == "ready"
    assert result.source.source_type == "pdf_url"
    assert result.source.original_name_or_url == "https://example.edu/docs/form.pdf"
    assert result.chunks[0].metadata["source_type"] == "pdf_url"
    assert result.chunks[0].metadata["url"] == "https://example.edu/docs/form.pdf"


def test_robots_disallow_returns_user_friendly_error(monkeypatch):
    monkeypatch.setattr("session_sources.url_loader.validate_url_safety", lambda url: type("R", (), {"ok": True, "reason": ""})())
    monkeypatch.setattr("session_sources.url_loader.robots_allowed", lambda url: type("R", (), {"ok": False, "reason": "blocked"})())

    result = load_url_source("https://example.edu/page")

    assert result.source.status == "error"
    assert "robots" in result.source.error_message
