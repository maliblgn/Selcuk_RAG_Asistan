import json
from collections import Counter
from pathlib import Path

from evaluation import evaluate_retrieval


GOLDEN_PATH = Path("evaluation/golden_questions.json")
REQUIRED_FIELDS = {
    "id",
    "question",
    "category",
    "expected_behavior",
    "expected_document",
    "expected_document_aliases",
    "expected_article_no",
    "expected_article_title",
    "expected_terms",
    "negative_terms",
    "notes",
}


def load_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_questions_schema_is_valid():
    questions = load_golden()
    assert isinstance(questions, list)
    for item in questions:
        assert REQUIRED_FIELDS <= set(item)
        assert item["id"].strip()
        assert item["question"].strip()
        assert item["category"].strip()
        assert item["expected_behavior"] in {"answer", "fallback"}
        assert isinstance(item["expected_document_aliases"], list)
        assert isinstance(item["expected_terms"], list)
        assert isinstance(item["negative_terms"], list)


def test_golden_questions_have_required_coverage():
    questions = load_golden()
    counts = Counter(item["expected_behavior"] for item in questions)
    categories = {item["category"] for item in questions}

    assert len(questions) >= 40
    assert len(categories) >= 6
    assert counts["answer"] >= 25
    assert counts["fallback"] >= 10


def synthetic_result(**overrides):
    result = {
        "id": "q1",
        "question": "Soru?",
        "category": "synthetic",
        "expected_behavior": "answer",
        "top_document": "Belge",
        "top_article_no": "1",
        "top_article_title": "Amac",
        "retrieved_doc_count": 3,
        "filtered_doc_count": 2,
        "document_hit_at_1": True,
        "document_hit_at_3": True,
        "article_hit_at_1": True,
        "article_hit_at_3": True,
        "expected_terms_found": ["terim"],
        "expected_terms_missing": [],
        "fallback_expected": False,
        "fallback_predicted": False,
        "source_panel_candidate_count": 2,
        "evaluation_status": "ok",
    }
    result.update(overrides)
    return result


def test_evaluate_retrieval_summary_fields_are_produced():
    questions = [
        {
            "id": "q1",
            "category": "synthetic",
            "expected_behavior": "answer",
            "expected_terms": ["terim"],
        },
        {
            "id": "q2",
            "category": "synthetic",
            "expected_behavior": "fallback",
            "expected_terms": [],
        },
    ]
    results = [
        synthetic_result(id="q1"),
        synthetic_result(
            id="q2",
            expected_behavior="fallback",
            document_hit_at_1=None,
            document_hit_at_3=None,
            article_hit_at_1=None,
            article_hit_at_3=None,
            expected_terms_found=[],
            fallback_expected=True,
            fallback_predicted=True,
            filtered_doc_count=0,
        ),
    ]

    summary = evaluate_retrieval.build_faz5a_summary(questions, results)

    assert summary["total_questions"] == 2
    assert summary["answer_questions"] == 1
    assert summary["fallback_questions"] == 1
    assert summary["document_hit_at_1"] == 1.0
    assert summary["document_hit_at_3"] == 1.0
    assert summary["article_hit_at_1"] == 1.0
    assert summary["article_hit_at_3"] == 1.0
    assert summary["expected_terms_hit_rate"] == 1.0
    assert summary["fallback_accuracy"] == 1.0
    assert summary["source_available_rate"] == 1.0
    assert summary["critical_failure_count"] == 0


def test_evaluation_status_values_are_known_enum():
    statuses = [
        "ok",
        "document_miss",
        "article_miss",
        "expected_terms_miss",
        "fallback_mismatch",
        "no_source_for_answer",
        "inspect",
    ]
    for status in statuses:
        assert status in evaluate_retrieval.EVALUATION_STATUSES


def test_status_helper_prioritizes_failure_modes():
    assert evaluate_retrieval._evaluation_status(synthetic_result(filtered_doc_count=0)) == "no_source_for_answer"
    assert evaluate_retrieval._evaluation_status(synthetic_result(document_hit_at_3=False)) == "document_miss"
    assert evaluate_retrieval._evaluation_status(synthetic_result(article_hit_at_3=False)) == "article_miss"
    assert evaluate_retrieval._evaluation_status(synthetic_result(expected_terms_missing=["eksik"])) == "expected_terms_miss"
    assert evaluate_retrieval._evaluation_status(
        synthetic_result(expected_behavior="fallback", fallback_expected=True, fallback_predicted=False)
    ) == "fallback_mismatch"


def test_markdown_report_contains_metric_names():
    report = {
        "summary": evaluate_retrieval.build_faz5a_summary(
            [{"id": "q1", "category": "synthetic", "expected_behavior": "answer", "expected_terms": ["terim"]}],
            [synthetic_result(id="q1")],
        ),
        "results": [synthetic_result(id="q1")],
    }

    markdown = evaluate_retrieval.build_markdown_report(report)

    assert "document_hit_at_1" in markdown
    assert "fallback_accuracy" in markdown


def test_local_retrieval_outputs_are_gitignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "retrieval_evaluation_report.local.json" in gitignore or "*_report*.json" in gitignore
    assert "retrieval_evaluation_summary.local.md" in gitignore
