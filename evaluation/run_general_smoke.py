"""Run retrieval/source-panel smoke checks for broad RAG coverage.

This script intentionally avoids LLM calls. It measures whether retrieval,
metadata rerank, relevance filtering, and source-panel candidate generation
behave plausibly across a representative question set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("MULTI_QUERY_ENABLED", "false")
os.environ.setdefault("FLASHRANK_ENABLED", "false")

from rag_engine import (  # noqa: E402
    SelcukRAGEngine,
    build_safe_fallback,
    classify_query_type,
    prepare_context_and_sources,
)


TRIAGE_STATUSES = {
    "ok",
    "answer_expected_without_source",
    "fallback_expected_with_source",
    "inspect_top_document",
    "no_retrieval_result",
}


def _load_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Question file must contain a JSON list.")
    return data


def _source_label(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    label = (
        metadata.get("source_title")
        or metadata.get("title")
        or metadata.get("source")
        or metadata.get("file_name")
    )
    return unquote(str(label)) if label else None


def _article_label(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    article_no = metadata.get("article_no")
    article_title = metadata.get("article_title")
    parts = []
    if article_no not in (None, ""):
        parts.append(f"Madde {article_no}")
    if article_title:
        parts.append(str(article_title))
    return " - ".join(parts) if parts else None


def _fold_text(text: str | None) -> str:
    text = unquote(str(text or "")).casefold()
    text = text.replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _contains_hint(text: str | None, hint: str | None) -> bool | None:
    if not hint:
        return None
    return _fold_text(hint) in _fold_text(text)


def determine_triage_status(result: dict) -> str:
    if result["retrieved_doc_count"] == 0:
        return "no_retrieval_result"
    if result["expected_behavior"] == "answer" and not result["has_relevant_source"]:
        return "answer_expected_without_source"
    if result["expected_behavior"] == "fallback" and result["has_relevant_source"]:
        return "fallback_expected_with_source"
    if result.get("expected_document_match") is False or result.get("expected_article_match") is False:
        return "inspect_top_document"
    return "ok"


def evaluate_question(engine: SelcukRAGEngine, item: dict) -> dict:
    question = item["question"]
    retrieved_docs = engine.retrieve(question)
    prepared = prepare_context_and_sources(question, retrieved_docs)
    filtered_docs = prepared["docs"]
    sources = prepared["sources"]
    top_doc = filtered_docs[0] if filtered_docs else None
    top_metadata = getattr(top_doc, "metadata", {}) if top_doc else {}
    query_type = classify_query_type(question)
    should_fallback = not filtered_docs
    fallback_text = build_safe_fallback(question, filtered_docs, query_type) if should_fallback else None
    top_document = _source_label(top_metadata)
    top_article = _article_label(top_metadata)
    expected_document_match = _contains_hint(top_document, item.get("expected_document_hint"))
    expected_article_match = _contains_hint(top_article, item.get("expected_article_hint"))

    result = {
        "id": item["id"],
        "question": question,
        "category": item.get("category"),
        "expected_behavior": item.get("expected_behavior"),
        "query_type": query_type,
        "retrieved_doc_count": len(retrieved_docs),
        "filtered_doc_count": len(filtered_docs),
        "top_document": top_document,
        "top_article": top_article,
        "expected_document_hint": item.get("expected_document_hint"),
        "expected_article_hint": item.get("expected_article_hint"),
        "expected_document_match": expected_document_match,
        "expected_article_match": expected_article_match,
        "has_relevant_source": bool(filtered_docs),
        "should_fallback": should_fallback,
        "source_panel_candidate_count": len(sources),
        "source_panel_top_label": sources[0]["label"] if sources else None,
        "fallback_text": fallback_text,
    }
    result["triage_status"] = determine_triage_status(result)
    return result


def build_summary(questions: list[dict], results: list[dict]) -> dict:
    categories = Counter(item.get("category", "unknown") for item in questions)
    expected = Counter(item.get("expected_behavior", "unknown") for item in questions)
    fallback_count = sum(1 for item in results if item["should_fallback"])
    answer_expected_without_source = [
        item["id"]
        for item in results
        if item["expected_behavior"] == "answer" and not item["has_relevant_source"]
    ]
    fallback_expected_with_source = [
        item["id"]
        for item in results
        if item["expected_behavior"] == "fallback" and item["has_relevant_source"]
    ]
    top_document_mismatch_ids = [
        item["id"]
        for item in results
        if item["expected_document_match"] is False
    ]
    article_hint_mismatches = [
        item["id"]
        for item in results
        if item["expected_article_match"] is False
    ]
    return {
        "total_questions": len(questions),
        "category_counts": dict(sorted(categories.items())),
        "expected_behavior_counts": dict(sorted(expected.items())),
        "smoke_fallback_count": fallback_count,
        "answer_expected_without_source_count": len(answer_expected_without_source),
        "fallback_expected_with_source_count": len(fallback_expected_with_source),
        "answer_expected_without_source_ids": answer_expected_without_source,
        "fallback_expected_with_source_ids": fallback_expected_with_source,
        "top_document_mismatch_ids": top_document_mismatch_ids,
        "article_hint_mismatches": article_hint_mismatches,
        "triage_status_counts": dict(sorted(Counter(item["triage_status"] for item in results).items())),
    }


def build_report(questions: list[dict], results: list[dict], questions_path: Path) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": generated_at,
        "questions_file": str(questions_path),
        "llm_calls": False,
        "summary": {
            "generated_at": generated_at,
            **build_summary(questions, results),
        },
        "results": results,
    }


def _format_list(items: list[str]) -> str:
    if not items:
        return "- Yok\n"
    return "".join(f"- `{item}`\n" for item in items)


def build_markdown_summary(report: dict) -> str:
    summary = report["summary"]
    risky = [
        item for item in report["results"]
        if item["triage_status"] != "ok"
    ][:5]
    lines = [
        "# General Smoke Evaluation Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total questions: {summary['total_questions']}",
        f"- Smoke fallback count: {summary['smoke_fallback_count']}",
        f"- Answer expected without source: {summary['answer_expected_without_source_count']}",
        f"- Fallback expected with source: {summary['fallback_expected_with_source_count']}",
        "",
        "## Category Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["category_counts"].items())
    lines.extend(["", "## Expected Behavior Counts", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["expected_behavior_counts"].items())
    lines.extend(["", "## Triage Status Counts", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["triage_status_counts"].items())
    lines.extend(["", "## Answer Expected Without Source", "", _format_list(summary["answer_expected_without_source_ids"])])
    lines.extend(["", "## Fallback Expected With Source", "", _format_list(summary["fallback_expected_with_source_ids"])])
    lines.extend(["", "## First Risky Examples", ""])
    if not risky:
        lines.append("- Yok")
    for item in risky:
        lines.extend([
            f"- `{item['id']}`: {item['triage_status']}",
            f"  - Question: {item['question']}",
            f"  - Top document: {item.get('top_document') or '-'}",
            f"  - Filtered docs: {item['filtered_doc_count']}",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run broad retrieval smoke checks.")
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    questions = _load_questions(args.questions)
    engine = SelcukRAGEngine(enable_llm=False)
    results = [evaluate_question(engine, item) for item in questions]
    report = build_report(questions, results, args.questions)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(build_markdown_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_critical and report["summary"]["answer_expected_without_source_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
