"""Triage retrieval evaluation failures into general improvement buckets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FAILURE_TYPES = {
    "document_miss",
    "article_miss",
    "no_source_for_answer",
    "expected_terms_miss",
    "fallback_mismatch",
    "inspect",
}

POSSIBLE_ROOT_CAUSES = {
    "query_vocabulary_gap",
    "metadata_title_mismatch",
    "article_metadata_mismatch",
    "relevance_filter_too_strict",
    "source_missing_or_not_indexed",
    "expected_document_hint_too_strict",
    "chunking_or_ocr_issue",
    "fallback_policy_review",
    "needs_manual_review",
}

CRITICAL_FAILURES = {"document_miss", "fallback_mismatch", "no_source_for_answer"}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def golden_by_id(golden_questions: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in golden_questions}


def failure_type_for(result: dict) -> str | None:
    status = result.get("evaluation_status")
    if status == "ok":
        return None
    if status in FAILURE_TYPES:
        return status
    return "inspect"


def infer_root_cause(result: dict, golden: dict) -> str:
    failure_type = failure_type_for(result)
    category = result.get("category")
    filtered_count = result.get("filtered_doc_count", 0)
    retrieved_count = result.get("retrieved_doc_count", 0)

    if failure_type == "no_source_for_answer":
        if retrieved_count == 0:
            return "source_missing_or_not_indexed"
        if category in {"directive_specific", "faculty_specific", "research_administration"}:
            return "query_vocabulary_gap"
        return "relevance_filter_too_strict"
    if failure_type == "document_miss":
        if filtered_count == 0:
            return "relevance_filter_too_strict"
        if golden.get("expected_document_aliases"):
            return "metadata_title_mismatch"
        return "expected_document_hint_too_strict"
    if failure_type == "article_miss":
        return "article_metadata_mismatch"
    if failure_type == "expected_terms_miss":
        return "chunking_or_ocr_issue"
    if failure_type == "fallback_mismatch":
        return "fallback_policy_review"
    if failure_type == "inspect":
        return "metadata_title_mismatch"
    return "needs_manual_review"


def recommended_action_for(root_cause: str) -> str:
    actions = {
        "query_vocabulary_gap": "Genel query normalization, Turkish character folding, synonym/alias expansion, and domain-term vocabulary should be reviewed before changing runtime scoring.",
        "metadata_title_mismatch": "Document title aliases and source metadata normalization should be compared against source inventory and golden expectations.",
        "article_metadata_mismatch": "Article number/title extraction and matching tolerance should be reviewed with OCR/chunk metadata examples.",
        "relevance_filter_too_strict": "Relevance filtering thresholds should be evaluated on golden metrics before any runtime threshold change.",
        "source_missing_or_not_indexed": "Confirm whether the expected source exists in source inventory and ChromaDB; snapshot update may be needed only as a separate task.",
        "expected_document_hint_too_strict": "Review golden expected_document and aliases; avoid treating overly narrow hints as retrieval failures.",
        "chunking_or_ocr_issue": "Inspect source chunks for OCR noise, split boundaries, and missing expected terms.",
        "fallback_policy_review": "Review fallback classification and relevance threshold for operational/current-info questions without adding question-specific patches.",
        "needs_manual_review": "Inspect the question, top source, and expected metadata manually before deciding on a general improvement.",
    }
    return actions.get(root_cause, actions["needs_manual_review"])


def priority_for(failure_type: str, root_cause: str, result: dict) -> str:
    if failure_type in CRITICAL_FAILURES:
        return "high"
    if failure_type in {"article_miss", "expected_terms_miss"}:
        return "medium"
    if root_cause in {"source_missing_or_not_indexed", "fallback_policy_review"}:
        return "high"
    if result.get("expected_behavior") == "answer" and result.get("filtered_doc_count", 0) == 0:
        return "high"
    return "low"


def build_failure_item(result: dict, golden: dict) -> dict:
    failure_type = failure_type_for(result) or "inspect"
    root_cause = infer_root_cause(result, golden)
    return {
        "id": result.get("id"),
        "question": result.get("question"),
        "category": result.get("category"),
        "expected_behavior": result.get("expected_behavior"),
        "evaluation_status": result.get("evaluation_status"),
        "failure_type": failure_type,
        "expected_document": golden.get("expected_document"),
        "expected_article_no": golden.get("expected_article_no"),
        "top_document": result.get("top_document"),
        "top_article_no": result.get("top_article_no"),
        "top_article_title": result.get("top_article_title"),
        "filtered_doc_count": result.get("filtered_doc_count"),
        "expected_terms_missing": result.get("expected_terms_missing") or [],
        "possible_root_cause": root_cause,
        "recommended_action": recommended_action_for(root_cause),
        "priority": priority_for(failure_type, root_cause, result),
    }


def sort_failures(failures: list[dict]) -> list[dict]:
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    type_rank = {
        "no_source_for_answer": 0,
        "document_miss": 1,
        "fallback_mismatch": 2,
        "article_miss": 3,
        "expected_terms_miss": 4,
        "inspect": 5,
    }
    return sorted(
        failures,
        key=lambda item: (
            priority_rank.get(item["priority"], 9),
            type_rank.get(item["failure_type"], 9),
            item.get("category") or "",
            item.get("id") or "",
        ),
    )


def build_summary(report: dict, failures: list[dict]) -> dict:
    results = report.get("results") or []
    top_priority_ids = [item["id"] for item in failures if item["priority"] == "high"][:10]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_questions": len(results),
        "total_failures": len(failures),
        "failures_by_type": dict(sorted(Counter(item["failure_type"] for item in failures).items())),
        "failures_by_category": dict(sorted(Counter(item["category"] for item in failures).items())),
        "possible_root_cause_counts": dict(sorted(Counter(item["possible_root_cause"] for item in failures).items())),
        "answer_expected_failures": sum(1 for item in failures if item["expected_behavior"] == "answer"),
        "fallback_expected_failures": sum(1 for item in failures if item["expected_behavior"] == "fallback"),
        "top_priority_ids": top_priority_ids,
    }


def build_triage_report(evaluation_report: dict, golden_questions: list[dict]) -> dict:
    lookup = golden_by_id(golden_questions)
    failures = []
    for result in evaluation_report.get("results") or []:
        if failure_type_for(result) is None:
            continue
        failures.append(build_failure_item(result, lookup.get(result.get("id"), {})))
    failures = sort_failures(failures)
    return {
        "summary": build_summary(evaluation_report, failures),
        "evaluation_summary": evaluation_report.get("summary", {}),
        "failures": failures,
    }


def build_markdown(report: dict) -> str:
    summary = report["summary"]
    evaluation_summary = report.get("evaluation_summary") or {}
    failures = report["failures"]
    lines = [
        "# Retrieval Triage Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total questions: {summary['total_questions']}",
        f"- Total failures / inspect items: {summary['total_failures']}",
        f"- Answer expected failures: {summary['answer_expected_failures']}",
        f"- Fallback expected failures: {summary['fallback_expected_failures']}",
        "",
        "## Metric Snapshot",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for key in [
        "document_hit_at_1",
        "document_hit_at_3",
        "article_hit_at_1",
        "article_hit_at_3",
        "expected_terms_hit_rate",
        "fallback_accuracy",
        "critical_failure_count",
    ]:
        value = evaluation_summary.get(key)
        if isinstance(value, float):
            value = f"{value:.3f}"
        lines.append(f"| {key} | {value if value is not None else 'n/a'} |")

    lines.extend(["", "## Failure Type Distribution", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["failures_by_type"].items())
    lines.extend(["", "## Possible Root Cause Distribution", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["possible_root_cause_counts"].items())
    lines.extend(["", "## Category-Level Issues", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["failures_by_category"].items())
    lines.extend(["", "## Top Priority Items", ""])
    if not summary["top_priority_ids"]:
        lines.append("- Yok")
    else:
        lines.extend(f"- `{item}`" for item in summary["top_priority_ids"])

    lines.extend(["", "## First 10 Detailed Items", ""])
    for item in failures[:10]:
        lines.extend(
            [
                f"- `{item['id']}`: `{item['failure_type']}` / `{item['possible_root_cause']}` / `{item['priority']}`",
                f"  - Question: {item['question']}",
                f"  - Expected document: {item.get('expected_document') or '-'}",
                f"  - Top document: {item.get('top_document') or '-'}",
                f"  - Recommended action: {item['recommended_action']}",
            ]
        )

    lines.extend(
        [
            "",
            "## General Improvement Areas",
            "",
            "- Query vocabulary, Turkish character normalization, and synonym handling.",
            "- Metadata title/document alias matching against source inventory.",
            "- Article metadata extraction and tolerant article-title matching.",
            "- Evaluation-driven relevance threshold review.",
            "- Source manifest and ChromaDB source inventory consistency checks.",
            "- OCR/chunking review for suspicious sources.",
            "",
            "No question-specific hard-coded patch should be made from this report alone.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triage retrieval evaluation failures.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--markdown-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evaluation_report = load_json(args.report)
    golden_questions = load_json(args.golden)
    report = build_triage_report(evaluation_report, golden_questions)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
