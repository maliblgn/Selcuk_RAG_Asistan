import json
from collections import Counter
from pathlib import Path


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
