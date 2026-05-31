from session_sources.chunker import chunk_page_texts, chunk_text


def test_chunk_text_skips_short_empty_chunks():
    assert chunk_text("s1", "too short", min_chars=80) == []


def test_chunk_text_preserves_metadata():
    chunks = chunk_text("s1", "Başvuru şartları ve kayıt koşulları. " * 40, metadata={"page_number": 2})

    assert chunks
    assert chunks[0].metadata["page_number"] == 2
    assert chunks[0].metadata["chunk_index"] == 0


def test_chunk_page_texts_keeps_page_numbers():
    chunks = chunk_page_texts("s1", [{"page_number": 3, "text": "Lisansüstü başvuru enstitüye yapılır. " * 20}], {"source_type": "pdf"})

    assert chunks
    assert chunks[0].metadata["page_number"] == 3


def test_section_aware_chunking_marks_cv_sections():
    text = """
    İletişim
    E-posta: test@example.com
    Telefon: +90 555 111 22 33

    Projeler
    - Kaynak Analiz Sistemi
    - Takvim Uygulaması

    Diller
    İngilizce: B2
    """
    chunks = chunk_text("s1", text, metadata={"source_type": "pdf", "page_number": 1}, min_chars=10)

    by_section = {chunk.metadata.get("section_type"): chunk for chunk in chunks}
    assert by_section["contact"].metadata["contains_email"]
    assert by_section["projects"].metadata["contains_project_terms"]
    assert by_section["languages"].metadata["contains_language_level"]
