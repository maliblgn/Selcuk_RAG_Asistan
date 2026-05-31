from session_sources.chunker import chunk_text
from session_sources.models import SessionSource, utc_now
from session_sources.session_rag import answer_from_session_source
from session_sources.vector_store import build_session_vector_store


def _store():
    source = SessionSource("s1", "pdf", "Test PDF", "test.pdf", utc_now(), 1, 1, source_label="PDF: Test")
    text = """
    İletişim
    E-posta: test@example.com
    Telefon: +90 555 111 22 33

    Özet
    Aday bilgisayar mühendisliği öğrencisidir. Yapay zeka ve veri analizi projeleri geliştirir.

    Eğitim
    Selçuk Üniversitesi Bilgisayar Mühendisliği. GPA: 3.42

    Projeler
    - Kaynak Analiz Sistemi
    - Takvim Uygulaması

    Diller
    İngilizce: B2

    Başvuru Şartları
    a) Transkript teslim edilir.
    b) Başvuru formu doldurulur.
    """
    chunks = chunk_text("s1", text, metadata={"source_type": "pdf", "page_number": 1}, min_chars=10)
    return build_session_vector_store(source, chunks)


def test_session_rag_answers_from_uploaded_source_with_citation():
    result = answer_from_session_source("Başvuru şartları nelerdir?", _store())

    assert result.status == "answered"
    assert "Transkript" in result.answer
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


def test_session_rag_extracts_email_without_dumping_full_chunk():
    result = answer_from_session_source("mail adresi nedir?", _store())

    assert result.status == "answered"
    assert "test@example.com" in result.answer
    assert "Telefon" not in result.answer
    assert "Projeler" not in result.answer


def test_session_rag_extracts_language_level():
    result = answer_from_session_source("İngilizce seviyesi nedir?", _store())

    assert result.status == "answered"
    assert "B2" in result.answer
    assert "İngilizce" in result.answer or "Ingilizce" in result.answer


def test_session_rag_lists_projects_as_bullets():
    result = answer_from_session_source("projeler nelerdir?", _store())

    assert result.status == "answered"
    assert "- Kaynak Analiz Sistemi" in result.answer
    assert "- Takvim Uygulaması" in result.answer


def test_session_meta_query_does_not_search_uploaded_source():
    result = answer_from_session_source("pdf yükle kısmımız çalışıyor mu?", _store())

    assert result.status == "meta_answer"
    assert "geçici kaynak" in result.answer
