from evaluation.evaluate_retrieval import (
    article_matches,
    article_numbers_from_content,
    compute_metrics,
    evaluate,
    expected_document_matches,
    expected_terms_match,
    resolve_db_path,
)


def test_expected_document_contains_matches_url_decoded_source():
    result = {
        "source": "https://example.edu.tr/L%C4%B0SANS%C3%9CST%C3%9C.pdf",
        "title": "",
    }

    assert expected_document_matches(result, ["LİSANSÜSTÜ"])
    assert expected_document_matches(result, ["Lisansustu"])


def test_article_no_regex_detects_content_article():
    content = "Başlık\nMADDE 43 - Doktora yeterlik sınavı\nMetin."

    assert article_numbers_from_content(content) == ["43"]
    assert article_matches({"content": content, "metadata": {}}, "43")


def test_expected_terms_case_insensitive_normalized():
    results = [{"content": "AKTS: Avrupa Kredi Transfer Sistemini ifade eder."}]

    assert expected_terms_match(results, ["avrupa kredi transfer sistemi"])


def test_compute_metrics_ratios():
    results = [
        {"document_hit_at_1": True, "document_hit_at_3": True, "document_hit_at_5": True, "article_hit_at_1": False, "article_hit_at_3": True, "article_hit_at_5": True, "expected_terms_hit_at_5": True},
        {"document_hit_at_1": False, "document_hit_at_3": True, "document_hit_at_5": True, "article_hit_at_1": False, "article_hit_at_3": False, "article_hit_at_5": True, "expected_terms_hit_at_5": False},
    ]

    metrics = compute_metrics(results)

    assert metrics["document_hit_at_1"] == 0.5
    assert metrics["document_hit_at_3"] == 1.0
    assert metrics["article_hit_at_1"] == 0.0
    assert metrics["article_hit_at_5"] == 1.0
    assert metrics["expected_terms_hit_at_5"] == 0.5


def test_resolve_db_path_accepts_persist_directory(tmp_path):
    persist_dir = tmp_path / "chroma_db_legal_test"
    persist_dir.mkdir()

    assert resolve_db_path(str(persist_dir)).endswith("chroma.sqlite3")


def test_evaluate_outputs_metadata_rerank_fields():
    questions = [
        {
            "id": "q1",
            "question": "AKTS kısaltması hangi sistemin adıdır?",
            "expected_document_contains": ["lisansustu"],
            "expected_article_no": "4",
            "expected_answer_terms": ["Avrupa Kredi Transfer Sistemi"],
        }
    ]
    docs = [
        {
            "id": 1,
            "content": "AKTS: Avrupa Kredi Transfer Sistemi.",
            "metadata": {"source": "lisansustu.pdf", "title": "Lisansustu", "article_no": "4", "article_title": "Tanımlar"},
            "source": "lisansustu.pdf",
            "title": "Lisansustu",
        }
    ]

    report = evaluate(questions, docs, top_k=1, candidate_k=5, metadata_rerank=True)

    assert report["metadata_rerank"] is True
    assert report["candidate_k"] == 5
    assert report["results"][0]["intent"] == "definition"
    assert report["results"][0]["acronym_terms"] == ["AKTS"]
    assert report["results"][0]["top_results"][0]["rerank_score"] is not None
