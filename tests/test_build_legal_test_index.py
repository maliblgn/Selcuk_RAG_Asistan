import pytest

from evaluation.build_legal_test_index import (
    build_article_documents_for_source,
    guard_target_db,
    select_source_items,
    summarize_source,
)


def _item(item_id, source, text, page=1):
    return {
        "id": item_id,
        "source": source,
        "title": "Lisansustu Test",
        "metadata": {
            "source": source,
            "title": "Lisansustu Test",
            "source_type": "web_pdf",
            "doc_type": "yonetmelik",
            "page": page,
        },
        "document": text,
    }


def test_article_document_metadata_fields_are_set():
    source = "https://example.edu.tr/lisansustu.pdf"
    items = [
        _item(1, source, "Tanımlar\nMADDE 4 - (1) AKTS: Avrupa Kredi Transfer Sistemi.", page=1),
        _item(2, source, "Doktora yeterlik sınavı\nMADDE 43 - (1) Yeterlik sınavı.", page=2),
    ]

    docs = build_article_documents_for_source(source, items)

    assert len(docs) == 2
    assert docs[0].metadata["source"] == source
    assert docs[0].metadata["article_no"] == "4"
    assert docs[0].metadata["article_title"] == "Tanımlar"
    assert docs[0].metadata["chunk_type"] == "article"
    assert docs[0].metadata["legal_chunker"] is True
    assert docs[0].metadata["test_index"] is True


def test_guard_target_db_rejects_main_chroma_db():
    with pytest.raises(ValueError):
        guard_target_db("chroma_db")


def test_guard_target_db_allows_legal_test_db():
    target = guard_target_db("chroma_db_legal_test")

    assert target.endswith("chroma_db_legal_test")


def test_summarize_source_report_format():
    source = "https://example.edu.tr/lisansustu.pdf"
    items = [
        _item(1, source, "Tanımlar\nMADDE 4 - (1) Metin.", page=1),
        _item(2, source, "Tez izleme komitesi\nMADDE 44 - (1) Metin.", page=2),
    ]
    docs = build_article_documents_for_source(source, items)

    summary = summarize_source(source, items, docs)

    assert summary["source"] == source
    assert summary["article_count"] == 2
    assert summary["has_article_4"] is True
    assert summary["has_article_43"] is False
    assert summary["has_article_44"] is True


def test_select_source_items_uses_filters(monkeypatch):
    source = "https://example.edu.tr/L%C4%B0SANS%C3%9CST%C3%9C.pdf"

    def fake_read_chroma_items(_source_db):
        return {
            "items": [
                _item(1, source, "MADDE 1 - Amaç"),
                _item(2, "https://example.edu.tr/other.pdf", "MADDE 1 - Amaç"),
            ]
        }

    monkeypatch.setattr("evaluation.build_legal_test_index.read_chroma_items", fake_read_chroma_items)

    selected = select_source_items("fake.sqlite3", source_contains=["LİSANSÜSTÜ"], limit_sources=2)

    assert len(selected) == 1
    assert selected[0][0] == source
