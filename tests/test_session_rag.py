from session_sources.chunker import chunk_text
from session_sources.models import SessionSource, utc_now
from session_sources.session_rag import answer_from_session_source
from session_sources.vector_store import build_session_vector_store


def _store():
    source = SessionSource("s1", "pdf", "Test PDF", "test.pdf", utc_now(), 1, 1, source_label="PDF: Test")
    chunks = chunk_text("s1", "Başvuru ilgili enstitü müdürlüğüne yapılır. Kabul şartları belgede açıklanır. " * 20, metadata={"source_type": "pdf", "page_number": 2})
    return build_session_vector_store(source, chunks)


def test_session_rag_answers_from_uploaded_source_with_citation():
    result = answer_from_session_source("Başvuru nereye yapılır?", _store())

    assert result.status == "answered"
    assert "enstitü" in result.answer
    assert result.citations
    assert "PDF" in result.citations[0]


def test_session_rag_does_not_fallback_to_main_chroma():
    result = answer_from_session_source("Yemekhane menüsü nedir?", _store())

    assert result.status == "no_relevant_context"
    assert "Genel Selçuk kaynaklarında" in result.answer


def test_session_rag_no_active_source_is_safe():
    result = answer_from_session_source("Bu PDF ne hakkında?", None)

    assert result.status == "no_active_source"
    assert "Aktif geçici kaynak yok" in result.answer
