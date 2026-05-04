from langchain_core.documents import Document

import legal_ingestion


LEGAL_TEXT = """MADDE 1 - Amaç
(1) Bu düzenlemenin amacı test etmektir.

MADDE 2 - Kapsam
(1) Bu düzenleme sentetik testleri kapsar.
"""


def _fallback_factory(calls):
    def fallback(docs):
        calls.append(list(docs))
        return [
            Document(
                page_content=f"fallback:{doc.page_content}",
                metadata=dict(doc.metadata or {}),
            )
            for doc in docs
        ]

    return fallback


def test_legal_chunking_disabled_uses_fallback():
    calls = []
    doc = Document(page_content=LEGAL_TEXT, metadata={"source": "synthetic", "title": "Test"})

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        [doc],
        fallback_splitter_func=_fallback_factory(calls),
        enabled=False,
    )

    assert len(calls) == 1
    assert result[0].page_content.startswith("fallback:")
    assert "article_no" not in result[0].metadata


def test_legal_chunking_enabled_single_document_creates_article_documents():
    calls = []
    doc = Document(
        page_content=LEGAL_TEXT,
        metadata={"source": "synthetic", "title": "Test", "doc_type": "yonetmelik"},
    )

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        [doc],
        fallback_splitter_func=_fallback_factory(calls),
        enabled=True,
    )

    assert calls == []
    assert len(result) == 2
    assert [doc.metadata["article_no"] for doc in result] == ["1", "2"]
    assert all(doc.metadata["chunk_type"] == "article" for doc in result)
    assert all(doc.metadata["legal_chunker"] is True for doc in result)


def test_legal_chunking_enabled_pdf_page_group_preserves_page_bounds():
    calls = []
    docs = [
        Document(
            page_content="MADDE 1 - Amaç\n(1) Birinci madde sayfa 1 metni.",
            metadata={"source": "pdf://test", "source_type": "web_pdf", "page": 1, "title": "PDF Test"},
        ),
        Document(
            page_content="MADDE 2 - Kapsam\n(1) Ikinci madde sayfa 2 metni.",
            metadata={"source": "pdf://test", "source_type": "web_pdf", "page": 2, "title": "PDF Test"},
        ),
    ]

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        docs,
        fallback_splitter_func=_fallback_factory(calls),
        enabled=True,
    )

    assert calls == []
    assert [doc.metadata["article_no"] for doc in result] == ["1", "2"]
    assert result[0].metadata["page_start"] == 1
    assert result[0].metadata["page_end"] == 1
    assert result[1].metadata["page_start"] == 2
    assert result[1].metadata["page_end"] == 2


def test_legal_chunking_enabled_non_legal_text_uses_fallback():
    calls = []
    doc = Document(page_content="Bu normal bir duyuru metnidir.", metadata={"source": "notice"})

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        [doc],
        fallback_splitter_func=_fallback_factory(calls),
        enabled=True,
    )

    assert len(calls) == 1
    assert result[0].page_content.startswith("fallback:")


def test_legal_chunker_exception_falls_back(monkeypatch):
    calls = []
    doc = Document(page_content=LEGAL_TEXT, metadata={"source": "synthetic"})

    def raise_error(*args, **kwargs):
        raise RuntimeError("synthetic legal chunker failure")

    monkeypatch.setattr(legal_ingestion.legal_chunker, "split_text_by_articles", raise_error)

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        [doc],
        fallback_splitter_func=_fallback_factory(calls),
        enabled=True,
    )

    assert len(calls) == 1
    assert result[0].page_content.startswith("fallback:")


def test_article_documents_preserve_source_metadata():
    calls = []
    metadata = {
        "source": "synthetic",
        "title": "Lisansustu Yonetmelik",
        "source_type": "web_pdf",
        "doc_type": "yonetmelik",
        "extraction_method": "unit_test",
    }
    doc = Document(page_content=LEGAL_TEXT, metadata=metadata)

    result = legal_ingestion.split_documents_with_optional_legal_chunking(
        [doc],
        fallback_splitter_func=_fallback_factory(calls),
        enabled=True,
    )

    for key, value in metadata.items():
        assert result[0].metadata[key] == value


def test_legal_chunking_enabled_env_parse(monkeypatch):
    monkeypatch.delenv("LEGAL_CHUNKING_ENABLED", raising=False)
    assert legal_ingestion.legal_chunking_enabled() is False

    for value in ("true", "True", "1", "yes", "on"):
        monkeypatch.setenv("LEGAL_CHUNKING_ENABLED", value)
        assert legal_ingestion.legal_chunking_enabled() is True

    for value in ("false", "0", "no", "off", ""):
        monkeypatch.setenv("LEGAL_CHUNKING_ENABLED", value)
        assert legal_ingestion.legal_chunking_enabled() is False

    monkeypatch.setenv("LEGAL_CHUNKING_ENABLED", "false")
    assert legal_ingestion.legal_chunking_enabled(explicit=True) is True
