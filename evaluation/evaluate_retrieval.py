"""Evaluate golden retrieval questions without making LLM calls.

The main CLI uses the production retrieval/filtering/source mapping path and
emits Faz 5A metrics. A small set of legacy BM25 helpers is kept for older
unit tests and historical comparison scripts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("MULTI_QUERY_ENABLED", "false")
os.environ.setdefault("FLASHRANK_ENABLED", "false")

try:
    from evaluation.retrieval_rerank import detect_query_intent, rerank_results
except ImportError:  # pragma: no cover - direct script execution fallback
    from retrieval_rerank import detect_query_intent, rerank_results

from rag_engine import SelcukRAGEngine, prepare_context_and_sources
from retrieval_normalization import (
    article_match_score,
    article_metadata_score,
    article_title_similarity_score,
    document_alias_score,
    extract_article_numbers,
    load_retrieval_aliases,
    normalize_article_no,
    normalize_text as shared_normalize_text,
    title_similarity_score,
)


DEFAULT_DB = ROOT_DIR / "chroma_db" / "chroma.sqlite3"
DEFAULT_GOLDEN = ROOT_DIR / "evaluation" / "golden_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "retrieval_evaluation_report.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "retrieval_evaluation_summary.local.md"
ARTICLE_RE = re.compile(r"(?im)(?:^|\n)\s*MADDE\s+(\d+)\s*[-–]?\s*")

EVALUATION_STATUSES = {
    "ok",
    "document_miss",
    "article_miss",
    "expected_terms_miss",
    "fallback_mismatch",
    "no_source_for_answer",
    "inspect",
}


def normalize_text(value: Any) -> str:
    """Normalize Turkish text, mojibake-ish legacy fixtures, and URL escapes."""
    return shared_normalize_text(value)


def _legacy_normalize_text(value: Any) -> str:
    """Legacy implementation kept only for reference while tests use wrapper."""

    text = unquote(str(value or ""))
    replacements = {
        "Ä°": "i",
        "I": "i",
        "ı": "i",
        "Ä±": "i",
        "Ğ": "g",
        "ğ": "g",
        "Ä": "g",
        "ÄŸ": "g",
        "Ü": "u",
        "ü": "u",
        "Ãœ": "u",
        "Ã¼": "u",
        "Ş": "s",
        "ş": "s",
        "Å": "s",
        "ÅŸ": "s",
        "Ö": "o",
        "ö": "o",
        "Ã–": "o",
        "Ã¶": "o",
        "Ç": "c",
        "ç": "c",
        "Ã‡": "c",
        "Ã§": "c",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokenize(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", normalize_text(value))


def resolve_db_path(db_path: str | os.PathLike[str] = DEFAULT_DB) -> str:
    path = Path(db_path)
    if path.is_dir():
        return str(path / "chroma.sqlite3")
    return str(path)


def metadata_value(row: tuple[Any, ...]) -> Any:
    _id, _key, string_value, int_value, float_value, bool_value = row
    if string_value is not None:
        return string_value
    if int_value is not None:
        return int_value
    if float_value is not None:
        return float_value
    if bool_value is not None:
        return bool(bool_value)
    return None


def read_chroma_documents(db_path: str | os.PathLike[str] = DEFAULT_DB) -> list[dict]:
    db_file = resolve_db_path(db_path)
    if not os.path.exists(db_file):
        return []

    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT id, key, string_value, int_value, float_value, bool_value
            FROM embedding_metadata
            """
        ).fetchall()
    finally:
        conn.close()

    metadata_by_id: dict[Any, dict] = defaultdict(dict)
    documents_by_id: dict[Any, str] = {}
    for row in rows:
        item_id, key = row[0], row[1]
        value = metadata_value(row)
        if key == "chroma:document":
            documents_by_id[item_id] = value or ""
        else:
            metadata_by_id[item_id][key] = value

    docs = []
    for item_id in sorted(set(metadata_by_id) | set(documents_by_id)):
        metadata = metadata_by_id.get(item_id, {})
        docs.append(
            {
                "id": item_id,
                "content": documents_by_id.get(item_id, ""),
                "metadata": metadata,
                "source": metadata.get("source") or "",
                "title": metadata.get("source_title") or metadata.get("title") or "",
                "page": metadata.get("page"),
            }
        )
    return docs


def article_numbers_from_content(content: str) -> list[str]:
    numbers: list[str] = []
    seen: set[str] = set()
    for match in ARTICLE_RE.finditer(content or ""):
        number = match.group(1)
        if number not in seen:
            seen.add(number)
            numbers.append(number)
    return numbers


def result_article_numbers(result: dict) -> list[str]:
    metadata = result.get("metadata") or {}
    article_no = metadata.get("article_no")
    if article_no not in (None, ""):
        normalized = normalize_article_no(str(article_no))
        return [normalized or str(article_no)]
    return sorted(extract_article_numbers(result.get("content") or "")) or article_numbers_from_content(result.get("content") or "")


def result_label(result: dict) -> str:
    metadata = result.get("metadata") or {}
    return " ".join(
        str(part or "")
        for part in [
            result.get("source"),
            result.get("title"),
            metadata.get("source_title"),
            metadata.get("file_name"),
        ]
    )


def expected_document_matches(result: dict, expected_values: list[str] | None) -> bool:
    haystack = normalize_text(result_label(result))
    if any(normalize_text(value) in haystack for value in (expected_values or [])):
        return True
    alias_config = load_retrieval_aliases()
    for value in expected_values or []:
        if title_similarity_score(value, haystack) >= 4.0:
            return True
        if document_alias_score(value, haystack, alias_config) >= 3.0:
            return True
    return False


def expected_terms_match(results: list[dict], expected_terms: list[str] | None) -> bool:
    haystack = normalize_text(" ".join(result.get("content", "") for result in results))
    return all(normalize_text(term) in haystack for term in (expected_terms or []))


def article_matches(result: dict, expected_article_no: str | None) -> bool:
    if not expected_article_no:
        return False
    expected = normalize_article_no(str(expected_article_no)) or str(expected_article_no)
    return expected in result_article_numbers(result)


def build_bm25_index(docs: list[dict]) -> dict:
    doc_tokens = [tokenize(f"{doc.get('title', '')} {doc.get('content', '')}") for doc in docs]
    doc_freq: Counter[str] = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))
    avg_len = sum(len(tokens) for tokens in doc_tokens) / max(len(doc_tokens), 1)
    return {
        "docs": docs,
        "doc_tokens": doc_tokens,
        "doc_freq": doc_freq,
        "avg_len": avg_len or 1,
        "doc_count": len(docs),
    }


def retrieve(index: dict, query: str, top_k: int = 5) -> list[dict]:
    query_terms = tokenize(query)
    if not query_terms:
        return []
    query_counts = Counter(query_terms)
    k1 = 1.5
    b = 0.75
    scored = []
    for doc, tokens in zip(index["docs"], index["doc_tokens"]):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        score = 0.0
        for term, query_weight in query_counts.items():
            tf = token_counts.get(term, 0)
            if tf == 0:
                continue
            df = index["doc_freq"].get(term, 0)
            idf = math.log(1 + (index["doc_count"] - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * len(tokens) / index["avg_len"])
            score += query_weight * idf * ((tf * (k1 + 1)) / denom)
        if score > 0:
            ranked = dict(doc)
            ranked["score"] = score
            scored.append(ranked)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def hit_at(results: list[dict], predicate, k: int) -> bool:
    return any(predicate(result) for result in results[:k])


def serialize_top_results(results: list[dict]) -> list[dict]:
    serialized = []
    for rank, result in enumerate(results, start=1):
        article_numbers = result_article_numbers(result)
        metadata = result.get("metadata") or {}
        serialized.append(
            {
                "rank": rank,
                "source": result.get("source", ""),
                "title": result.get("title", ""),
                "page": result.get("page"),
                "article_no": metadata.get("article_no") or (article_numbers[0] if article_numbers else None),
                "article_title": metadata.get("article_title"),
                "score": result.get("score"),
                "rerank_score": result.get("rerank_score"),
                "rerank_explanation": result.get("rerank_explanation", []),
                "content_preview": " ".join((result.get("content") or "").split())[:500],
            }
        )
    return serialized


def evaluate_question_bm25(index: dict, question: dict, top_k: int = 5, candidate_k: int | None = None, metadata_rerank: bool = False) -> dict:
    candidate_k = candidate_k or top_k
    results = retrieve(index, question["question"], top_k=candidate_k)
    intent = detect_query_intent(question["question"])
    if metadata_rerank:
        results = rerank_results(question["question"], results)
    results = results[:top_k]
    expected_doc = question.get("expected_document_contains") or question.get("expected_document_aliases") or []
    expected_article_no = question.get("expected_article_no")
    expected_terms = question.get("expected_answer_terms") or question.get("expected_terms") or []

    return {
        "id": question["id"],
        "question": question["question"],
        "expected_article_no": expected_article_no,
        "intent": intent["intent"],
        "acronym_terms": intent["acronym_terms"],
        "top_results": serialize_top_results(results),
        "document_hit_at_1": hit_at(results, lambda result: expected_document_matches(result, expected_doc), 1),
        "document_hit_at_3": hit_at(results, lambda result: expected_document_matches(result, expected_doc), 3),
        "document_hit_at_5": hit_at(results, lambda result: expected_document_matches(result, expected_doc), min(5, top_k)),
        "article_hit_at_1": hit_at(results, lambda result: article_matches(result, expected_article_no), 1),
        "article_hit_at_3": hit_at(results, lambda result: article_matches(result, expected_article_no), 3),
        "article_hit_at_5": hit_at(results, lambda result: article_matches(result, expected_article_no), min(5, top_k)),
        "expected_terms_hit_at_5": expected_terms_match(results[: min(5, top_k)], expected_terms),
    }


def metric_ratio(results: list[dict], key: str) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if result.get(key)) / len(results)


def compute_metrics(results: list[dict]) -> dict:
    return {
        "document_hit_at_1": metric_ratio(results, "document_hit_at_1"),
        "document_hit_at_3": metric_ratio(results, "document_hit_at_3"),
        "document_hit_at_5": metric_ratio(results, "document_hit_at_5"),
        "article_hit_at_1": metric_ratio(results, "article_hit_at_1"),
        "article_hit_at_3": metric_ratio(results, "article_hit_at_3"),
        "article_hit_at_5": metric_ratio(results, "article_hit_at_5"),
        "expected_terms_hit_at_5": metric_ratio(results, "expected_terms_hit_at_5"),
    }


def evaluate(
    questions: list[dict],
    docs: list[dict],
    top_k: int = 5,
    mode: str = "retrieval_baseline_current_index",
    db_path: str | None = None,
    baseline: dict | None = None,
    metadata_rerank: bool = False,
    candidate_k: int | None = None,
) -> dict:
    """Legacy BM25 evaluation entry point used by existing tests."""

    index = build_bm25_index(docs)
    candidate_k = candidate_k or top_k
    results = [
        evaluate_question_bm25(index, question, top_k=top_k, candidate_k=candidate_k, metadata_rerank=metadata_rerank)
        for question in questions
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "retrieval_method": "read_only_sqlite_bm25",
        "db_path": db_path,
        "question_count": len(questions),
        "top_k": top_k,
        "candidate_k": candidate_k,
        "metadata_rerank": metadata_rerank,
        "document_count": len(docs),
        "metrics": compute_metrics(results),
        "results": results,
    }
    if baseline:
        report["baseline"] = baseline
    return report


def _doc_to_dict(doc: Any) -> dict:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    content = getattr(doc, "page_content", None) or getattr(doc, "content", "") or ""
    return {
        "content": content,
        "metadata": metadata,
        "source": metadata.get("source") or "",
        "title": metadata.get("source_title") or metadata.get("title") or metadata.get("file_name") or "",
        "page": metadata.get("page"),
    }


def _source_label_from_metadata(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    label = (
        metadata.get("source_title")
        or metadata.get("title")
        or metadata.get("file_name")
        or metadata.get("source")
    )
    return unquote(str(label)) if label else None


def _article_no(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    article = metadata.get("article_no")
    if article in (None, ""):
        return None
    return normalize_article_no(str(article)) or str(article)


def _article_title(metadata: dict | None) -> str | None:
    metadata = metadata or {}
    title = metadata.get("article_title")
    return str(title) if title else None


def _question_expected_documents(item: dict) -> list[str]:
    values = []
    if item.get("expected_document"):
        values.append(item["expected_document"])
    values.extend(item.get("expected_document_aliases") or [])
    return values


def _document_hit(docs: list[dict], item: dict, k: int) -> bool | None:
    expected = _question_expected_documents(item)
    if not expected:
        return None
    return hit_at(docs, lambda result: expected_document_matches(result, expected), min(k, len(docs)))


def _article_hit(docs: list[dict], item: dict, k: int) -> bool | None:
    expected_no = item.get("expected_article_no")
    expected_title = item.get("expected_article_title")
    if not expected_no and not expected_title:
        return None

    def predicate(result: dict) -> bool:
        metadata = result.get("metadata") or {}
        actual_no = metadata.get("article_no") or ""
        article_title = metadata.get("article_title") or ""
        content = result.get("content") or ""
        expected_no_norm = normalize_article_no(str(expected_no or ""))
        actual_numbers = set(result_article_numbers(result))
        actual_numbers.update(extract_article_numbers(f"{article_title} {content[:3000]}"))
        no_match = True if not expected_no_norm else expected_no_norm in actual_numbers
        metadata_score = article_metadata_score(expected_no, expected_title, actual_no, article_title, content)
        if expected_no_norm and not expected_title:
            return no_match
        if expected_no_norm and expected_title:
            return no_match and metadata_score >= 5.0
        return (
            article_title_similarity_score(expected_title or "", article_title, content) >= 4.0
            or article_match_score(expected_title or "", actual_no, article_title, content) >= 4.0
        )

    return hit_at(docs, predicate, min(k, len(docs)))


def _expected_terms(docs: list[dict], expected_terms: list[str] | None) -> tuple[list[str], list[str]]:
    haystack = normalize_text(" ".join(doc.get("content", "") for doc in docs))
    found = []
    missing = []
    for term in expected_terms or []:
        if normalize_text(term) in haystack:
            found.append(term)
        else:
            missing.append(term)
    return found, missing


def _evaluation_status(result: dict) -> str:
    if result["expected_behavior"] == "fallback":
        return "ok" if result["fallback_predicted"] else "fallback_mismatch"
    if result["filtered_doc_count"] == 0:
        return "no_source_for_answer"
    if result["document_hit_at_3"] is False:
        return "document_miss"
    if result["article_hit_at_3"] is False:
        return "article_miss"
    if result["expected_terms_missing"]:
        return "expected_terms_miss"
    if result["document_hit_at_1"] is False or result["article_hit_at_1"] is False:
        return "inspect"
    return "ok"


def evaluate_golden_question(engine: SelcukRAGEngine, item: dict) -> dict:
    retrieved_docs = engine.retrieve(item["question"])
    prepared = prepare_context_and_sources(item["question"], retrieved_docs)
    filtered_docs_raw = prepared.get("docs") or []
    sources = prepared.get("sources") or []
    retrieved = [_doc_to_dict(doc) for doc in retrieved_docs]
    filtered = [_doc_to_dict(doc) for doc in filtered_docs_raw]
    top_metadata = filtered[0]["metadata"] if filtered else {}
    found_terms, missing_terms = _expected_terms(filtered, item.get("expected_terms"))
    fallback_expected = item.get("expected_behavior") == "fallback"
    fallback_predicted = len(filtered) == 0

    result = {
        "id": item["id"],
        "question": item["question"],
        "category": item.get("category"),
        "expected_behavior": item.get("expected_behavior"),
        "top_document": _source_label_from_metadata(top_metadata),
        "top_article_no": _article_no(top_metadata),
        "top_article_title": _article_title(top_metadata),
        "retrieved_doc_count": len(retrieved),
        "filtered_doc_count": len(filtered),
        "document_hit_at_1": _document_hit(filtered, item, 1),
        "document_hit_at_3": _document_hit(filtered, item, 3),
        "article_hit_at_1": _article_hit(filtered, item, 1),
        "article_hit_at_3": _article_hit(filtered, item, 3),
        "expected_terms_found": found_terms,
        "expected_terms_missing": missing_terms,
        "fallback_expected": fallback_expected,
        "fallback_predicted": fallback_predicted,
        "source_panel_candidate_count": len(sources),
    }
    result["evaluation_status"] = _evaluation_status(result)
    return result


def _ratio(values: list[bool | None]) -> float | None:
    eligible = [value for value in values if value is not None]
    if not eligible:
        return None
    return sum(1 for value in eligible if value) / len(eligible)


def build_faz5a_summary(questions: list[dict], results: list[dict]) -> dict:
    answer_results = [item for item in results if item["expected_behavior"] == "answer"]
    fallback_results = [item for item in results if item["expected_behavior"] == "fallback"]
    total_terms = sum(len(item.get("expected_terms") or []) for item in questions)
    found_terms = sum(len(item.get("expected_terms_found") or []) for item in results)
    critical_statuses = {"document_miss", "fallback_mismatch", "no_source_for_answer"}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_questions": len(questions),
        "answer_questions": len(answer_results),
        "fallback_questions": len(fallback_results),
        "category_counts": dict(sorted(Counter(item.get("category", "unknown") for item in questions).items())),
        "document_hit_at_1": _ratio([item["document_hit_at_1"] for item in answer_results]),
        "document_hit_at_3": _ratio([item["document_hit_at_3"] for item in answer_results]),
        "article_hit_at_1": _ratio([item["article_hit_at_1"] for item in answer_results]),
        "article_hit_at_3": _ratio([item["article_hit_at_3"] for item in answer_results]),
        "expected_terms_hit_rate": (found_terms / total_terms) if total_terms else None,
        "fallback_accuracy": _ratio([item["fallback_predicted"] for item in fallback_results]),
        "source_available_rate": _ratio([item["filtered_doc_count"] > 0 for item in answer_results]),
        "critical_failure_count": sum(1 for item in results if item["evaluation_status"] in critical_statuses),
        "evaluation_status_counts": dict(sorted(Counter(item["evaluation_status"] for item in results).items())),
    }


def evaluate_golden(questions: list[dict]) -> dict:
    engine = SelcukRAGEngine(enable_llm=False)
    results = [evaluate_golden_question(engine, item) for item in questions]
    return {
        "summary": build_faz5a_summary(questions, results),
        "results": results,
        "llm_calls": False,
        "evaluation_method": "production_retrieval_filtering_source_mapping",
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def build_markdown_report(report: dict) -> str:
    summary = report["summary"]
    risky = [item for item in report["results"] if item["evaluation_status"] != "ok"][:10]
    lines = [
        "# Retrieval Evaluation Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Total questions: {summary['total_questions']}",
        f"- Answer questions: {summary['answer_questions']}",
        f"- Fallback questions: {summary['fallback_questions']}",
        f"- Critical failures: {summary['critical_failure_count']}",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| document_hit_at_1 | {_pct(summary['document_hit_at_1'])} |",
        f"| document_hit_at_3 | {_pct(summary['document_hit_at_3'])} |",
        f"| article_hit_at_1 | {_pct(summary['article_hit_at_1'])} |",
        f"| article_hit_at_3 | {_pct(summary['article_hit_at_3'])} |",
        f"| expected_terms_hit_rate | {_pct(summary['expected_terms_hit_rate'])} |",
        f"| fallback_accuracy | {_pct(summary['fallback_accuracy'])} |",
        f"| source_available_rate | {_pct(summary['source_available_rate'])} |",
        "",
        "## Category Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["category_counts"].items())
    lines.extend(["", "## Evaluation Status Counts", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in summary["evaluation_status_counts"].items())
    lines.extend(["", "## First Items To Inspect", ""])
    if not risky:
        lines.append("- Yok")
    for item in risky:
        lines.extend(
            [
                f"- `{item['id']}`: `{item['evaluation_status']}`",
                f"  - Question: {item['question']}",
                f"  - Top document: {item.get('top_document') or '-'}",
                f"  - Top article: {item.get('top_article_no') or '-'} {item.get('top_article_title') or ''}".rstrip(),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def load_questions(path: str | os.PathLike[str]) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Golden question file must contain a JSON list.")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate golden retrieval metrics without LLM calls.")
    parser.add_argument("--golden", "--questions", dest="golden", default=str(DEFAULT_GOLDEN), help="Golden questions JSON path")
    parser.add_argument("--out", default=str(DEFAULT_JSON_OUT), help="JSON report path")
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT), help="Markdown summary path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    questions = load_questions(args.golden)
    report = evaluate_golden(questions)
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(build_markdown_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
