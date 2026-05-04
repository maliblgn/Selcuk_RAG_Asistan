from legal_chunker import (
    ArticleChunk,
    article_chunks_to_documents,
    clean_legal_text,
    deduplicate_articles,
    extract_article_title,
    find_article_starts,
    looks_like_legal_text,
    split_pages_by_articles,
    split_text_by_articles,
)


def test_split_standard_articles_into_two_chunks():
    text = "MADDE 1 - Amaç\nBirinci madde.\n\nMADDE 2 - Kapsam\nİkinci madde."
    chunks = split_text_by_articles(text)
    assert len(chunks) == 2
    assert chunks[0].article_no == "1"
    assert chunks[1].article_no == "2"
    assert chunks[0].content.startswith("MADDE 1 -")


def test_en_dash_article_marker_works():
    text = "MADDE 1 – Amaç\nMetin.\nMADDE 2 – Kapsam\nMetin."
    chunks = split_text_by_articles(text)
    assert [chunk.article_no for chunk in chunks] == ["1", "2"]


def test_compact_parenthesized_article_marker_works():
    text = "MADDE 43-(1) Doktora yeterlik sınavları yapılır.\nMADDE 44 - Sonraki madde."
    chunks = split_text_by_articles(text)
    assert chunks[0].article_no == "43"
    assert chunks[0].article_title == "Doktora yeterlik sınavları yapılır"


def test_sentence_inline_madde_is_not_start():
    text = "MADDE 1 - Amaç\nBu madde kapsamında işlemler yapılır.\nMADDE 2 - Kapsam\nMetin."
    starts = find_article_starts(text)
    assert [match.group(2) for match in starts] == ["1", "2"]


def test_article_title_extracted_from_first_line():
    article_text = "MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır:\nBentler."
    assert (
        extract_article_title(article_text, "43")
        == "Doktora yeterlik sınavları ile ilgili esaslar şunlardır"
    )


def test_page_start_and_page_end_are_estimated():
    pages = [
        "MADDE 1 - Amaç\nBirinci madde sayfa 1'de başlar.",
        "Birinci madde sayfa 2'de devam eder.\nMADDE 2 - Kapsam\nİkinci madde.",
    ]
    chunks = split_pages_by_articles(pages)
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert chunks[1].page_start == 2
    assert chunks[1].page_end == 2


def test_source_metadata_preserved_in_documents():
    chunks = split_text_by_articles("MADDE 1 - Amaç\nMetin.\nMADDE 2 - Kapsam\nMetin.")
    docs = article_chunks_to_documents(chunks, {"source": "test.pdf", "doc_type": "yönetmelik"})
    assert docs[0].metadata["source"] == "test.pdf"
    assert docs[0].metadata["doc_type"] == "yönetmelik"


def test_documents_get_article_metadata():
    chunks = split_text_by_articles("MADDE 1 - Amaç\nMetin.\nMADDE 2 - Kapsam\nMetin.")
    docs = article_chunks_to_documents(chunks)
    assert docs[0].metadata["chunk_type"] == "article"
    assert docs[0].metadata["legal_chunker"] is True
    assert docs[0].metadata["article_no"] == "1"
    assert docs[0].page_content.startswith("[Madde 1 - Amaç]")


def test_looks_like_legal_text_requires_two_articles():
    assert looks_like_legal_text("MADDE 1 - Amaç\nMetin.\nMADDE 2 - Kapsam\nMetin.") is True
    assert looks_like_legal_text("MADDE 1 - Amaç\nTek madde.") is False


def test_article_numbers_remain_strings():
    chunks = split_text_by_articles("madde 5 - Amaç\nMetin.\nMadde 6 - Kapsam\nMetin.")
    assert chunks[0].article_no == "5"
    assert isinstance(chunks[0].article_no, str)


def test_preceding_heading_tanimlar_becomes_article_title():
    text = "Tanımlar\nMADDE 4 - (1) Bu Yönetmelikte geçen; AKTS: Avrupa Kredi Transfer Sistemi.\nMADDE 5 - Esaslar"

    chunks = split_text_by_articles(text)

    assert chunks[0].article_title == "Tanımlar"
    assert chunks[0].title_source == "preceding_heading"


def test_section_heading_is_not_used_when_subheading_exists():
    text = "BİRİNCİ BÖLÜM\nTanımlar\nMADDE 4 - (1) Bu Yönetmelikte geçen kavramlar.\nMADDE 5 - Esaslar"

    chunks = split_text_by_articles(text)

    assert chunks[0].article_title == "Tanımlar"
    assert chunks[0].article_title != "BİRİNCİ BÖLÜM"


def test_sentence_tail_heading_is_preferred_when_heading_shares_line():
    text = "Bu Yönetmelik ilgili maddelere dayanılarak hazırlanmıştır. Tanımlar\nMADDE 4 - (1) Metin.\nMADDE 5 - Esaslar"

    chunks = split_text_by_articles(text)

    assert chunks[0].article_title == "Tanımlar"


def test_long_preceding_sentence_is_rejected_as_heading():
    text = "Bütünleştirilmiş doktora programını on yarıyılda tamamlayamayan öğrenci\nMADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır:\nMetin.\nMADDE 44 - Sonraki"

    chunks = split_text_by_articles(text)

    assert chunks[0].article_title == "Doktora yeterlik sınavları ile ilgili esaslar şunlardır"
    assert chunks[0].title_source == "inline_fallback"


def test_inline_title_fallback_continues_without_preceding_heading():
    text = "MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır:\nMetin.\nMADDE 44 - Sonraki"

    chunks = split_text_by_articles(text)

    assert chunks[0].article_title == "Doktora yeterlik sınavları ile ilgili esaslar şunlardır"
    assert chunks[0].title_source == "inline_fallback"


def test_context_prefix_lines_are_removed_from_content():
    text = "[Bağlam: Test PDF]\nTanımlar\nMADDE 4 - (1) Bu Yönetmelikte geçen kavramlar.\n...[bağlam kısaltıldı]\nMADDE 5 - Esaslar"

    cleaned, changed = clean_legal_text(text)
    chunks = split_text_by_articles(text)

    assert changed is True
    assert "[Bağlam:" not in cleaned
    assert "bağlam kısaltıldı" not in chunks[0].content
    assert chunks[0].clean_context_prefix_applied is True


def test_deduplicate_articles_prefers_longer_containing_content():
    short = ArticleChunk("58", "Kısa", "MADDE 58 - Kısa metin.", 0, 22, page_start=18, page_end=18)
    long = ArticleChunk(
        "58",
        "Kısa",
        "MADDE 58 - Kısa metin. Devam eden daha uzun açıklama.",
        0,
        58,
        page_start=19,
        page_end=20,
    )

    result = deduplicate_articles([short, long])

    assert len(result) == 1
    assert result[0].content == long.content
    assert result[0].duplicate_source_count == 2
    assert result[0].duplicate_warning == "deduplicated_contained_articles"


def test_deduplicate_articles_merges_page_bounds():
    first = ArticleChunk("57", "Başlık", "MADDE 57 - Ortak metin.", 0, 22, page_start=10, page_end=10)
    second = ArticleChunk("57", "Başlık", "MADDE 57 - Ortak metin. Devam.", 0, 30, page_start=11, page_end=12)

    result = deduplicate_articles([first, second])

    assert result[0].page_start == 10
    assert result[0].page_end == 12


def test_article_document_contains_quality_metadata():
    chunks = split_text_by_articles("Tanımlar\nMADDE 4 - (1) Metin.\nMADDE 5 - Esaslar")
    docs = article_chunks_to_documents(chunks)

    assert docs[0].metadata["title_source"] == "preceding_heading"
    assert docs[0].metadata["duplicate_source_count"] == 1
    assert docs[0].metadata["clean_context_prefix_applied"] is False
