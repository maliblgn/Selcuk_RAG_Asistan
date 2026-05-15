"""Audit source inventory aliases and golden document expectations.

This script is read-only: it inspects ChromaDB metadata, golden questions, and
retrieval alias config without changing runtime behavior or golden data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.evaluate_retrieval import DEFAULT_DB, load_questions, read_chroma_documents
from retrieval_normalization import (
    article_metadata_score,
    article_title_similarity_score,
    document_alias_score,
    load_retrieval_aliases,
    normalize_article_no,
    normalize_text,
    title_similarity_score,
    tokenize_for_match,
)


DEFAULT_GOLDEN = ROOT_DIR / "evaluation" / "golden_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "source_inventory_alias_audit.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "source_inventory_alias_audit.local.md"

SUSPECTED_ISSUES = {
    "expected_document_not_in_inventory",
    "expected_document_alias_missing",
    "expected_document_too_strict",
    "inventory_title_encoded_or_variant",
    "article_title_too_strict",
    "article_no_present_but_title_variant",
    "likely_golden_expectation_review",
    "likely_source_metadata_issue",
    "needs_manual_review",
}

RECOMMENDED_ACTIONS = {
    "add_document_alias",
    "relax_golden_expected_document_alias",
    "review_expected_article_title",
    "review_source_metadata_title",
    "review_chunking_or_ocr",
    "no_action_needed",
}


def _metadata_label(metadata: dict) -> str:
    return " ".join(
        str(part or "")
        for part in (
            metadata.get("source_title"),
            metadata.get("title"),
            metadata.get("file_name"),
            metadata.get("source"),
            metadata.get("url"),
        )
    )


def _source_key(doc: dict) -> str:
    metadata = doc.get("metadata") or {}
    label = _metadata_label(metadata) or doc.get("source") or doc.get("title") or ""
    return normalize_text(label) or str(doc.get("id") or "")


def build_source_inventory(db_path: str | os.PathLike[str] = DEFAULT_DB) -> list[dict]:
    """Read ChromaDB and return unique source-level inventory records."""

    docs = read_chroma_documents(db_path)
    if not docs:
        raise RuntimeError(f"ChromaDB source inventory could not be read from {db_path}")

    grouped: dict[str, dict] = {}
    article_titles: dict[str, set[str]] = defaultdict(set)
    article_numbers: dict[str, set[str]] = defaultdict(set)
    source_types: dict[str, set[str]] = defaultdict(set)
    chunk_counts: Counter[str] = Counter()

    for doc in docs:
        metadata = doc.get("metadata") or {}
        key = _source_key(doc)
        if key not in grouped:
            grouped[key] = {
                "key": key,
                "title": metadata.get("source_title") or metadata.get("title") or doc.get("title") or "",
                "file_name": metadata.get("file_name") or "",
                "source": metadata.get("source") or doc.get("source") or "",
                "url": metadata.get("url") or metadata.get("source_url") or "",
                "source_type": metadata.get("source_type") or "",
                "normalized_label": key,
            }
        if metadata.get("article_title"):
            article_titles[key].add(str(metadata["article_title"]))
        article_no = normalize_article_no(str(metadata.get("article_no") or ""))
        if article_no:
            article_numbers[key].add(article_no)
        if metadata.get("source_type"):
            source_types[key].add(str(metadata["source_type"]))
        chunk_counts[key] += 1

    inventory = []
    for key, record in grouped.items():
        item = dict(record)
        item["chunk_count"] = chunk_counts[key]
        item["article_titles"] = sorted(article_titles[key])
        item["article_numbers"] = sorted(article_numbers[key], key=lambda value: int(value) if value.isdigit() else 9999)
        item["source_types"] = sorted(source_types[key])
        item["search_text"] = normalize_text(
            " ".join(
                str(part or "")
                for part in (
                    item["title"],
                    item["file_name"],
                    item["source"],
                    item["url"],
                    item["source_type"],
                )
            )
        )
        inventory.append(item)
    return sorted(inventory, key=lambda item: (item["title"], item["source"], item["key"]))


def load_alias_config(path: str | Path = ROOT_DIR / "config" / "retrieval_aliases.json") -> dict:
    return load_retrieval_aliases(path)


def _golden_document_values(item: dict) -> list[str]:
    values = []
    if item.get("expected_document"):
        values.append(item["expected_document"])
    values.extend(item.get("expected_document_aliases") or [])
    return [value for value in values if str(value or "").strip()]


def _is_exact_document_match(expected_document: str, source: dict) -> bool:
    expected_norm = normalize_text(expected_document)
    haystack = source.get("search_text") or ""
    return bool(expected_norm and (expected_norm in haystack or haystack in expected_norm))


def _is_alias_document_match(values: list[str], source: dict, alias_config: dict) -> bool:
    haystack = source.get("search_text") or ""
    if any(normalize_text(value) and normalize_text(value) in haystack for value in values):
        return True
    if any(title_similarity_score(value, haystack) >= 4.0 for value in values):
        return True
    if any(document_alias_score(value, haystack, alias_config) >= 3.0 for value in values):
        return True
    return False


def _token_overlap_score(values: list[str], source: dict) -> float:
    query_tokens = set()
    for value in values:
        query_tokens.update(tokenize_for_match(value))
    source_tokens = tokenize_for_match(source.get("search_text") or "")
    if not query_tokens or not source_tokens:
        return 0.0
    overlap = query_tokens & source_tokens
    return len(overlap) / max(len(query_tokens), 1)


def find_document_match(item: dict, inventory: list[dict], alias_config: dict) -> dict:
    values = _golden_document_values(item)
    expected_document = item.get("expected_document") or ""
    exact_matches = [source for source in inventory if _is_exact_document_match(expected_document, source)]
    if exact_matches:
        return {"match_type": "exact", "source": exact_matches[0], "score": 1.0}

    alias_matches = [source for source in inventory if _is_alias_document_match(values, source, alias_config)]
    if alias_matches:
        alias_matches.sort(key=lambda source: _token_overlap_score(values, source), reverse=True)
        return {"match_type": "alias", "source": alias_matches[0], "score": _token_overlap_score(values, alias_matches[0])}

    candidates = sorted(
        ((_token_overlap_score(values, source), source) for source in inventory),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best_source = candidates[0] if candidates else (0.0, None)
    return {"match_type": "missing", "source": best_source, "score": best_score}


def proposed_aliases_for(item: dict, source: dict | None) -> list[str]:
    if not source:
        return []
    proposals = []
    for value in (source.get("title"), source.get("file_name")):
        normalized = normalize_text(value or "")
        if normalized and normalized not in proposals:
            proposals.append(normalized)
    expected = normalize_text(item.get("expected_document") or "")
    if expected and expected not in proposals:
        proposals.append(expected)
    return proposals[:5]


def _article_issue(item: dict, source: dict | None) -> tuple[str | None, str]:
    expected_no = normalize_article_no(str(item.get("expected_article_no") or ""))
    expected_title = item.get("expected_article_title") or ""
    if not expected_no and not expected_title:
        return None, "no_action_needed"
    if not source:
        return "likely_source_metadata_issue", "review_source_metadata_title"

    article_numbers = set(source.get("article_numbers") or [])
    article_titles = source.get("article_titles") or []
    best_title_score = max(
        [article_title_similarity_score(expected_title, title) for title in article_titles] or [0.0]
    )

    if expected_no and expected_no not in article_numbers:
        return "likely_source_metadata_issue", "review_chunking_or_ocr"
    if expected_title and best_title_score < 4.0:
        return "article_title_too_strict", "review_expected_article_title"
    if expected_title and best_title_score < 6.0:
        return "article_no_present_but_title_variant", "review_expected_article_title"
    metadata_score = max(
        [article_metadata_score(expected_no, expected_title, no, title, "") for no in article_numbers for title in article_titles]
        or [0.0]
    )
    if metadata_score >= 5.0:
        return None, "no_action_needed"
    return "needs_manual_review", "review_source_metadata_title"


def classify_golden_item(item: dict, match: dict) -> dict:
    source = match.get("source")
    match_type = match["match_type"]
    article_issue, article_action = _article_issue(item, source)
    suspected_issue = None
    recommended_action = "no_action_needed"

    if match_type == "missing":
        if match.get("score", 0.0) >= 0.35:
            suspected_issue = "expected_document_alias_missing"
            recommended_action = "add_document_alias"
        else:
            suspected_issue = "expected_document_not_in_inventory"
            recommended_action = "review_source_metadata_title"
    elif match_type == "alias":
        suspected_issue = "expected_document_too_strict"
        recommended_action = "relax_golden_expected_document_alias"

    if article_issue and (suspected_issue is None or match_type != "missing"):
        suspected_issue = article_issue
        recommended_action = article_action

    if suspected_issue is None:
        suspected_issue = "likely_golden_expectation_review" if match_type == "alias" else "needs_manual_review"
        recommended_action = "no_action_needed"

    priority = "high" if suspected_issue in {"expected_document_not_in_inventory", "likely_source_metadata_issue"} else "medium"
    if recommended_action == "no_action_needed":
        priority = "low"

    return {
        "id": item.get("id"),
        "question": item.get("question"),
        "category": item.get("category"),
        "expected_behavior": item.get("expected_behavior"),
        "expected_document": item.get("expected_document"),
        "expected_document_aliases": item.get("expected_document_aliases") or [],
        "expected_article_no": item.get("expected_article_no"),
        "expected_article_title": item.get("expected_article_title"),
        "document_match_type": match_type,
        "match_score": match.get("score", 0.0),
        "matched_source_title": (source or {}).get("title"),
        "matched_source_file_name": (source or {}).get("file_name"),
        "matched_source": (source or {}).get("source"),
        "matched_article_numbers": (source or {}).get("article_numbers") or [],
        "suspected_issue": suspected_issue,
        "recommended_action": recommended_action,
        "proposed_aliases": proposed_aliases_for(item, source) if recommended_action == "add_document_alias" else [],
        "priority": priority,
    }


def build_audit_report(golden_questions: list[dict], inventory: list[dict], alias_config: dict) -> dict:
    question_items = [item for item in golden_questions if item.get("expected_document")]
    issues = []
    all_items = []
    for item in question_items:
        match = find_document_match(item, inventory, alias_config)
        audit_item = classify_golden_item(item, match)
        all_items.append(audit_item)
        if audit_item["document_match_type"] != "exact" or audit_item["recommended_action"] != "no_action_needed":
            issues.append(audit_item)

    exact_count = sum(1 for item in all_items if item["document_match_type"] == "exact")
    alias_count = sum(1 for item in all_items if item["document_match_type"] == "alias")
    missing_count = sum(1 for item in all_items if item["document_match_type"] == "missing")
    alias_candidates = [alias for item in issues for alias in item.get("proposed_aliases") or []]
    high_ids = [item["id"] for item in issues if item["priority"] == "high"][:10]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_sources": len(inventory),
        "total_golden_questions": len(golden_questions),
        "questions_with_expected_document": len(question_items),
        "exact_document_matches": exact_count,
        "alias_document_matches": alias_count,
        "missing_document_matches": missing_count,
        "alias_candidate_count": len(set(alias_candidates)),
        "article_expectation_review_count": sum(
            1 for item in issues if item["recommended_action"] == "review_expected_article_title"
        ),
        "likely_source_metadata_issue_count": sum(
            1 for item in issues if item["suspected_issue"] == "likely_source_metadata_issue"
        ),
        "top_priority_ids": high_ids,
        "issues_by_type": dict(sorted(Counter(item["suspected_issue"] for item in issues).items())),
        "recommended_actions_count": dict(sorted(Counter(item["recommended_action"] for item in issues).items())),
    }
    return {"summary": summary, "issues": issues, "items": all_items}


def build_markdown(report: dict) -> str:
    summary = report["summary"]
    issues = report["issues"]
    lines = [
        "# Source Inventory Alias Audit",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total sources: {summary['total_sources']}",
        f"- Golden questions: {summary['total_golden_questions']}",
        f"- Questions with expected document: {summary['questions_with_expected_document']}",
        f"- Exact document matches: {summary['exact_document_matches']}",
        f"- Alias document matches: {summary['alias_document_matches']}",
        f"- Missing document matches: {summary['missing_document_matches']}",
        f"- Alias candidates: {summary['alias_candidate_count']}",
        f"- Article expectation review count: {summary['article_expectation_review_count']}",
        f"- Likely source metadata issue count: {summary['likely_source_metadata_issue_count']}",
        "",
        "## Issues By Type",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["issues_by_type"].items())
    lines.extend(["", "## Recommended Actions", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["recommended_actions_count"].items())
    lines.extend(["", "## Top Priority Items", ""])
    if not summary["top_priority_ids"]:
        lines.append("- Yok")
    else:
        lines.extend(f"- `{item}`" for item in summary["top_priority_ids"])

    alias_items = [item for item in issues if item["recommended_action"] == "add_document_alias"]
    lines.extend(["", "## Proposed Document Aliases", ""])
    if not alias_items:
        lines.append("- Yok")
    for item in alias_items[:20]:
        lines.append(f"- `{item['id']}`: {', '.join(item.get('proposed_aliases') or [])}")

    review_items = [item for item in issues if item["recommended_action"] == "review_expected_article_title"]
    lines.extend(["", "## Golden Expectation Review", ""])
    if not review_items:
        lines.append("- Yok")
    for item in review_items[:20]:
        lines.append(
            f"- `{item['id']}`: expected `{item.get('expected_article_no') or '-'} {item.get('expected_article_title') or ''}`; matched source `{item.get('matched_source_title') or '-'}`"
        )

    metadata_items = [item for item in issues if item["recommended_action"] in {"review_source_metadata_title", "review_chunking_or_ocr"}]
    lines.extend(["", "## Source Metadata / Chunking Review", ""])
    if not metadata_items:
        lines.append("- Yok")
    for item in metadata_items[:20]:
        lines.append(f"- `{item['id']}`: `{item['suspected_issue']}` / `{item['recommended_action']}`")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit source inventory aliases and golden expectations.")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN), help="Golden questions JSON path.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB), help="Chroma sqlite path or persist directory.")
    parser.add_argument("--out", default=str(DEFAULT_JSON_OUT), help="JSON output path.")
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT), help="Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    questions = load_questions(args.golden)
    inventory = build_source_inventory(args.db_path)
    alias_config = load_alias_config()
    report = build_audit_report(questions, inventory, alias_config)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
