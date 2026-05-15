import json
from pathlib import Path

from evaluation import evaluate_answer_quality as aq


ROOT_DIR = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT_DIR / "evaluation" / "answer_quality_questions.json"


def load_questions():
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def test_answer_quality_questions_schema_is_valid():
    questions = load_questions()
    assert isinstance(questions, list)
    assert len(questions) >= 12
    expected_behaviors = {item["expected_behavior"] for item in questions}
    assert {"answer", "fallback"} <= expected_behaviors
    for item in questions:
        assert item["id"]
        assert item["question"]
        assert item["category"]
        assert item["expected_behavior"] in {"answer", "fallback"}
        assert isinstance(item.get("quality_checks"), list)


def test_detection_helpers_find_known_risks():
    assert aq.detect_source_block_leak("Cevap.\n\n--- KAYNAKLAR ---\n[1] x")
    assert aq.detect_source_block_leak("### Kaynaklar\nx")
    assert aq.detect_url_leak("URL: https://example.com/test")
    assert aq.detect_inline_citation("Bu ifade edilir. [1]")
    number_list = ", ".join(str(i) for i in range(1, 35))
    assert aq.detect_long_number_sequence(number_list)


def test_fallback_detector_is_normalized():
    answer = "Bu bilgi mevcut indekslenmiş yönetmelik/yönerge kaynaklarında güvenilir şekilde bulunamadı."
    assert aq.detect_fallback_answer(answer)


def test_summary_fields_and_status_enum_for_skipped_dry_run():
    questions = [
        {
            "id": "q1",
            "question": "AKTS nedir?",
            "category": "academic_definition",
            "expected_behavior": "answer",
            "expected_terms": ["akts"],
            "forbidden_terms": [],
            "quality_checks": ["require_inline_citation"],
        }
    ]
    results = [
        {
            "id": "q1",
            "question": "AKTS nedir?",
            "category": "academic_definition",
            "expected_behavior": "answer",
            "live_llm_used": False,
            "answer_text_preview": "",
            "retrieved_source_count": 1,
            "source_panel_candidate_count": 1,
            "citation_present": False,
            "source_block_leak": False,
            "url_leak": False,
            "low_quality_answer": False,
            "long_number_sequence": False,
            "fallback_expected": False,
            "fallback_detected": False,
            "expected_terms_found": [],
            "expected_terms_missing": ["akts"],
            "forbidden_terms_found": [],
            "quality_checks": ["require_inline_citation"],
            "live_llm_error": "",
            "quality_status": "skipped_live_llm",
        }
    ]
    report = aq.build_report(questions, results, live_llm=False)
    summary = report["summary"]
    assert summary["total_questions"] == 1
    assert summary["evaluated_questions"] == 0
    assert summary["skipped_questions"] == 1
    assert "citation_present_rate" in summary
    assert set(summary["quality_status_counts"]) <= aq.QUALITY_STATUSES


def test_determine_quality_status_prioritizes_live_failures():
    base = {
        "live_llm_used": True,
        "live_llm_error": "",
        "source_block_leak": False,
        "url_leak": False,
        "low_quality_answer": False,
        "long_number_sequence": False,
        "expected_behavior": "answer",
        "retrieved_source_count": 1,
        "citation_present": True,
        "expected_terms_missing": [],
        "forbidden_terms_found": [],
    }
    assert aq.determine_quality_status(base) == "ok"
    assert aq.determine_quality_status({**base, "citation_present": False}) == "citation_missing"
    assert aq.determine_quality_status({**base, "source_block_leak": True}) == "source_block_leak"
    assert aq.determine_quality_status({**base, "live_llm_error": "boom"}) == "live_llm_error"


def test_main_dry_run_can_write_skipped_report_without_real_llm(monkeypatch, tmp_path):
    class FakeEngine:
        def __init__(self, enable_llm=False):
            assert enable_llm is False

        def retrieve(self, question):
            return []

    monkeypatch.setattr(aq, "SelcukRAGEngine", FakeEngine)
    questions_path = tmp_path / "questions.json"
    questions_path.write_text(
        json.dumps([
            {
                "id": "fallback_sample",
                "question": "Bugün yemekte ne var?",
                "category": "operational_current_info",
                "expected_behavior": "fallback",
                "expected_terms": ["bulunamadi"],
                "forbidden_terms": [],
                "quality_checks": ["require_safe_fallback"],
            }
        ]),
        encoding="utf-8",
    )
    out_path = tmp_path / "answer_quality_report.local.json"
    md_path = tmp_path / "answer_quality_summary.local.md"

    exit_code = aq.main([
        "--questions", str(questions_path),
        "--out", str(out_path),
        "--markdown-out", str(md_path),
    ])

    assert exit_code == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["summary"]["skipped_questions"] == 1
    assert report["results"][0]["quality_status"] == "skipped_live_llm"
    assert md_path.exists()


def test_live_llm_without_key_returns_controlled_error(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    questions_path = tmp_path / "questions.json"
    questions_path.write_text("[]", encoding="utf-8")
    exit_code = aq.main([
        "--questions", str(questions_path),
        "--out", str(tmp_path / "out.json"),
        "--markdown-out", str(tmp_path / "out.md"),
        "--live-llm",
    ])
    assert exit_code == 2
