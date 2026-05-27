"""Read-only Streamlit quality dashboard helpers.

The dashboard summarizes local evaluation artifacts when they exist. It never
runs shell commands and intentionally avoids displaying raw answers or secrets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from check_chroma_health import check_chroma_health
from dynamic_menu_reader import get_dynamic_menu_health


ROOT_DIR = Path(__file__).resolve().parent

ARTIFACT_PATHS = {
    "retrieval": ROOT_DIR / "retrieval_evaluation_report.local.json",
    "general_smoke": ROOT_DIR / "general_smoke_report.local.json",
    "answer_quality": ROOT_DIR / "answer_quality_report.local.json",
    "provider_comparison": ROOT_DIR / "provider_comparison_report.local.json",
}

SENSITIVE_KEY_PARTS = ("key", "token", "secret", "password", "authorization")


def safe_load_json(path: str | Path) -> dict[str, Any] | None:
    """Load a local JSON artifact without raising on missing or malformed files."""
    try:
        json_path = Path(path)
        if not json_path.exists() or not json_path.is_file():
            return None
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _summary(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary")
    return summary if isinstance(summary, dict) else report


def _safe_pick(data: dict[str, Any] | None, keys: list[str]) -> dict[str, Any] | None:
    if not data:
        return None
    return {
        key: data.get(key)
        for key in keys
        if key in data and not _is_sensitive_key(key)
    }


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def summarize_retrieval_report(path: str | Path = ARTIFACT_PATHS["retrieval"]) -> dict[str, Any] | None:
    data = _summary(safe_load_json(path))
    return _safe_pick(data, [
        "generated_at",
        "total_questions",
        "answer_questions",
        "fallback_questions",
        "document_hit_at_1",
        "document_hit_at_3",
        "article_hit_at_1",
        "article_hit_at_3",
        "fallback_accuracy",
        "critical_failure_count",
    ])


def summarize_general_smoke_report(path: str | Path = ARTIFACT_PATHS["general_smoke"]) -> dict[str, Any] | None:
    data = _summary(safe_load_json(path))
    return _safe_pick(data, [
        "generated_at",
        "total_questions",
        "expected_behavior_counts",
        "smoke_fallback_count",
        "answer_expected_without_source_count",
        "fallback_expected_with_source_count",
        "triage_status_counts",
    ])


def summarize_answer_quality_report(path: str | Path = ARTIFACT_PATHS["answer_quality"]) -> dict[str, Any] | None:
    data = _summary(safe_load_json(path))
    return _safe_pick(data, [
        "generated_at",
        "total_questions",
        "evaluated_questions",
        "skipped_questions",
        "citation_present_rate",
        "source_block_leak_count",
        "url_leak_count",
        "fallback_mismatch_count",
        "low_quality_answer_count",
        "long_number_sequence_count",
        "critical_failure_count",
        "quality_status_counts",
    ])


def summarize_provider_comparison_report(path: str | Path = ARTIFACT_PATHS["provider_comparison"]) -> dict[str, Any] | None:
    report = safe_load_json(path)
    if not report:
        return None
    providers = []
    for item in report.get("provider_summaries") or []:
        if not isinstance(item, dict):
            continue
        providers.append(_safe_pick(item, [
            "provider_id",
            "provider",
            "model",
            "status",
            "evaluated_questions",
            "skipped_questions",
            "critical_failure_count",
            "source_block_leak_count",
            "url_leak_count",
            "fallback_mismatch_count",
            "citation_present_rate",
        ]))
    return {
        "generated_at": report.get("generated_at"),
        "total_providers": report.get("total_providers"),
        "evaluated_providers": report.get("evaluated_providers"),
        "skipped_providers": report.get("skipped_providers"),
        "live_llm": report.get("live_llm"),
        "providers": [item for item in providers if item],
    }


def summarize_dynamic_menu_health() -> dict[str, Any]:
    return _safe_pick(get_dynamic_menu_health(), [
        "mode",
        "source_url",
        "source_title",
        "cache_ttl_seconds",
        "supported_parse_strategies",
        "live_fetch_required",
        "secret_required",
    ]) or {}


def get_system_health(db_path: str | Path = ROOT_DIR / "chroma_db") -> dict[str, Any]:
    report = check_chroma_health(str(db_path))
    return _safe_pick(report, [
        "generated_at",
        "db_path",
        "db_exists",
        "sqlite_exists",
        "status",
        "ok",
        "reason",
        "collection_readable",
        "document_count",
        "unique_source_count",
        "source_type_counts",
    ]) or {}


def _command_help() -> dict[str, str]:
    return {
        "Retrieval evaluation": (
            "python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json "
            "--out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md"
        ),
        "General smoke": (
            "python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json "
            "--out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md"
        ),
        "Answer quality dry-run": (
            "python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json "
            "--out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md"
        ),
        "Provider comparison dry-run": (
            "python evaluation/compare_llm_providers.py --config evaluation/provider_models.json "
            "--questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json "
            "--markdown-out provider_comparison_summary.local.md"
        ),
    }


def _render_summary_table(st, title: str, summary: dict[str, Any] | None, missing_command: str) -> None:
    st.markdown(f"### {title}")
    if not summary:
        st.info("Local artifact bulunamadi. Komutu terminalde calistirip bu paneli yenileyebilirsiniz.")
        st.code(missing_command, language="bash")
        return
    st.json(summary, expanded=False)


def render_quality_dashboard() -> None:
    """Render the read-only quality dashboard inside an existing Streamlit page."""
    import streamlit as st

    commands = _command_help()

    st.markdown("## Sistem / Kalite Paneli")
    st.caption("Read-only panel. Komut calistirmaz, API key veya secret gostermez.")

    health = get_system_health()
    st.markdown("### Sistem Durumu")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ChromaDB", "OK" if health.get("ok") else "Sorun")
    col2.metric("Collection", "Okunuyor" if health.get("collection_readable") else "Okunamiyor")
    col3.metric("Chunk", health.get("document_count", 0))
    col4.metric("Kaynak", health.get("unique_source_count", 0))
    st.caption(f"Healthcheck zamani: `{health.get('generated_at', 'bilinmiyor')}`")
    if not health.get("ok"):
        st.warning(health.get("reason") or "ChromaDB hazir degil.")

    runtime_hint = os.getenv("SPACE_ID") or os.getenv("HF_SPACE_ID") or "local/runtime"
    st.caption(f"Runtime: `{runtime_hint}`")

    _render_summary_table(
        st,
        "Retrieval Quality",
        summarize_retrieval_report(),
        commands["Retrieval evaluation"],
    )
    _render_summary_table(
        st,
        "General Smoke",
        summarize_general_smoke_report(),
        commands["General smoke"],
    )
    _render_summary_table(
        st,
        "Answer Quality",
        summarize_answer_quality_report(),
        commands["Answer quality dry-run"],
    )
    _render_summary_table(
        st,
        "Provider Comparison",
        summarize_provider_comparison_report(),
        commands["Provider comparison dry-run"],
    )
    st.markdown("### Dynamic Menu Health")
    st.json(summarize_dynamic_menu_health(), expanded=False)

    st.markdown("### Komut Kilavuzu")
    for label, command in commands.items():
        st.markdown(f"**{label}**")
        st.code(command, language="bash")
    st.caption("Live LLM komutlari manuel calistirilir ve API key gerektirir; key degeri UI'da gosterilmez.")
