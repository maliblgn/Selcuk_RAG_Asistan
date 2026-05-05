from evaluation.retrieval_rerank import (
    detect_query_intent,
    legal_safe_query_allowed,
    rerank_results,
    score_result_with_metadata,
)


def _result(article_no, title, content, score=1.0):
    return {
        "content": content,
        "score": score,
        "metadata": {
            "article_no": article_no,
            "article_title": title,
        },
    }


def test_detect_query_intent_definition_phrase():
    intent = detect_query_intent("Bu kavram ne anlama gelir?")

    assert intent["intent"] == "definition"


def test_detect_query_intent_acronym_terms():
    intent = detect_query_intent("AKTS kısaltması hangi sistemin adıdır?")

    assert "AKTS" in intent["acronym_terms"]


def test_definition_intent_tanimlar_boosts_score():
    result = _result("4", "Tanımlar", "MADDE 4 - AKTS: Avrupa Kredi Transfer Sistemi.")

    scored = score_result_with_metadata("AKTS kısaltması hangi sistemin adıdır?", result, base_score=1.0)

    assert scored["rerank_score"] > 10
    assert any(item["reason"] == "definition_intent_title_tanimlar" for item in scored["rerank_explanation"])


def test_acronym_colon_result_scores_above_plain_acronym():
    question = "AKTS kısaltması hangi sistemin adıdır?"
    with_colon = _result("4", "Tanımlar", "AKTS: Avrupa Kredi Transfer Sistemi.")
    without_colon = _result("12", "Yatay geçiş", "AKTS ders transferinde geçer.")

    score_with = score_result_with_metadata(question, with_colon, base_score=1.0)["rerank_score"]
    score_without = score_result_with_metadata(question, without_colon, base_score=1.0)["rerank_score"]

    assert score_with > score_without


def test_deadline_question_does_not_get_definition_tanimlar_boost():
    question = "Doktora öğrencisi yeterlik sınavına ne zaman girer?"
    result = _result("4", "Tanımlar", "MADDE 4 - Tanımlar.")

    scored = score_result_with_metadata(question, result, base_score=1.0)

    assert scored["intent"] == "deadline"
    assert not any(item["reason"] == "definition_intent_title_tanimlar" for item in scored["rerank_explanation"])


def test_rerank_order_changes_expected_way():
    question = "AKTS kısaltması hangi sistemin adıdır?"
    results = [
        _result("12", "Yatay geçiş yoluyla öğrenci kabulü", "AKTS ders transferinde geçer.", score=5.0),
        _result("4", "Tanımlar", "AKTS: Avrupa Kredi Transfer Sistemi.", score=1.0),
    ]

    reranked = rerank_results(question, results)

    assert reranked[0]["metadata"]["article_no"] == "4"


def test_acronym_colon_generalizes_to_ales_and_dus():
    ales = _result("4", "Tanımlar", "ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavı.")
    dus = _result("4", "Tanımlar", "DUS: Diş Hekimliğinde Uzmanlık Sınavı.")

    assert score_result_with_metadata("ALES ne demektir?", ales, base_score=1.0)["rerank_score"] > 10
    assert score_result_with_metadata("DUS ne demektir?", dus, base_score=1.0)["rerank_score"] > 10


def test_purpose_question_detects_purpose_and_does_not_boost_tanimlar():
    intent = detect_query_intent("Tezli yüksek lisans programının amacı nedir?")
    tanimlar = _result("4", "Tanımlar", "MADDE 4 - Tanımlar.", score=10.0)

    scored = score_result_with_metadata("Tezli yüksek lisans programının amacı nedir?", tanimlar, base_score=10.0)

    assert intent["intent"] == "purpose"
    assert not any(item["reason"] == "definition_intent_title_tanimlar" for item in scored["rerank_explanation"])
    assert any(item["reason"] == "purpose_intent_tanimlar_penalty" for item in scored["rerank_explanation"])


def test_purpose_intent_title_amac_gets_boost():
    amac = _result("24", "Amaç", "Tezli yüksek lisans programının amacı bilimsel araştırma yapmaktır.")

    scored = score_result_with_metadata("Tezli yüksek lisans programının amacı nedir?", amac, base_score=1.0)

    assert any(item["reason"] == "purpose_intent_title_amac" for item in scored["rerank_explanation"])
    assert scored["rerank_score"] > 10


def test_acronym_definition_boost_is_preserved_for_akts():
    result = _result("4", "Tanımlar", "AKTS: Avrupa Kredi Transfer Sistemi.")

    scored = score_result_with_metadata("AKTS kısaltması hangi sistemin adıdır?", result, base_score=1.0)

    assert scored["intent"] == "definition"
    assert scored["acronym_terms"] == ["AKTS"]
    assert any(item["reason"] == "definition_intent_title_tanimlar" for item in scored["rerank_explanation"])
    assert any(item["reason"] == "acronym_colon_AKTS" for item in scored["rerank_explanation"])


def test_tez_onerisi_phrase_overlap_gets_boost():
    result = _result("45", "Tez önerisi savunması", "Tez önerisi altı ay içinde savunulur.")

    scored = score_result_with_metadata("Tez önerisi ne kadar süre içinde savunulmalıdır?", result, base_score=1.0)

    assert any(
        item["reason"] == "title_query_phrase_overlap_tez_onerisi"
        for item in scored["rerank_explanation"]
    )


def test_tez_savunma_jurisi_content_overlap_gets_boost():
    result = _result("29", "Yüksek lisans tezinin sonuçlanması", "Tez jürisi enstitü yönetim kurulu tarafından oluşturulur.")

    scored = score_result_with_metadata("Tez savunma jürisi nasıl oluşturulur?", result, base_score=1.0)

    assert any(
        item["reason"] == "content_query_phrase_overlap_tez_jurisi"
        for item in scored["rerank_explanation"]
    )


def test_non_definition_question_does_not_auto_boost_article_4():
    result = _result("4", "Tanımlar", "MADDE 4 - Tanımlar.", score=1.0)

    scored = score_result_with_metadata("Tez önerisi ne kadar süre içinde savunulmalıdır?", result, base_score=1.0)

    assert scored["intent"] == "deadline"
    assert not any(item["reason"] == "definition_intent_article_4" for item in scored["rerank_explanation"])


def test_legal_safe_mode_filters_lost_critical_term():
    original = "Tez izleme komitesi kaç öğretim üyesinden oluşur?"

    assert not legal_safe_query_allowed(original, "Tez danışmanlık komitesi kaç kişiden oluşur?")
    assert not legal_safe_query_allowed(original, "Tez savunma komitesi kaç kişiden oluşur?")
    assert legal_safe_query_allowed(original, "Tez izleme komitesi üye sayısı nedir?")


def test_tez_izleme_article_44_scores_first():
    question = "tez izleme komitesi kaç öğretim üyesinden oluşur"
    results = [
        _result("45", "Tez önerisi savunması", "Tez önerisi savunması yapılır.", score=10.0),
        _result(
            "44",
            "Tez izleme komitesi",
            "MADDE 44 - Tez izleme komitesi üç öğretim üyesinden oluşur.",
            score=1.0,
        ),
    ]

    reranked = rerank_results(question, results)

    assert reranked[0]["metadata"]["article_no"] == "44"


def test_doktora_yeterlik_article_43_scores_first():
    question = "doktora yeterlik sınavları ile ilgili esaslar nelerdir"
    results = [
        _result("44", "Tez izleme komitesi", "Tez izleme komitesi esasları.", score=8.0),
        _result("43", "Doktora yeterlik sınavı", "Doktora yeterlik sınavları ile ilgili esaslar.", score=1.0),
    ]

    reranked = rerank_results(question, results)

    assert reranked[0]["metadata"]["article_no"] == "43"


def test_akts_article_4_tanimlar_scores_first():
    question = "AKTS nedir?"
    results = [
        _result("12", "Ders yükü", "AKTS ders yükünü gösterir.", score=8.0),
        _result("4", "Tanımlar", "AKTS: Avrupa Kredi Transfer Sistemi ifade eder.", score=1.0),
    ]

    reranked = rerank_results(question, results)

    assert reranked[0]["metadata"]["article_no"] == "4"


def test_akts_prefers_lisansustu_definition_over_narrow_staj_source():
    question = "AKTS nedir?"
    results = [
        {
            "content": "AKTS ders yükünü gösterir.",
            "score": 10.0,
            "metadata": {
                "article_no": "4",
                "article_title": "Tanımlar",
                "title": "Selcuk_Universitesi_Fen_Fakultesi_Staj_Yonergesi",
                "source": "Fen_Fakultesi_Staj_Yonergesi.pdf",
            },
        },
        {
            "content": "AKTS: Avrupa Kredi Transfer Sistemini ifade eder.",
            "score": 1.0,
            "metadata": {
                "article_no": "4",
                "article_title": "Tanımlar",
                "title": "Lisansüstü Eğitim ve Öğretim Yönetmeliği",
                "source": "Lisansustu_Egitim_ve_Ogretim_Yonetmeligi.pdf",
            },
        },
    ]

    reranked = rerank_results(question, results)

    assert "Lisansüstü" in reranked[0]["metadata"]["title"]


def test_akts_source_specific_query_can_boost_matching_unit_source():
    question = "Fen Fakültesi staj yönergesinde AKTS nedir?"
    results = [
        {
            "content": "AKTS ders yükünü gösterir.",
            "score": 1.0,
            "metadata": {
                "article_no": "4",
                "article_title": "Tanımlar",
                "title": "Selcuk Universitesi Fen Fakultesi Staj Yonergesi",
                "source": "Fen_Fakultesi_Staj_Yonergesi.pdf",
            },
        },
        {
            "content": "AKTS: Avrupa Kredi Transfer Sistemini ifade eder.",
            "score": 1.0,
            "metadata": {
                "article_no": "4",
                "article_title": "Tanımlar",
                "title": "Lisansüstü Eğitim ve Öğretim Yönetmeliği",
                "source": "Lisansustu_Egitim_ve_Ogretim_Yonetmeligi.pdf",
            },
        },
    ]

    reranked = rerank_results(question, results)

    assert "Fen Fakultesi Staj" in reranked[0]["metadata"]["title"]
