import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from evaluation import run_general_smoke


QUESTIONS_PATH = Path("evaluation/general_smoke_questions.json")
REQUIRED_FIELDS = {"id", "question", "category", "expected_behavior"}


def load_questions():
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def test_general_smoke_questions_json_is_valid_list():
    questions = load_questions()
    assert isinstance(questions, list)


def test_general_smoke_questions_has_at_least_30_items():
    questions = load_questions()
    assert len(questions) >= 30


def test_general_smoke_questions_cover_at_least_5_categories():
    questions = load_questions()
    categories = {item["category"] for item in questions}
    assert len(categories) >= 5


def test_general_smoke_questions_include_answer_and_fallback_expectations():
    questions = load_questions()
    expectations = Counter(item["expected_behavior"] for item in questions)
    assert expectations["answer"] > 0
    assert expectations["fallback"] > 0


def test_general_smoke_questions_required_fields_present():
    questions = load_questions()
    for item in questions:
        assert REQUIRED_FIELDS <= set(item)
        assert item["id"].strip()
        assert item["question"].strip()
        assert item["category"].strip()
        assert item["expected_behavior"] in {"answer", "fallback"}


def synthetic_result(**overrides):
    result = {
        "id": "q1",
        "question": "Soru?",
        "category": "synthetic",
        "expected_behavior": "answer",
        "query_type": "general_document_question",
        "retrieved_doc_count": 1,
        "filtered_doc_count": 1,
        "top_document": "Belge",
        "top_article": None,
        "expected_document_hint": "Belge",
        "expected_article_hint": None,
        "expected_document_match": True,
        "expected_article_match": None,
        "has_relevant_source": True,
        "should_fallback": False,
        "source_panel_candidate_count": 1,
        "source_panel_top_label": "Belge",
        "fallback_text": None,
    }
    result.update(overrides)
    result["triage_status"] = run_general_smoke.determine_triage_status(result)
    return result


def test_run_general_smoke_summary_fields_are_produced():
    questions = [
        {"id": "q1", "category": "synthetic", "expected_behavior": "answer"},
        {"id": "q2", "category": "synthetic", "expected_behavior": "fallback"},
    ]
    results = [
        synthetic_result(id="q1"),
        synthetic_result(
            id="q2",
            expected_behavior="fallback",
            has_relevant_source=True,
            filtered_doc_count=1,
            should_fallback=False,
        ),
    ]
    report = run_general_smoke.build_report(questions, results, Path("questions.json"))
    summary = report["summary"]
    assert summary["total_questions"] == 2
    assert summary["category_counts"] == {"synthetic": 2}
    assert summary["expected_behavior_counts"] == {"answer": 1, "fallback": 1}
    assert "answer_expected_without_source_ids" in summary
    assert "fallback_expected_with_source_ids" in summary
    assert summary["fallback_expected_with_source_ids"] == ["q2"]


def test_triage_status_values_are_known_enum():
    cases = [
        synthetic_result(),
        synthetic_result(retrieved_doc_count=0, filtered_doc_count=0, has_relevant_source=False),
        synthetic_result(filtered_doc_count=0, has_relevant_source=False),
        synthetic_result(expected_behavior="fallback", has_relevant_source=True),
        synthetic_result(expected_document_match=False),
    ]
    for item in cases:
        assert item["triage_status"] in run_general_smoke.TRIAGE_STATUSES


def test_fail_on_critical_can_return_nonzero(tmp_path, monkeypatch):
    questions_path = tmp_path / "questions.json"
    out_path = tmp_path / "report.json"
    questions_path.write_text(
        json.dumps([
            {
                "id": "critical",
                "question": "Kaynak beklenen soru",
                "category": "synthetic",
                "expected_behavior": "answer",
            }
        ]),
        encoding="utf-8",
    )

    class FakeEngine:
        def __init__(self, enable_llm=False):
            self.enable_llm = enable_llm

    def fake_evaluate_question(engine, item):
        return synthetic_result(
            id=item["id"],
            question=item["question"],
            category=item["category"],
            expected_behavior="answer",
            retrieved_doc_count=1,
            filtered_doc_count=0,
            has_relevant_source=False,
            should_fallback=True,
        )

    monkeypatch.setattr(run_general_smoke, "SelcukRAGEngine", FakeEngine)
    monkeypatch.setattr(run_general_smoke, "evaluate_question", fake_evaluate_question)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_general_smoke.py",
            "--questions",
            str(questions_path),
            "--out",
            str(out_path),
            "--fail-on-critical",
        ],
    )
    assert run_general_smoke.main() == 1
    assert out_path.exists()


def test_markdown_summary_contains_risk_lists():
    report = run_general_smoke.build_report(
        [{"id": "q1", "category": "synthetic", "expected_behavior": "answer"}],
        [synthetic_result(id="q1", filtered_doc_count=0, has_relevant_source=False, should_fallback=True)],
        Path("questions.json"),
    )
    markdown = run_general_smoke.build_markdown_summary(report)
    assert "Answer Expected Without Source" in markdown
    assert "`q1`" in markdown
