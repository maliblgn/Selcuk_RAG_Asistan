"""Audit golden article metadata against production retrieval output."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("MULTI_QUERY_ENABLED", "false")
os.environ.setdefault("FLASHRANK_ENABLED", "false")

from evaluation.evaluate_retrieval import evaluate_golden_question, load_questions
from rag_engine import SelcukRAGEngine, prepare_context_and_sources
from retrieval_normalization import (
    article_metadata_score,
    article_title_similarity_score,
    extract_article_numbers,
    normalize_article_no,
    normalize_article_title,
)


DEFAULT_GOLDEN = ROOT_DIR / "evaluation" / "golden_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "article_metadata_audit.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "article_metadata_audit.local.md"

SUSPECTED_ISSUES = {
    "missing_article_metadata",
    "article_no_format_mismatch",
    "article_title_partial_mismatch",
    "content_has_article_but_metadata_mismatch",
    "likely_golden_expectation_too_strict",
    "needs_manual_review",
}


def _doc_to_dict(doc: Any) -> dict:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    return {
        "content": getattr(doc, "page_content", "") or "",
        "metadata": metadata,
    }


def _top_filtered_doc(engine: SelcukRAGEngine, question: str) -> dict | None:
    retrieved_docs = engine.retrieve(question)
    prepared = prepare_context_and_sources(question, retrieved_docs)
    docs = prepared.get("docs") or []
    if not docs:
        return None
    return _doc_to_dict(docs[0])


def _classify_issue(item: dict, top_doc: dict | None, evaluation_result: dict) -> str:
    if not top_doc:
        return "missing_article_metadata"

    metadata = top_doc.get("metadata") or {}
    content = top_doc.get("content") or ""
    expected_no = normalize_article_no(str(item.get("expected_article_no") or ""))
    actual_no_raw = str(metadata.get("article_no") or "")
    actual_no = normalize_article_no(actual_no_raw)
    expected_title = item.get("expected_article_title") or ""
    actual_title = metadata.get("article_title") or ""
    content_numbers = extract_article_numbers(f"{actual_title} {content[:3000]}")
    metadata_score = article_metadata_score(expected_no, expected_title, actual_no_raw, actual_title, content)

    if expected_no and not actual_no and not content_numbers:
        return "missing_article_metadata"
    if expected_no and actual_no_raw and actual_no == expected_no and actual_no_raw.strip() != expected_no:
        return "article_no_format_mismatch"
    if expected_no and expected_no in content_numbers and actual_no != expected_no:
        return "content_has_article_but_metadata_mismatch"
    if expected_title and article_title_similarity_score(expected_title, actual_title, content) >= 4.0:
        if evaluation_result.get("evaluation_status") == "article_miss":
            return "likely_golden_expectation_too_strict"
        return "article_title_partial_mismatch"
    if metadata_score >= 5.0:
        return "likely_golden_expectation_too_strict"
    if expected_title and normalize_article_title(expected_title) and not normalize_article_title(actual_title):
        return "missing_article_metadata"
    return "needs_manual_review"


def build_audit(golden_questions: list[dict]) -> dict:
    engine = SelcukRAGEngine(enable_llm=False)
    answer_questions = [item for item in golden_questions if item.get("expected_behavior") == "answer"]
    article_questions = [
        item for item in answer_questions if item.get("expected_article_no") or item.get("expected_article_title")
    ]
    items = []
    for item in article_questions:
        evaluation_result = evaluate_golden_question(engine, item)
        top_doc = _top_filtered_doc(engine, item["question"])
        metadata = (top_doc or {}).get("metadata") or {}
        content = (top_doc or {}).get("content") or ""
        actual_title = metadata.get("article_title") or ""
        candidates = sorted(extract_article_numbers(f"{actual_title} {content[:3000]}"))
        issue = _classify_issue(item, top_doc, evaluation_result)
        items.append(
            {
                "id": item.get("id"),
                "question": item.get("question"),
                "expected_document": item.get("expected_document"),
                "expected_article_no": item.get("expected_article_no"),
                "expected_article_title": item.get("expected_article_title"),
                "top_document": evaluation_result.get("top_document"),
                "top_article_no": evaluation_result.get("top_article_no"),
                "top_article_title": evaluation_result.get("top_article_title"),
                "content_article_phrase_candidates": candidates,
                "evaluation_status": evaluation_result.get("evaluation_status"),
                "suspected_issue": issue,
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_answer_questions": len(answer_questions),
        "questions_with_expected_article": len(article_questions),
        "article_miss_candidates": sum(1 for item in items if item["evaluation_status"] == "article_miss"),
        "missing_article_no_count": sum(1 for item in items if not item.get("top_article_no")),
        "missing_article_title_count": sum(1 for item in items if not item.get("top_article_title")),
        "content_article_phrase_found_count": sum(1 for item in items if item.get("content_article_phrase_candidates")),
        "suspected_metadata_mismatch_count": sum(
            1
            for item in items
            if item["suspected_issue"]
            in {"article_no_format_mismatch", "article_title_partial_mismatch", "content_has_article_but_metadata_mismatch"}
        ),
        "suspected_issue_counts": dict(sorted(Counter(item["suspected_issue"] for item in items).items())),
    }
    return {"summary": summary, "items": items}


def build_markdown(report: dict) -> str:
    summary = report["summary"]
    items = report["items"]
    lines = [
        "# Article Metadata Audit",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total answer questions: {summary['total_answer_questions']}",
        f"- Questions with expected article: {summary['questions_with_expected_article']}",
        f"- Article miss candidates: {summary['article_miss_candidates']}",
        f"- Missing article_no count: {summary['missing_article_no_count']}",
        f"- Missing article_title count: {summary['missing_article_title_count']}",
        f"- Content article phrase found count: {summary['content_article_phrase_found_count']}",
        f"- Suspected metadata mismatch count: {summary['suspected_metadata_mismatch_count']}",
        "",
        "## Suspected Issue Distribution",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["suspected_issue_counts"].items())
    lines.extend(["", "## Article Miss / Inspect Candidates", ""])
    relevant = [item for item in items if item["evaluation_status"] != "ok" or item["suspected_issue"] != "needs_manual_review"]
    if not relevant:
        lines.append("- Yok")
    for item in relevant[:20]:
        lines.extend(
            [
                f"- `{item['id']}`: `{item['evaluation_status']}` / `{item['suspected_issue']}`",
                f"  - Expected: {item.get('expected_article_no') or '-'} {item.get('expected_article_title') or ''}".rstrip(),
                f"  - Top: {item.get('top_article_no') or '-'} {item.get('top_article_title') or ''}".rstrip(),
                f"  - Content candidates: {', '.join(item.get('content_article_phrase_candidates') or []) or '-'}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit article metadata for golden retrieval questions.")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN), help="Golden questions JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_JSON_OUT), help="JSON output path.")
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT), help="Markdown summary output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    questions = load_questions(args.golden)
    report = build_audit(questions)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
