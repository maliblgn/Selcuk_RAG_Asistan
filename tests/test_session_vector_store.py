from session_sources.chunker import chunk_text
from session_sources.models import SessionSource, utc_now
from session_sources.vector_store import build_session_vector_store


def _store():
    source = SessionSource("s1", "pdf", "Test PDF", "test.pdf", utc_now(), 1, 1, source_label="PDF: Test")
    chunks = chunk_text("s1", "Başvuru şartları enstitü müdürlüğüne yapılır. Transkript teslim edilir. " * 20, metadata={"source_type": "pdf", "page_number": 1})
    return build_session_vector_store(source, chunks)


def test_session_vector_store_search_finds_relevant_chunk():
    results = _store().search("Başvuru nereye yapılır?")

    assert results
    assert results[0][1] > 0


def test_session_vector_store_to_documents_has_session_metadata():
    store = _store()
    docs = store.to_documents(store.search("transkript"))

    assert docs
    assert docs[0].metadata["session_source_id"] == "s1"
    assert docs[0].metadata["source_type"] == "pdf"
