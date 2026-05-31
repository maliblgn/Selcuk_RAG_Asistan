from session_sources.chunker import chunk_text
from session_sources.models import SessionSource, utc_now
from session_sources.vector_store import build_session_vector_store


def _store():
    source = SessionSource("s1", "pdf", "Test PDF", "test.pdf", utc_now(), 1, 1, source_label="PDF: Test")
    text = """
    İletişim
    E-posta: test@example.com

    Diller
    İngilizce: B2

    Projeler
    - Kaynak Analiz Sistemi
    - Takvim Uygulaması

    Başvuru Şartları
    a) Transkript teslim edilir.
    b) Başvuru formu doldurulur.
    """
    chunks = chunk_text("s1", text, metadata={"source_type": "pdf", "page_number": 1}, min_chars=10)
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


def test_intent_metadata_boosts_target_specific_chunks():
    store = _store()

    assert store.search("mail adresi nedir?")[0][0].metadata["section_type"] == "contact"
    assert store.search("İngilizce seviyesi nedir?")[0][0].metadata["section_type"] == "languages"
    assert store.search("projeler nelerdir?")[0][0].metadata["section_type"] == "projects"
