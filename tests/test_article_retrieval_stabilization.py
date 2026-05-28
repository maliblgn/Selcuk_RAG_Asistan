from rag_engine import SelcukRAGEngine
from retrieval_rerank import score_result_with_metadata


class _FakeStaticDb:
    def __init__(self, documents, metadatas):
        self._documents = documents
        self._metadatas = metadatas

    def get(self, include=None):
        return {"documents": self._documents, "metadatas": self._metadatas}


def _engine_with_fake_db(documents, metadatas):
    engine = SelcukRAGEngine.__new__(SelcukRAGEngine)
    engine.static_db = _FakeStaticDb(documents, metadatas)
    return engine


def test_acronym_definition_fallback_adds_general_lisansustu_definition_candidate():
    engine = _engine_with_fake_db(
        ["[Madde 4 - Tanımlar] ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını ifade eder."],
        [
            {
                "article_no": "4",
                "article_title": "Tanımlar",
                "source": "Lisansustu Egitim ve Ogretim Yonetmeligi.pdf",
                "title": "Lisansustu Egitim ve Ogretim Yonetmeligi",
            }
        ],
    )

    docs = engine._definition_candidate_fallback_docs("Lisansustu basvurularda ALES neyi ifade eder?")

    assert docs
    assert docs[0].metadata["metadata_fallback"] == "academic_acronym_definition"
    assert docs[0].metadata["article_no"] == "4"


def test_grade_average_fallback_adds_onlisans_lisans_candidate():
    engine = _engine_with_fake_db(
        [
            (
                "[Madde 14 - Not ortalaması] GANO; öğrencinin aldığı bütün derslerin "
                "ağırlıklı puanları toplamının kredi toplamına bölünmesiyle hesaplanır."
            )
        ],
        [
            {
                "article_no": "14",
                "article_title": "Not ortalaması",
                "source": "On Lisans ve Lisans Egitim-Ogretim ve Sinav Yonetmeligi.pdf",
                "title": "On Lisans ve Lisans Egitim-Ogretim ve Sinav Yonetmeligi",
            }
        ],
    )

    docs = engine._definition_candidate_fallback_docs(
        "On lisans ve lisans egitiminde agirlikli genel not ortalamasi nasil tanimlanir?"
    )

    assert docs
    assert docs[0].metadata["metadata_fallback"] == "onlisans_lisans_grade_average"
    assert docs[0].metadata["article_no"] == "14"


def test_broad_lisansustu_regulation_scores_above_narrow_directive_for_ales_definition():
    question = "Lisansustu basvurularda ALES neyi ifade eder?"
    content = "[Madde 4 - Tanımlar] ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını ifade eder."
    broad = {
        "content": content,
        "metadata": {
            "article_no": "4",
            "article_title": "Tanımlar",
            "source": "Lisansustu Egitim ve Ogretim Yonetmeligi.pdf",
            "title": "Lisansustu Egitim ve Ogretim Yonetmeligi",
        },
    }
    narrow = {
        "content": content,
        "metadata": {
            "article_no": "4",
            "article_title": "Tanımlar",
            "source": "Butunlesik Yuksek Lisans Yonergesi.pdf",
            "title": "Butunlesik Yuksek Lisans Yonergesi",
        },
    }

    broad_score = score_result_with_metadata(question, broad)["metadata_score"]
    narrow_score = score_result_with_metadata(question, narrow)["metadata_score"]

    assert broad_score > narrow_score


def test_article_stabilization_has_no_question_id_dependency():
    question = "ALES kisaltmasi lisansustu basvuruda neyi ifade eder?"
    result = {
        "content": "[Madde 4 - Tanımlar] ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını ifade eder.",
        "metadata": {
            "article_no": "4",
            "article_title": "Tanımlar",
            "source": "Lisansustu Egitim ve Ogretim Yonetmeligi.pdf",
            "title": "Lisansustu Egitim ve Ogretim Yonetmeligi",
        },
    }

    scored = score_result_with_metadata(question, result)

    assert scored["metadata_score"] >= 20
    assert "golden_" not in str(scored["rerank_explanation"])
