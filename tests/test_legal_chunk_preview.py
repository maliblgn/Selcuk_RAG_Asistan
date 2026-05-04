from legal_chunk_preview import (
    build_page_texts,
    group_items_by_source,
    normalize_for_filter,
    preview_source,
    select_sources,
    source_matches_filters,
)


def _item(item_id, source, document, title="Test", page=None):
    metadata = {"source": source, "title": title, "source_type": "web_pdf", "doc_type": "yonetmelik"}
    if page is not None:
        metadata["page"] = page
    return {
        "id": item_id,
        "source": source,
        "title": title,
        "metadata": metadata,
        "document": document,
    }


def test_source_contains_filter_matches_url_encoded_text():
    source = "https://example.edu.tr/L%C4%B0SANS%C3%9CST%C3%9C.pdf"
    items = [_item(1, source, "MADDE 1 - Amaç")]

    assert source_matches_filters(source, items, source_contains=["LİSANSÜSTÜ"])
    assert source_matches_filters(source, items, source_contains=["L%C4%B0SANS%C3%9CST%C3%9C"])
    assert normalize_for_filter("LİSANSÜSTÜ") == "lisansustu"


def test_source_grouping_groups_by_source():
    items = [
        _item(1, "source-a", "A"),
        _item(2, "source-b", "B"),
        _item(3, "source-a", "C"),
    ]

    grouped = group_items_by_source(items)

    assert set(grouped) == {"source-a", "source-b"}
    assert len(grouped["source-a"]) == 2


def test_select_sources_applies_limit_after_filtering():
    grouped = group_items_by_source([
        _item(1, "https://example.edu.tr/lisansustu-a.pdf", "A"),
        _item(2, "https://example.edu.tr/lisansustu-b.pdf", "B"),
        _item(3, "https://example.edu.tr/other.pdf", "C"),
    ])

    selected = select_sources(grouped, source_contains=["lisansustu"], limit_sources=1)

    assert len(selected) == 1
    assert "lisansustu" in selected[0][0]


def test_page_metadata_builds_ordered_page_texts():
    items = [
        _item(3, "source", "page two later", page=2),
        _item(1, "source", "page one first", page=1),
        _item(2, "source", "page one second", page=1),
    ]

    page_texts = build_page_texts(items)

    assert page_texts == ["page one first\npage one second", "page two later"]


def test_preview_source_extracts_critical_article_summary():
    source = "https://example.edu.tr/lisansustu.pdf"
    items = [
        _item(
            1,
            source,
            "Tanımlar\nMADDE 4 - (1) AKTS: Avrupa Kredi Transfer Sistemi anlamına gelir.",
            title="Lisansüstü Eğitim Yönetmeliği",
            page=1,
        ),
        _item(
            2,
            source,
            "Doktora yeterlik sınavı\nMADDE 43 - (1) Yeterlik sınavı esasları düzenlenir.",
            title="Lisansüstü Eğitim Yönetmeliği",
            page=2,
        ),
        _item(
            3,
            source,
            "Tez izleme komitesi\nMADDE 44 - (1) Tez izleme kuralları düzenlenir.",
            title="Lisansüstü Eğitim Yönetmeliği",
            page=3,
        ),
    ]

    summary = preview_source(source, items)

    assert summary["article_count"] == 3
    assert summary["has_article_4"] is True
    assert summary["has_article_43"] is True
    assert summary["has_article_44"] is True
    assert summary["article_4_title"] == "Tanımlar"
    assert summary["article_4_title_source"] == "preceding_heading"
    assert summary["article_44_title"] == "Tez izleme komitesi"
    assert "AKTS" in summary["article_4_preview"]
    assert "Avrupa Kredi Transfer Sistemi" in summary["article_4_preview"]
    assert summary["article_43_page_start"] == 2
    assert summary["article_44_page_end"] == 3


def test_preview_source_reports_duplicate_before_after():
    source = "https://example.edu.tr/lisansustu.pdf"
    items = [
        _item(1, source, "MADDE 57 - Ortak metin.", page=1),
        _item(2, source, "MADDE 57 - Ortak metin. Devam eden uzun metin.", page=2),
        _item(3, source, "MADDE 58 - Sonraki madde.", page=3),
    ]

    summary = preview_source(source, items)

    assert summary["article_count_before_dedup"] == 3
    assert summary["article_count_after_dedup"] == 2
    assert summary["duplicate_article_numbers_before"] == ["57"]
    assert summary["duplicate_article_numbers_after"] == []
