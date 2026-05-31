from session_sources.extractors import (
    detect_query_intent,
    extract_email,
    extract_gpa,
    extract_language_levels,
    extract_phone,
    extract_project_titles,
    extract_requirement_items,
)
from session_sources.text_quality import choose_best_page_text, clean_extracted_text, score_extracted_text_quality


def test_text_quality_cleans_common_pdf_mojibake():
    text = clean_extracted_text("Selcuk U�niversitesi I�ngilizce O�ğrenme")

    assert "Üniversitesi" in text
    assert "İngilizce" in text
    assert "Öğrenme" in text


def test_best_page_text_prefers_readable_candidate():
    broken = "U�niversitesi � � �"
    readable = "Selçuk Üniversitesi İngilizce öğrenme çıktıları"

    assert choose_best_page_text([broken, readable]) == readable
    assert score_extracted_text_quality(readable) > score_extracted_text_quality(broken)


def test_targeted_extractors_are_general():
    text = """
    İletişim
    E-posta: aday@example.com
    Telefon: +90 555 111 22 33
    Eğitim
    GPA: 3.42
    Diller
    İngilizce: B2
    Projeler
    - Kaynak Analiz Sistemi
    - Takvim Uygulaması
    Başvuru Şartları
    a) Transkript sunulur.
    b) Başvuru formu doldurulur.
    """

    assert extract_email(text) == ["aday@example.com"]
    assert extract_phone(text) == ["+90 555 111 22 33"]
    assert extract_gpa(text) == ["3.42"]
    assert ("İngilizce", "B2") in extract_language_levels(text)
    assert "Kaynak Analiz Sistemi" in extract_project_titles(text)
    assert "Transkript sunulur." in extract_requirement_items(text)


def test_query_intents_are_not_question_id_based():
    assert detect_query_intent("mail adresi nedir").name == "email"
    assert detect_query_intent("projeler nelerdir").name == "projects"
    assert detect_query_intent("başvuru şartları nelerdir").name == "requirements"
