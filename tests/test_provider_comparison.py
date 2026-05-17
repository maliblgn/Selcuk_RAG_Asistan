import json
from pathlib import Path

import evaluation.compare_llm_providers as comparison


def test_provider_models_json_schema_is_valid():
    config = comparison.load_config(Path("evaluation/provider_models.json"))
    providers = comparison.all_provider_configs(config)

    assert config["default_question_file"] == "evaluation/answer_quality_questions.json"
    assert providers
    for provider in providers:
        comparison.validate_provider(provider)
        assert provider["id"]
        assert provider["provider"] in {"groq", "openai"}
        assert provider["model"]
        assert provider["api_key_env"].endswith("_API_KEY")


def test_dry_run_does_not_evaluate_provider(monkeypatch):
    provider = {
        "id": "sample_groq",
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "api_key_env": "GROQ_API_KEY",
        "enabled_by_default": True,
    }
    monkeypatch.setenv("GROQ_API_KEY", "secret-value")

    summary = comparison.evaluate_provider(provider, [{"id": "q1", "question": "AKTS nedir?"}], live_llm=False)

    assert summary["status"] == "skipped_disabled"
    assert summary["evaluated_questions"] == 0
    assert summary["skipped_questions"] == 1
    assert "secret-value" not in json.dumps(summary)


def test_live_provider_without_key_is_skipped(monkeypatch):
    provider = {
        "id": "sample_groq",
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "api_key_env": "MISSING_TEST_API_KEY",
        "enabled_by_default": True,
    }
    monkeypatch.delenv("MISSING_TEST_API_KEY", raising=False)

    summary = comparison.evaluate_provider(provider, [{"id": "q1", "question": "AKTS nedir?"}], live_llm=True)

    assert summary["status"] == "skipped_missing_key"
    assert summary["errors"] == ["missing_env:MISSING_TEST_API_KEY"]


def test_summary_fields_and_status_enum_are_produced():
    provider_summary = {
        "provider_id": "sample_groq",
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "status": "evaluated",
        "evaluated_questions": 1,
        "skipped_questions": 0,
        "citation_present_rate": 1.0,
        "source_block_leak_count": 0,
        "url_leak_count": 0,
        "fallback_mismatch_count": 0,
        "low_quality_answer_count": 0,
        "long_number_sequence_count": 0,
        "critical_failure_count": 0,
        "raw_source_block_leak_count": 1,
        "final_source_block_leak_count": 0,
        "raw_url_leak_count": 1,
        "final_url_leak_count": 0,
        "quality_status_counts": {"ok": 1},
        "quality_status_raw_counts": {"source_block_leak": 1},
        "average_latency_sec": 0.1,
        "errors": [],
        "critical_question_ids": [],
        "results": [],
    }

    report = comparison.build_report({}, [{"id": "q1"}], [provider_summary], live_llm=True, limit=1)

    assert report["total_providers"] == 1
    assert report["evaluated_providers"] == 1
    assert report["best_provider_by"]["lowest_critical_failure_count"] == "sample_groq"
    assert set(report["provider_status_counts"]) <= comparison.PROVIDER_STATUSES
    assert all(key in provider_summary for key in comparison.METRIC_KEYS)


def test_main_writes_valid_json_without_live_llm(tmp_path):
    config_path = tmp_path / "providers.json"
    questions_path = tmp_path / "questions.json"
    out_path = tmp_path / "provider_report.local.json"
    markdown_path = tmp_path / "provider_summary.local.md"
    config_path.write_text(json.dumps({
        "providers": [{
            "id": "sample_groq",
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "api_key_env": "GROQ_API_KEY",
            "enabled_by_default": True,
        }],
        "optional_providers": [],
    }), encoding="utf-8")
    questions_path.write_text(json.dumps([{
        "id": "q1",
        "question": "AKTS nedir?",
        "category": "academic_definition",
        "expected_behavior": "answer",
        "expected_terms": ["akts"],
        "forbidden_terms": [],
        "quality_checks": [],
    }]), encoding="utf-8")

    rc = comparison.main([
        "--config", str(config_path),
        "--questions", str(questions_path),
        "--out", str(out_path),
        "--markdown-out", str(markdown_path),
    ])

    assert rc == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["provider_summaries"][0]["status"] == "skipped_disabled"
    assert markdown_path.exists()


def test_provider_comparison_outputs_are_gitignored():
    patterns = Path(".gitignore").read_text(encoding="utf-8")

    assert "provider_comparison_report.local.json" in patterns
    assert "provider_comparison_summary.local.md" in patterns
