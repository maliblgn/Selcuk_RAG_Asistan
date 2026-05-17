"""Compare LLM provider/model candidates with the answer quality question set.

Default mode is CI-safe: it validates provider configuration and question files
without calling external LLM APIs. Live mode is opt-in with ``--live-llm`` and
only evaluates providers whose API key is available in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from evaluation.evaluate_answer_quality import (  # noqa: E402
    build_summary,
    evaluate_question,
    load_questions,
)
from rag_engine import SelcukRAGEngine  # noqa: E402


DEFAULT_CONFIG = ROOT_DIR / "evaluation" / "provider_models.json"
DEFAULT_QUESTIONS = ROOT_DIR / "evaluation" / "answer_quality_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "provider_comparison_report.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "provider_comparison_summary.local.md"

PROVIDER_STATUSES = {
    "evaluated",
    "skipped_missing_key",
    "skipped_disabled",
    "error",
}

METRIC_KEYS = [
    "citation_present_rate",
    "source_block_leak_count",
    "url_leak_count",
    "fallback_mismatch_count",
    "low_quality_answer_count",
    "long_number_sequence_count",
    "critical_failure_count",
    "raw_source_block_leak_count",
    "final_source_block_leak_count",
    "raw_url_leak_count",
    "final_url_leak_count",
]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Provider config must be a JSON object.")
    return data


def all_provider_configs(config: dict[str, Any]) -> list[dict[str, Any]]:
    providers = config.get("providers") or []
    optional = config.get("optional_providers") or []
    if not isinstance(providers, list) or not isinstance(optional, list):
        raise ValueError("Provider config providers fields must be lists.")
    return [*providers, *optional]


def validate_provider(provider: dict[str, Any]) -> None:
    required = ["id", "provider", "model", "api_key_env"]
    missing = [key for key in required if not provider.get(key)]
    if missing:
        raise ValueError(f"Provider entry is missing required fields: {', '.join(missing)}")


def select_providers(config: dict[str, Any], provider_id: str | None) -> list[dict[str, Any]]:
    providers = all_provider_configs(config)
    for provider in providers:
        validate_provider(provider)
    if provider_id:
        selected = [provider for provider in providers if provider["id"] == provider_id]
        if not selected:
            raise ValueError(f"Provider id not found in config: {provider_id}")
        return selected
    return [provider for provider in providers if provider.get("enabled_by_default", False)]


def _empty_metric_summary(total_questions: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_questions": total_questions,
        "evaluated_questions": 0,
        "skipped_questions": total_questions,
        "answer_expected_count": 0,
        "fallback_expected_count": 0,
        "quality_status_counts": {},
        "quality_status_raw_counts": {},
    }
    summary.update({key: 0 for key in METRIC_KEYS})
    return summary


@contextmanager
def temporary_env(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _provider_base(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": provider["id"],
        "provider": provider["provider"],
        "model": provider["model"],
    }


def _skipped_summary(provider: dict[str, Any], questions: list[dict[str, Any]], status: str, error: str = "") -> dict[str, Any]:
    summary = {
        **_provider_base(provider),
        "status": status,
        **_empty_metric_summary(len(questions)),
        "average_latency_sec": None,
        "errors": [error] if error else [],
        "critical_question_ids": [],
        "results": [],
    }
    return summary


def evaluate_provider(provider: dict[str, Any], questions: list[dict[str, Any]], *, live_llm: bool) -> dict[str, Any]:
    key_env = provider["api_key_env"]
    key_present = bool(os.getenv(key_env))
    if not live_llm:
        return _skipped_summary(provider, questions, "skipped_disabled", "live_llm_not_requested")
    if not key_present:
        return _skipped_summary(provider, questions, "skipped_missing_key", f"missing_env:{key_env}")
    if provider["provider"] != "groq":
        return _skipped_summary(provider, questions, "error", f"provider_not_implemented:{provider['provider']}")

    started = time.perf_counter()
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    with temporary_env({"GROQ_MODEL": provider["model"]}):
        engine = SelcukRAGEngine(enable_llm=True)
        for item in questions:
            try:
                results.append(evaluate_question(engine, item, live_llm=True))
            except Exception as exc:  # pragma: no cover - external provider dependent
                errors.append(f"{item.get('id', 'unknown')}: {exc}")
                results.append({
                    "id": item.get("id"),
                    "question": item.get("question"),
                    "category": item.get("category"),
                    "expected_behavior": item.get("expected_behavior"),
                    "live_llm_used": False,
                    "quality_status": "live_llm_error",
                    "quality_status_raw": "live_llm_error",
                    "live_llm_error": str(exc),
                    "source_block_leak": False,
                    "url_leak": False,
                    "raw_source_block_leak": False,
                    "final_source_block_leak": False,
                    "raw_url_leak": False,
                    "final_url_leak": False,
                    "postprocess_removed_source_block": False,
                    "postprocess_removed_url": False,
                    "fallback_detected": False,
                    "fallback_expected": item.get("expected_behavior") == "fallback",
                    "low_quality_answer": False,
                    "long_number_sequence": False,
                    "citation_present": False,
                    "citation_present_final": False,
                    "expected_terms_missing": [],
                    "forbidden_terms_found": [],
                })

    elapsed = time.perf_counter() - started
    summary = build_summary(questions, results)
    critical_ids = [
        item["id"] for item in results
        if item.get("quality_status") not in {"ok", "skipped_live_llm"}
    ]
    return {
        **_provider_base(provider),
        "status": "evaluated",
        **{key: summary.get(key, 0) for key in ["evaluated_questions", "skipped_questions", *METRIC_KEYS]},
        "quality_status_counts": summary.get("quality_status_counts", {}),
        "quality_status_raw_counts": summary.get("quality_status_raw_counts", {}),
        "average_latency_sec": (elapsed / len(questions)) if questions else None,
        "errors": errors,
        "critical_question_ids": critical_ids,
        "results": results,
    }


def _best_provider(provider_summaries: list[dict[str, Any]], metric: str, *, highest: bool = False) -> str | None:
    evaluated = [item for item in provider_summaries if item["status"] == "evaluated"]
    if not evaluated:
        return None
    best = sorted(evaluated, key=lambda item: item.get(metric, 0), reverse=highest)[0]
    return best["provider_id"]


def build_report(
    config: dict[str, Any],
    questions: list[dict[str, Any]],
    provider_summaries: list[dict[str, Any]],
    *,
    live_llm: bool,
    limit: int | None,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    status_counts = Counter(item["status"] for item in provider_summaries)
    return {
        "generated_at": generated_at,
        "config_default_question_file": config.get("default_question_file"),
        "total_providers": len(provider_summaries),
        "evaluated_providers": status_counts.get("evaluated", 0),
        "skipped_providers": len(provider_summaries) - status_counts.get("evaluated", 0),
        "provider_status_counts": dict(sorted(status_counts.items())),
        "total_questions_requested": len(questions),
        "limit": limit,
        "live_llm": live_llm,
        "provider_summaries": provider_summaries,
        "best_provider_by": {
            "lowest_critical_failure_count": _best_provider(provider_summaries, "critical_failure_count"),
            "highest_citation_present_rate": _best_provider(provider_summaries, "citation_present_rate", highest=True),
            "lowest_fallback_mismatch_count": _best_provider(provider_summaries, "fallback_mismatch_count"),
        },
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# Provider Comparison Summary",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Live LLM: `{report['live_llm']}`",
        f"- Total providers: {report['total_providers']}",
        f"- Evaluated providers: {report['evaluated_providers']}",
        f"- Skipped providers: {report['skipped_providers']}",
        f"- Question limit: {report['limit']}",
        "",
        "## Provider Metrics",
        "",
        "| Provider | Model | Status | Evaluated | Critical | Citation | Source Leak | URL Leak | Fallback Mismatch |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["provider_summaries"]:
        lines.append(
            f"| `{item['provider_id']}` | `{item['model']}` | `{item['status']}` | "
            f"{item.get('evaluated_questions', 0)} | {item.get('critical_failure_count', 0)} | "
            f"{item.get('citation_present_rate', 0):.3f} | {item.get('source_block_leak_count', 0)} | "
            f"{item.get('url_leak_count', 0)} | {item.get('fallback_mismatch_count', 0)} |"
        )
    lines.extend(["", "## Critical Items", ""])
    critical_lines: list[str] = []
    for item in report["provider_summaries"]:
        for question_id in item.get("critical_question_ids", [])[:10]:
            critical_lines.append(f"- `{item['provider_id']}`: `{question_id}`")
    lines.extend(critical_lines or ["- Yok"])
    lines.extend([
        "",
        "## Notes",
        "",
        "- This evaluation does not change the production provider.",
        "- Dry-run mode is CI-safe and does not call external LLM APIs.",
        "- API key values are never written to this report.",
    ])
    return "\n".join(lines).strip() + "\n"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--provider-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--live-llm", action="store_true")
    parser.add_argument("--fail-on-critical", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    questions = load_questions(args.questions)
    if args.limit is not None:
        questions = questions[: max(0, args.limit)]
    providers = select_providers(config, args.provider_id)
    provider_summaries = [
        evaluate_provider(provider, questions, live_llm=args.live_llm)
        for provider in providers
    ]
    report = build_report(config, questions, provider_summaries, live_llm=args.live_llm, limit=args.limit)
    write_json(args.out, report)
    args.markdown_out.write_text(build_markdown_summary(report), encoding="utf-8")
    print(json.dumps({
        key: report[key]
        for key in [
            "generated_at",
            "total_providers",
            "evaluated_providers",
            "skipped_providers",
            "total_questions_requested",
            "limit",
            "live_llm",
            "provider_status_counts",
            "best_provider_by",
        ]
    }, ensure_ascii=False, indent=2))
    if args.fail_on_critical:
        failures = sum(item.get("critical_failure_count", 0) for item in provider_summaries if item["status"] == "evaluated")
        if failures > 0:
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
