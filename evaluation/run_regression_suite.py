"""Run common local evaluation and regression profiles.

The runner intentionally keeps live LLM calls, live dynamic fetches, ingestion,
and ChromaDB mutations out of the default profiles. It is a convenience wrapper
around existing commands, not a new evaluation implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JSON_OUT = ROOT_DIR / "regression_suite_report.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "regression_suite_summary.local.md"


@dataclass(frozen=True)
class SuiteStep:
    name: str
    command: tuple[str, ...]
    description: str = ""


def _python(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


def _artifact(name: str) -> str:
    return f"{name}.local.json"


def _markdown(name: str) -> str:
    return f"{name}.local.md"


STEP_REGISTRY: dict[str, SuiteStep] = {
    "syntax": SuiteStep(
        "syntax",
        _python(
            "-m",
            "py_compile",
            "evaluation/run_regression_suite.py",
            "evaluation/evaluate_answer_grounding.py",
            "evaluation/evaluate_manual_acceptance.py",
            "evaluation/evaluate_vector_coverage.py",
            "tools/audit_chroma_coverage.py",
            "tools/generate_chroma_coverage_questions.py",
            "chroma_runtime.py",
            "app.py",
            "app_chat_handlers.py",
            "query_router.py",
            "rag_engine.py",
            "source_discovery.py",
            "dynamic_menu_reader.py",
            "quality_dashboard.py",
        ),
        "Compile core runtime and runner modules.",
    ),
    "query_router_tests": SuiteStep(
        "query_router_tests",
        _python("-m", "pytest", "tests/test_query_router.py", "-v"),
        "Validate route decisions.",
    ),
    "dynamic_menu_tests": SuiteStep(
        "dynamic_menu_tests",
        _python("-m", "pytest", "tests/test_dynamic_menu_reader.py", "-v"),
        "Validate dynamic menu intent/parser safety.",
    ),
    "app_chat_handler_tests": SuiteStep(
        "app_chat_handler_tests",
        _python("-m", "pytest", "tests/test_app_chat_handlers.py", "-v"),
        "Validate chat orchestration helpers.",
    ),
    "dynamic_menu_dry_run": SuiteStep(
        "dynamic_menu_dry_run",
        _python(
            "evaluation/evaluate_dynamic_menu.py",
            "--questions",
            "evaluation/dynamic_menu_smoke_questions.json",
            "--out",
            _artifact("dynamic_menu_report"),
            "--markdown-out",
            _markdown("dynamic_menu_summary"),
        ),
        "CI-safe dynamic menu smoke evaluation.",
    ),
    "dynamic_menu_debug_dry_run": SuiteStep(
        "dynamic_menu_debug_dry_run",
        _python(
            "tools/debug_dynamic_menu_source.py",
            "--out",
            _artifact("dynamic_menu_debug"),
            "--markdown-out",
            _markdown("dynamic_menu_debug"),
        ),
        "Dynamic menu endpoint diagnostics; no raw HTML is stored.",
    ),
    "source_discovery_evaluation": SuiteStep(
        "source_discovery_evaluation",
        _python(
            "evaluation/evaluate_source_discovery.py",
            "--questions",
            "evaluation/source_discovery_smoke_questions.json",
            "--out",
            _artifact("source_discovery_report"),
            "--markdown-out",
            _markdown("source_discovery_summary"),
        ),
        "Source discovery smoke evaluation.",
    ),
    "retrieval_evaluation": SuiteStep(
        "retrieval_evaluation",
        _python(
            "evaluation/evaluate_retrieval.py",
            "--golden",
            "evaluation/golden_questions.json",
            "--out",
            _artifact("retrieval_evaluation_report"),
            "--markdown-out",
            _markdown("retrieval_evaluation_summary"),
        ),
        "Golden retrieval evaluation.",
    ),
    "general_smoke": SuiteStep(
        "general_smoke",
        _python(
            "evaluation/run_general_smoke.py",
            "--questions",
            "evaluation/general_smoke_questions.json",
            "--out",
            _artifact("general_smoke_report"),
            "--markdown-out",
            _markdown("general_smoke_summary"),
        ),
        "General smoke question evaluation.",
    ),
    "answer_quality_dry_run": SuiteStep(
        "answer_quality_dry_run",
        _python(
            "evaluation/evaluate_answer_quality.py",
            "--questions",
            "evaluation/answer_quality_questions.json",
            "--out",
            _artifact("answer_quality_report"),
            "--markdown-out",
            _markdown("answer_quality_summary"),
        ),
        "Answer quality dry-run without live LLM calls.",
    ),
    "answer_grounding_evidence": SuiteStep(
        "answer_grounding_evidence",
        _python(
            "evaluation/evaluate_answer_grounding.py",
            "--questions",
            "evaluation/answer_grounding_questions.json",
            "--out",
            _artifact("answer_grounding_report"),
            "--markdown-out",
            _markdown("answer_grounding_summary"),
        ),
        "Answer grounding evidence-only evaluation; no live LLM calls.",
    ),
    "manual_acceptance": SuiteStep(
        "manual_acceptance",
        _python(
            "evaluation/evaluate_manual_acceptance.py",
            "--questions",
            "evaluation/manual_acceptance_questions.json",
            "--out",
            _artifact("manual_acceptance_report"),
            "--markdown-out",
            _markdown("manual_acceptance_summary"),
        ),
        "CI-safe manual live QA acceptance checks.",
    ),
    "provider_comparison_dry_run": SuiteStep(
        "provider_comparison_dry_run",
        _python(
            "evaluation/compare_llm_providers.py",
            "--config",
            "evaluation/provider_models.json",
            "--questions",
            "evaluation/answer_quality_questions.json",
            "--out",
            _artifact("provider_comparison_report"),
            "--markdown-out",
            _markdown("provider_comparison_summary"),
        ),
        "Provider comparison dry-run without live LLM calls.",
    ),
    "article_metadata_audit": SuiteStep(
        "article_metadata_audit",
        _python(
            "evaluation/audit_article_metadata.py",
            "--golden",
            "evaluation/golden_questions.json",
            "--out",
            _artifact("article_metadata_audit"),
            "--markdown-out",
            _markdown("article_metadata_audit"),
        ),
        "Article metadata audit.",
    ),
    "source_inventory_alias_audit": SuiteStep(
        "source_inventory_alias_audit",
        _python(
            "evaluation/audit_source_inventory_aliases.py",
            "--golden",
            "evaluation/golden_questions.json",
            "--out",
            _artifact("source_inventory_alias_audit"),
            "--markdown-out",
            _markdown("source_inventory_alias_audit"),
        ),
        "Source inventory alias audit.",
    ),
    "full_pytest": SuiteStep(
        "full_pytest",
        _python("-m", "pytest", "tests/", "-v"),
        "Run the full test suite.",
    ),
}


PROFILE_STEPS: dict[str, list[str]] = {
    "fast": [
        "syntax",
        "query_router_tests",
        "dynamic_menu_tests",
        "app_chat_handler_tests",
        "dynamic_menu_dry_run",
        "source_discovery_evaluation",
        "full_pytest",
    ],
    "full": [
        "syntax",
        "query_router_tests",
        "dynamic_menu_tests",
        "app_chat_handler_tests",
        "dynamic_menu_dry_run",
        "source_discovery_evaluation",
        "retrieval_evaluation",
        "general_smoke",
        "answer_grounding_evidence",
        "manual_acceptance",
        "answer_quality_dry_run",
        "provider_comparison_dry_run",
        "full_pytest",
    ],
    "dynamic-source": [
        "syntax",
        "dynamic_menu_tests",
        "dynamic_menu_dry_run",
        "source_discovery_evaluation",
        "general_smoke",
    ],
    "snapshot-update": [
        "syntax",
        "query_router_tests",
        "dynamic_menu_tests",
        "app_chat_handler_tests",
        "dynamic_menu_dry_run",
        "source_discovery_evaluation",
        "retrieval_evaluation",
        "general_smoke",
        "answer_grounding_evidence",
        "manual_acceptance",
        "answer_quality_dry_run",
        "provider_comparison_dry_run",
        "article_metadata_audit",
        "source_inventory_alias_audit",
        "full_pytest",
    ],
    "grounding": [
        "syntax",
        "query_router_tests",
        "source_discovery_evaluation",
        "retrieval_evaluation",
        "answer_grounding_evidence",
    ],
}


PROFILE_DESCRIPTIONS = {
    "fast": "Syntax, route/dynamic/helper tests, dynamic/source smoke, full pytest.",
    "full": "Fast profile plus retrieval, general smoke, answer quality, provider comparison.",
    "dynamic-source": "Dynamic menu and source discovery focused checks; no live fetch by default.",
    "snapshot-update": "Post-snapshot quality chain; does not run ingestion or mutate ChromaDB.",
    "grounding": "Answer grounding evidence checks plus route/source/retrieval prerequisites.",
}


SECRET_PATTERNS = (
    "GROQ_API_KEY=",
    "OPENAI_API_KEY=",
    "hf_",
    "gsk_",
    "sk-",
)


def sanitize_output(text: str, max_chars: int = 4000) -> str:
    """Redact common secret-looking values and trim noisy command output."""

    sanitized = text or ""
    for pattern in SECRET_PATTERNS:
        sanitized = sanitized.replace(pattern, f"{pattern[:3]}[REDACTED]")
    if len(sanitized) > max_chars:
        return sanitized[-max_chars:]
    return sanitized


def get_profile_steps(profile: str) -> list[SuiteStep]:
    if profile not in PROFILE_STEPS:
        known = ", ".join(sorted(PROFILE_STEPS))
        raise ValueError(f"Unknown profile '{profile}'. Known profiles: {known}")
    return [STEP_REGISTRY[name] for name in PROFILE_STEPS[profile]]


def command_to_text(command: Sequence[str]) -> str:
    return " ".join(command)


def list_profiles() -> str:
    lines = ["Available regression profiles:"]
    for profile in sorted(PROFILE_STEPS):
        lines.append(f"- {profile}: {PROFILE_DESCRIPTIONS[profile]}")
        for step_name in PROFILE_STEPS[profile]:
            lines.append(f"  - {step_name}: {STEP_REGISTRY[step_name].description}")
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_step(step: SuiteStep, dry_run: bool = False, env_overrides: dict[str, str] | None = None) -> dict:
    started = time.monotonic()
    env_overrides = env_overrides or {}
    if dry_run:
        return {
            "name": step.name,
            "command": command_to_text(step.command),
            "status": "skipped",
            "return_code": None,
            "duration_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "description": step.description,
            "env_overrides": sorted(env_overrides),
        }

    env = os.environ.copy()
    env.update(env_overrides)
    completed = subprocess.run(
        step.command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        env=env,
    )
    duration = time.monotonic() - started
    return {
        "name": step.name,
        "command": command_to_text(step.command),
        "status": "passed" if completed.returncode == 0 else "failed",
        "return_code": completed.returncode,
        "duration_seconds": round(duration, 3),
        "stdout_tail": sanitize_output(completed.stdout),
        "stderr_tail": sanitize_output(completed.stderr),
        "description": step.description,
        "env_overrides": sorted(env_overrides),
    }


def build_report(
    profile: str,
    steps: list[dict],
    dry_run: bool,
    continue_on_failure: bool,
    use_local_chroma_copy: bool = False,
) -> dict:
    passed = sum(1 for item in steps if item["status"] == "passed")
    failed = sum(1 for item in steps if item["status"] == "failed")
    skipped = sum(1 for item in steps if item["status"] == "skipped")
    return {
        "generated_at": _now(),
        "profile": profile,
        "dry_run": dry_run,
        "continue_on_failure": continue_on_failure,
        "live_llm": False,
        "dynamic_live_fetch": False,
        "use_local_chroma_copy": use_local_chroma_copy,
        "total_steps": len(steps),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "status": "failed" if failed else "passed",
        "steps": steps,
    }


def write_json(report: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Regression Suite Summary",
        "",
        f"- Profile: {report['profile']}",
        f"- Status: {report['status']}",
        f"- Dry run: {report['dry_run']}",
        f"- Use local Chroma copy: {report['use_local_chroma_copy']}",
        f"- Total steps: {report['total_steps']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['failed']}",
        f"- Skipped: {report['skipped']}",
        "",
        "| Step | Status | Return code | Duration (s) |",
        "| --- | --- | ---: | ---: |",
    ]
    for step in report["steps"]:
        return_code = "" if step["return_code"] is None else step["return_code"]
        lines.append(f"| {step['name']} | {step['status']} | {return_code} | {step['duration_seconds']:.3f} |")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_profile(
    profile: str,
    dry_run: bool = False,
    continue_on_failure: bool = False,
    use_local_chroma_copy: bool = False,
) -> dict:
    step_results: list[dict] = []
    env_overrides = {"CHROMA_USE_LOCAL_COPY": "1"} if use_local_chroma_copy else {}
    for step in get_profile_steps(profile):
        result = run_step(step, dry_run=dry_run, env_overrides=env_overrides)
        step_results.append(result)
        if result["status"] == "failed" and not continue_on_failure:
            break
    return build_report(profile, step_results, dry_run, continue_on_failure, use_local_chroma_copy)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local regression/evaluation profiles.")
    parser.add_argument("--profile", choices=sorted(PROFILE_STEPS), default="fast")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--use-local-chroma-copy", action="store_true", help="Run child commands with CHROMA_USE_LOCAL_COPY=1")
    parser.add_argument("--out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_profiles:
        print(list_profiles())
        return 0

    report = run_profile(
        args.profile,
        dry_run=args.dry_run,
        continue_on_failure=args.continue_on_failure,
        use_local_chroma_copy=args.use_local_chroma_copy,
    )
    write_json(report, args.out)
    write_markdown(report, args.markdown_out)
    print(json.dumps({
        "profile": report["profile"],
        "status": report["status"],
        "total_steps": report["total_steps"],
        "passed": report["passed"],
        "failed": report["failed"],
        "skipped": report["skipped"],
        "use_local_chroma_copy": report["use_local_chroma_copy"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
