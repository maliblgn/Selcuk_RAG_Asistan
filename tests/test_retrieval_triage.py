import json
import sys
from pathlib import Path

from evaluation import triage_retrieval_failures as triage


def sample_evaluation_report():
    return {
        "summary": {
            "document_hit_at_1": 0.5,
            "document_hit_at_3": 0.6,
            "article_hit_at_1": 0.4,
            "article_hit_at_3": 0.5,
            "expected_terms_hit_rate": 0.7,
            "fallback_accuracy": 1.0,
            "critical_failure_count": 2,
        },
        "results": [
            {
                "id": "answer_missing",
                "question": "Burs basvurusu nasil yapilir?",
                "category": "directive_specific",
                "expected_behavior": "answer",
                "top_document": None,
                "top_article_no": None,
                "top_article_title": None,
                "retrieved_doc_count": 2,
                "filtered_doc_count": 0,
                "expected_terms_missing": ["burs"],
                "evaluation_status": "no_source_for_answer",
            },
            {
                "id": "fallback_ok",
                "question": "Bugun yemekte ne var?",
                "category": "operational_current_info",
                "expected_behavior": "fallback",
                "top_document": None,
                "top_article_no": None,
                "top_article_title": None,
                "retrieved_doc_count": 0,
                "filtered_doc_count": 0,
                "expected_terms_missing": [],
                "evaluation_status": "ok",
            },
            {
                "id": "article_bad",
                "question": "Madde sorusu",
                "category": "academic_article",
                "expected_behavior": "answer",
                "top_document": "Lisansustu",
                "top_article_no": "24",
                "top_article_title": "Amac",
                "retrieved_doc_count": 4,
                "filtered_doc_count": 3,
                "expected_terms_missing": [],
                "evaluation_status": "article_miss",
            },
        ],
    }


def sample_golden_questions():
    return [
        {
            "id": "answer_missing",
            "expected_document": "Burs Yonergesi",
            "expected_document_aliases": ["Burs"],
            "expected_article_no": "5",
        },
        {
            "id": "fallback_ok",
            "expected_document": None,
            "expected_document_aliases": [],
            "expected_article_no": None,
        },
        {
            "id": "article_bad",
            "expected_document": "Lisansustu",
            "expected_document_aliases": ["Lisansustu"],
            "expected_article_no": "43",
        },
    ]


def test_triage_script_imports_and_enums_are_known():
    assert "document_miss" in triage.FAILURE_TYPES
    assert "article_miss" in triage.FAILURE_TYPES
    assert "no_source_for_answer" in triage.FAILURE_TYPES
    assert "fallback_mismatch" in triage.FAILURE_TYPES
    assert "query_vocabulary_gap" in triage.POSSIBLE_ROOT_CAUSES
    assert "article_metadata_mismatch" in triage.POSSIBLE_ROOT_CAUSES
    assert "relevance_filter_too_strict" in triage.POSSIBLE_ROOT_CAUSES


def test_triage_summary_fields_are_produced():
    report = triage.build_triage_report(sample_evaluation_report(), sample_golden_questions())
    summary = report["summary"]

    assert summary["total_questions"] == 3
    assert summary["total_failures"] == 2
    assert summary["failures_by_type"]["no_source_for_answer"] == 1
    assert summary["failures_by_type"]["article_miss"] == 1
    assert "possible_root_cause_counts" in summary
    assert "top_priority_ids" in summary
    assert summary["top_priority_ids"] == ["answer_missing"]


def test_failure_items_include_recommended_action():
    report = triage.build_triage_report(sample_evaluation_report(), sample_golden_questions())

    for item in report["failures"]:
        assert item["failure_type"] in triage.FAILURE_TYPES
        assert item["possible_root_cause"] in triage.POSSIBLE_ROOT_CAUSES
        assert item["recommended_action"]
        assert item["priority"] in {"high", "medium", "low"}


def test_triage_main_writes_valid_json(tmp_path, monkeypatch):
    eval_path = tmp_path / "eval.json"
    golden_path = tmp_path / "golden.json"
    out_path = tmp_path / "triage.json"
    markdown_path = tmp_path / "triage.md"
    eval_path.write_text(json.dumps(sample_evaluation_report()), encoding="utf-8")
    golden_path.write_text(json.dumps(sample_golden_questions()), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "triage_retrieval_failures.py",
            "--report",
            str(eval_path),
            "--golden",
            str(golden_path),
            "--out",
            str(out_path),
            "--markdown-out",
            str(markdown_path),
        ],
    )

    assert triage.main() == 0
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert parsed["summary"]["total_failures"] == 2
    assert markdown_path.exists()


def test_local_triage_outputs_are_gitignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "retrieval_triage_report.local.json" in gitignore
    assert "retrieval_triage_summary.local.md" in gitignore
