import json
from pathlib import Path

import quality_dashboard as qd


def test_safe_load_json_missing_file_returns_none(tmp_path):
    assert qd.safe_load_json(tmp_path / "missing.json") is None


def test_safe_load_json_malformed_file_returns_none(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    assert qd.safe_load_json(path) is None


def test_summarize_retrieval_report_extracts_expected_fields(tmp_path):
    path = tmp_path / "retrieval_evaluation_report.local.json"
    path.write_text(json.dumps({
        "document_hit_at_1": 0.9,
        "document_hit_at_3": 0.93,
        "article_hit_at_1": 0.67,
        "article_hit_at_3": 0.77,
        "fallback_accuracy": 1.0,
        "critical_failure_count": 2,
        "secret": "do-not-show",
    }), encoding="utf-8")

    summary = qd.summarize_retrieval_report(path)

    assert summary["document_hit_at_1"] == 0.9
    assert summary["fallback_accuracy"] == 1.0
    assert "secret" not in summary


def test_summarize_answer_quality_report_uses_final_leak_fields(tmp_path):
    path = tmp_path / "answer_quality_report.local.json"
    path.write_text(json.dumps({
        "summary": {
            "total_questions": 10,
            "evaluated_questions": 10,
            "source_block_leak_count": 0,
            "url_leak_count": 0,
            "critical_failure_count": 0,
            "quality_status_counts": {"ok": 10},
        }
    }), encoding="utf-8")

    summary = qd.summarize_answer_quality_report(path)

    assert summary["source_block_leak_count"] == 0
    assert summary["url_leak_count"] == 0
    assert summary["quality_status_counts"] == {"ok": 10}


def test_summarize_provider_comparison_report_sanitizes_provider_fields(tmp_path):
    path = tmp_path / "provider_comparison_report.local.json"
    path.write_text(json.dumps({
        "generated_at": "now",
        "total_providers": 1,
        "evaluated_providers": 1,
        "skipped_providers": 0,
        "live_llm": True,
        "provider_summaries": [{
            "provider_id": "groq_llama_3_1_8b_instant",
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "status": "evaluated",
            "evaluated_questions": 10,
            "critical_failure_count": 0,
            "source_block_leak_count": 0,
            "url_leak_count": 0,
            "api_key_env": "GROQ_API_KEY",
            "secret_value": "never",
        }],
    }), encoding="utf-8")

    summary = qd.summarize_provider_comparison_report(path)
    provider = summary["providers"][0]

    assert provider["provider_id"] == "groq_llama_3_1_8b_instant"
    assert provider["status"] == "evaluated"
    assert "api_key_env" not in provider
    assert "secret_value" not in provider


def test_general_smoke_summary_extracts_risk_counts(tmp_path):
    path = tmp_path / "general_smoke_report.local.json"
    path.write_text(json.dumps({
        "summary": {
            "total_questions": 34,
            "expected_behavior_counts": {"answer": 23, "fallback": 11},
            "answer_expected_without_source_count": 2,
            "fallback_expected_with_source_count": 2,
        }
    }), encoding="utf-8")

    summary = qd.summarize_general_smoke_report(path)

    assert summary["total_questions"] == 34
    assert summary["expected_behavior_counts"]["answer"] == 23
    assert summary["answer_expected_without_source_count"] == 2


def test_render_quality_dashboard_importable():
    assert callable(qd.render_quality_dashboard)
