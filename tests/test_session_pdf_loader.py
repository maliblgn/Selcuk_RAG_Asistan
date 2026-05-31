from pypdf import PdfWriter

from session_sources.pdf_loader import build_pdf_session_source


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, _stream):
        self.pages = [_FakePage("Başvuru şartları ve enstitü bilgisi. " * 20)]


def test_pdf_loader_extracts_text_and_page_metadata(monkeypatch):
    monkeypatch.setattr("session_sources.pdf_loader.PdfReader", _FakeReader)

    source, chunks = build_pdf_session_source(b"%PDF fake", "test.pdf")

    assert source.status == "ready"
    assert source.source_type == "pdf"
    assert chunks
    assert chunks[0].metadata["page_number"] == 1


def test_empty_pdf_returns_meaningful_error():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    import io

    buffer = io.BytesIO()
    writer.write(buffer)

    source, chunks = build_pdf_session_source(buffer.getvalue(), "blank.pdf")

    assert source.status == "error"
    assert chunks == []
    assert "okunabilir metin" in source.error_message
