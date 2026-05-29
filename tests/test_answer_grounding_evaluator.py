import json

from langchain_core.documents import Document

from evaluation import evaluate_answer_grounding as grounding


class FakeEngine:
    def __init__(self, docs=None):
        self.docs = docs or []

    def retrieve(self, _query):
        return self.docs


def test_answer_grounding_questions_schema_loads():
    questions = grounding.load_questions(grounding.DEFAULT_QUESTIONS)

    assert len(questions) >= 30
    assert {item["expected_mode"] for item in questions} <= grounding.VALID_EXPECTED_MODES
    assert all(item.get("id") for item in questions)
    assert all("requires_fallback" in item for item in questions)


def test_empty_question_list_returns_empty_report():
    report = grounding.evaluate_questions([])

    assert report["summary"]["total_questions"] == 0
    assert report["summary"]["passed"] == 0
    assert report["results"] == []


def test_expected_mode_check_passes_for_dynamic_menu():
    item = {
        "id": "dynamic",
        "query": "bugun yemekte ne var",
        "expected_mode": "dynamic_dining_menu",
        "expected_answer_type": "dynamic",
        "expected_source_keywords": ["Yemekhane"],
        "expected_document_keywords": [],
        "expected_article_numbers": [],
        "expected_terms": [],
        "forbidden_terms": [],
        "requires_fallback": False,
    }

    report = grounding.evaluate_questions([item])

    assert report["summary"]["passed"] == 1
    assert report["results"][0]["actual_mode"] == "dynamic_dining_menu"


def test_forbidden_terms_are_reported_in_evidence():
    doc = Document(
        page_content="AKTS Avrupa Kredi Transfer Sistemi yemekhane",
        metadata={"title": "Lisansustu Egitim ve Ogretim Yonetmeligi", "article_no": "4"},
    )
    item = {
        "id": "forbidden",
        "query": "AKTS nedir?",
        "expected_mode": "rag",
        "expected_answer_type": "definition",
        "expected_source_keywords": ["Lisansustu"],
        "expected_document_keywords": ["Lisansustu"],
        "expected_article_numbers": ["4"],
        "expected_terms": ["AKTS"],
        "forbidden_terms": ["yemekhane"],
        "requires_fallback": False,
    }

    result = grounding.evaluate_question(item, engine=FakeEngine([doc]))

    assert "forbidden_terms_found" in result["failure_reasons"]
    assert result["forbidden_terms_found"] == ["yemekhane"]


def test_missing_expected_terms_are_reported():
    doc = Document(
        page_content="AKTS kisa tanim.",
        metadata={"title": "Lisansustu Egitim ve Ogretim Yonetmeligi", "article_no": "4"},
    )
    item = {
        "id": "missing",
        "query": "AKTS nedir?",
        "expected_mode": "rag",
        "expected_answer_type": "definition",
        "expected_source_keywords": ["Lisansustu"],
        "expected_document_keywords": ["Lisansustu"],
        "expected_article_numbers": ["4"],
        "expected_terms": ["Avrupa Kredi Transfer Sistemi"],
        "forbidden_terms": [],
        "requires_fallback": False,
    }

    result = grounding.evaluate_question(item, engine=FakeEngine([doc]))

    assert "expected_terms_missing" in result["failure_reasons"]
    assert result["missing_terms"]["expected_terms"] == ["Avrupa Kredi Transfer Sistemi"]


def test_requires_fallback_passes_when_no_docs():
    item = {
        "id": "fallback",
        "query": "Rektorun bugunku programi nedir?",
        "expected_mode": "fallback",
        "expected_answer_type": "unknown",
        "expected_source_keywords": [],
        "expected_document_keywords": [],
        "expected_article_numbers": [],
        "expected_terms": [],
        "forbidden_terms": [],
        "requires_fallback": True,
    }

    result = grounding.evaluate_question(item, engine=FakeEngine([]))

    assert result["passed"]
    assert result["actual_mode"] == "fallback"
    assert result["fallback_predicted"] is True


def test_live_llm_default_false_and_missing_key_skips(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    doc = Document(
        page_content="AKTS Avrupa Kredi Transfer Sistemi",
        metadata={"title": "Lisansustu Egitim ve Ogretim Yonetmeligi", "article_no": "4"},
    )
    item = {
        "id": "live_skip",
        "query": "AKTS nedir?",
        "expected_mode": "rag",
        "expected_answer_type": "definition",
        "expected_source_keywords": ["Lisansustu"],
        "expected_document_keywords": ["Lisansustu"],
        "expected_article_numbers": ["4"],
        "expected_terms": ["AKTS"],
        "forbidden_terms": [],
        "requires_fallback": False,
    }

    report = grounding.evaluate_questions([item], live_llm=True, engine_factory=lambda _enabled: FakeEngine([doc]))

    assert report["live_llm_requested"] is True
    assert report["llm_calls"] is False
    assert report["results"][0]["live_skip_reason"] == "missing_groq_api_key"


def test_report_json_and_markdown_can_be_written(tmp_path):
    report = grounding.evaluate_questions([])
    json_path = tmp_path / "answer_grounding.local.json"
    markdown_path = tmp_path / "answer_grounding.local.md"

    grounding.write_json(json_path, report)
    markdown_path.write_text(grounding.build_markdown_summary(report), encoding="utf-8")

    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert "summary" in loaded
    assert "results" in loaded
    assert markdown_path.read_text(encoding="utf-8").startswith("# Answer Grounding Evaluation Summary")
