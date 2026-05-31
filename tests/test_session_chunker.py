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
