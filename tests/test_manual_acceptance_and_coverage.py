import json

from evaluation.evaluate_manual_acceptance import build_report, load_questions
from evaluation.evaluate_vector_coverage import evaluate_questions
from tools.generate_chroma_coverage_questions import QUESTION_TEMPLATES


def test_manual_acceptance_questions_schema_and_report():
    questions = load_questions("evaluation/manual_acceptance_questions.json")

    assert len(questions) >= 15
    assert all("id" in item and "query" in item and "expected_mode" in item for item in questions)

    report = build_report(questions)

    assert report["total_questions"] == len(questions)
    assert "critical_failures" in report
    assert report["mode_accuracy"] >= 0.9


def test_manual_acceptance_json_is_valid():
    data = json.loads(open("evaluation/manual_acceptance_questions.json", encoding="utf-8").read())

    assert isinstance(data, list)
    assert any(item["expected_mode"] == "dynamic_dining_menu" for item in data)
    assert any(item["expected_mode"] == "source_discovery" for item in data)


def test_vector_coverage_evaluator_empty_list_passes():
    report = evaluate_questions([])

    assert report["status"] == "passed"
    assert report["total_questions"] == 0
    assert report["mode_pass_rate"] == 1.0


def test_generated_coverage_templates_include_risky_topics():
    for topic in ("cift_anadal", "agno_gano", "lisansustu", "yemekhane"):
        assert topic in QUESTION_TEMPLATES
        assert QUESTION_TEMPLATES[topic]
