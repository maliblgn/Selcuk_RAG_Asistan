import os
import sys
import types
from unittest.mock import MagicMock


def _make_stub_modules():
    lc_hf = types.ModuleType("langchain_huggingface")
    lc_hf.HuggingFaceEmbeddings = MagicMock()
    sys.modules.setdefault("langchain_huggingface", lc_hf)

    lc_chroma = types.ModuleType("langchain_chroma")
    lc_chroma.Chroma = MagicMock()
    sys.modules.setdefault("langchain_chroma", lc_chroma)

    lc_groq = types.ModuleType("langchain_groq")
    lc_groq.ChatGroq = MagicMock()
    sys.modules.setdefault("langchain_groq", lc_groq)


_make_stub_modules()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag_engine import (  # noqa: E402
    build_safe_fallback,
    classify_query_type,
    ensure_inline_citation,
    filter_relevant_docs,
    is_low_quality_answer,
    prepare_context_and_sources,
    strip_model_generated_sources,
)


class FakeDoc:
    def __init__(self, content, metadata):
        self.page_content = content
        self.metadata = metadata


def test_kutuphane_sorusunda_ftr_relevant_source_olarak_kalmaz():
    docs = [
        FakeDoc(
            "Fizyoterapi klinik uygulama esasları ve devam zorunluluğu.",
            {"title": "FTR Klinik Uygulamalar Yönergesi", "source": "ftr.pdf"},
        ),
        FakeDoc(
            "Kütüphane çalışma saatleri hafta içi 08.30-17.30 arasındadır.",
            {"title": "Kütüphane Yönergesi", "source": "kutuphane.pdf"},
        ),
    ]

    filtered = filter_relevant_docs("Selçuk Üniversitesi kütüphanesinde hangi saatlerde hizmet sunulur?", docs)

    assert [doc.metadata["title"] for doc in filtered] == ["Kütüphane Yönergesi"]


def test_yemekhane_sorusunda_alakasiz_kaynaklar_source_paneline_girmez():
    docs = [
        FakeDoc("Kütüphane kullanım kuralları.", {"title": "Kütüphane Yönergesi", "source": "kutuphane.pdf"}),
        FakeDoc("Klinik uygulama kuralları.", {"title": "FTR Klinik Uygulamalar Yönergesi", "source": "ftr.pdf"}),
        FakeDoc("İş sağlığı ve güvenliği eğitimleri.", {"title": "İş Sağlığı ve Güvenliği Yönergesi", "source": "isg.pdf"}),
    ]

    prepared = prepare_context_and_sources("Selçuk Üniversitesi yemekhane hizmetleri hangi saatlerde sunulur?", docs)

    assert prepared["docs"] == []
    assert prepared["sources"] == []


def test_operational_current_info_relevant_doc_yoksa_safe_fallback_uretilir():
    question = "Selçuk Üniversitesi yemekhane hizmetleri hangi saatlerde sunulur?"

    assert classify_query_type(question) == "operational_current_info"
    assert build_safe_fallback(question, [], "operational_current_info") == (
        "Bu soru güncel operasyonel bilgi gerektiriyor olabilir. "
        "Mevcut yönetmelik/yönerge kaynaklarında açık ve güvenilir saat bilgisi bulunamadı."
    )


def test_strip_model_generated_sources_kaynaklar_blogunu_temizler():
    answer = (
        "AKTS, Avrupa Kredi Transfer Sistemini ifade eder. [1]\n\n"
        "--- KAYNAKLAR ---\n"
        "[1] https://example.com/a.pdf\n"
        "URL: https://example.com/b.pdf"
    )

    assert strip_model_generated_sources(answer) == "AKTS, Avrupa Kredi Transfer Sistemini ifade eder. [1]"


def test_strip_model_generated_sources_inline_citation_korur():
    answer = "Tez izleme komitesi üç öğretim üyesinden oluşur. [1]"

    assert strip_model_generated_sources(answer) == answer


def test_ensure_inline_citation_citation_ekler():
    answer = ensure_inline_citation("AKTS, Avrupa Kredi Transfer Sistemidir.", [{"label": "Kaynak"}])

    assert answer.endswith("[1]")


def test_context_1_ile_source_panel_1_ayni_doca_baglanir():
    docs = [
        FakeDoc(
            "AKTS: Avrupa Kredi Transfer Sistemini ifade eder.",
            {
                "title": "Lisansüstü Eğitim ve Öğretim Yönetmeliği",
                "source": "lisansustu.pdf",
                "article_no": "4",
                "article_title": "Tanımlar",
            },
        )
    ]

    prepared = prepare_context_and_sources("AKTS nedir?", docs)

    assert "[1] Kaynak: Lisansüstü Eğitim ve Öğretim Yönetmeliği" in prepared["context"]
    assert prepared["sources"][0]["label"] == "Lisansüstü Eğitim ve Öğretim Yönetmeliği"
    assert prepared["docs"][0] is docs[0]


def test_long_number_list_low_quality_true_doner():
    answer = "Ders kredisi genellikle " + ", ".join(str(i) for i in range(1, 80))

    assert is_low_quality_answer(answer)


def test_normal_akts_cevabi_low_quality_false_doner():
    answer = "AKTS, Avrupa Kredi Transfer Sistemini ifade eder. [1]"

    assert not is_low_quality_answer(answer)


def test_bilgi_yok_fallbackinde_alakasiz_source_panel_gosterilmez():
    docs = [
        FakeDoc("Kütüphane kullanım kuralları.", {"title": "Kütüphane Yönergesi", "source": "kutuphane.pdf"}),
    ]

    prepared = prepare_context_and_sources("Selçuk Üniversitesi yemekhane hizmetleri hangi saatlerde sunulur?", docs)
    answer = build_safe_fallback("Selçuk Üniversitesi yemekhane hizmetleri hangi saatlerde sunulur?", prepared["docs"], prepared["query_type"])

    assert prepared["sources"] == []
    assert "güvenilir saat bilgisi bulunamadı" in answer
