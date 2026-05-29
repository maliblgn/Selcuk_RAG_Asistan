from query_router import route_query
from langchain_core.documents import Document

from rag_engine import (
    build_safe_fallback,
    deduplicate_repeated_sentences,
    guard_unsupported_term_equivalence,
)
from source_discovery import build_source_discovery_answer


def test_source_discovery_answer_uses_user_friendly_turkish_text():
    answer = build_source_discovery_answer({
        "topic": "staj",
        "status": "ok",
        "total_matches": 1,
        "sources": [
            {
                "rank": 1,
                "title": "Teknoloji Fakültesi Staj Uygulama Yönergesi",
                "reason": "Başlık/metadata alanında ilgili terimler bulundu",
                "matched_terms": ["staj", "yönerge"],
            }
        ],
    })

    assert "İndekslenmiş kaynaklar" in answer
    assert "ilişkili" in answer
    assert "Eşleşme nedeni" in answer
    assert "Eşleşen terimler" in answer
    assert "mevcut indekslenmiş kaynaklar" in answer
    for broken in ("Indekslenmis", "iliskili", "Eslesme", "Eslesen", "gosterildi"):
        assert broken not in answer


def test_source_discovery_no_match_does_not_fabricate_sources():
    answer = build_source_discovery_answer({
        "topic": "bilinmeyen konu",
        "status": "no_match",
        "total_matches": 0,
        "sources": [],
    })

    assert "kaynak eşleşmesi bulamadım" in answer
    assert "kaynak uydurmadım" in answer
    assert "[1]" not in answer


def test_manual_live_qa_routes_are_preserved():
    assert route_query("Staj yönergesi var mı?").mode == "source_discovery"
    assert route_query("Teknoloji Fakültesi staj kaynakları nelerdir?").mode == "source_discovery"
    assert route_query("Bugün yemekte ne var?").mode == "dynamic_dining_menu"
    assert route_query("AKTS nedir?").mode == "rag"


def test_repeated_sentence_dedupe_preserves_inline_citation():
    answer = (
        "Başvurular ilgili enstitüye yapılır ve belgeler teslim edilir. [1] "
        "Başvurular ilgili enstitüye yapılır ve belgeler teslim edilir. [1] "
        "Adayların koşulları ilgili ilanda belirtilir. [1]"
    )

    cleaned = deduplicate_repeated_sentences(answer)

    assert cleaned.count("Başvurular ilgili enstitüye yapılır") == 1
    assert "[1]" in cleaned
    assert "Adayların koşulları ilgili ilanda belirtilir" in cleaned


def test_safe_fallback_is_explicit_about_not_inventing_information():
    answer = build_safe_fallback("Çift anadal şartları nelerdir?", [], "general_document_question")

    assert "indekslenmiş kaynaklar" in answer
    assert "bilgi uydurmuyorum" in answer


def test_unsupported_term_equivalence_guard_is_cautious_when_one_term_missing():
    docs = [
        Document(
            page_content="GANO, öğrencinin aldığı derslerin ağırlıklı puanları üzerinden hesaplanır.",
            metadata={"title": "Ön Lisans ve Lisans Eğitim Öğretim Yönetmeliği"},
        )
    ]

    answer = guard_unsupported_term_equivalence(
        "GANO ile AGNO aynı şeydir.",
        "GANO ile AGNO aynı şey mi?",
        docs,
    )

    assert "GANO" in answer
    assert "AGNO" in answer
    assert "eşdeğer olduğuna dair açık bir ifade bulamadım" in answer
    assert "aynı şeydir" not in answer
