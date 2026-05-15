"""Evaluate limited LLM answer quality for RAG responses.

Default mode is CI-safe and does not call an external LLM. It still exercises
retrieval, relevance filtering, and source-panel preparation, then marks answer
quality as ``skipped_live_llm``. Live mode is opt-in with ``--live-llm``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

from rag_engine import (  # noqa: E402
    SelcukRAGEngine,
    build_safe_fallback,
    classify_query_type,
    ensure_inline_citation,
    is_low_quality_answer,
    prepare_context_and_sources,
    strip_model_generated_sources,
)
from retrieval_normalization import normalize_text  # noqa: E402


DEFAULT_QUESTIONS = ROOT_DIR / "evaluation" / "answer_quality_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "answer_quality_report.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "answer_quality_summary.local.md"

QUALITY_STATUSES = {
    "ok",
    "skipped_live_llm",
    "citation_missing",
    "source_block_leak",
    "url_leak",
    "fallback_mismatch",
    "low_quality_answer",
    "expected_terms_miss",
    "live_llm_error",
    "inspect",
}

SOURCE_BLOCK_RE = re.compile(
    r"(?im)^\s*(?:[-*_]{2,}\s*)?(?:#+\s*)?(?:\*\*)?\s*"
    r"kaynak(?:lar)?\s*(?:\*\*)?\s*:?\s*(?:[-*_]{2,})?.*$"
)
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
INLINE_CITATION_RE = re.compile(r"\[\d+\]")


def load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Answer quality question file must contain a JSON list.")
    return data


def detect_source_block_leak(answer: str) -> bool:
    return bool(SOURCE_BLOCK_RE.search(str(answer or "")))


def detect_url_leak(answer: str) -> bool:
    return bool(URL_RE.search(str(answer or "")))


def detect_long_number_sequence(answer: str) -> bool:
    text = str(answer or "")
    if re.search(r"(?:\b\d+\b\s*,\s*){20,}\b\d+\b", text):
        return True
    numbers = [int(value) for value in re.findall(r"\b\d+\b", text)]
    run = 1
    previous = None
    for number in numbers:
        if previous is not None and number == previous + 1:
            run += 1
            if run > 20:
                return True
        else:
            run = 1
        previous = number
    return False


def detect_inline_citation(answer: str) -> bool:
    return bool(INLINE_CITATION_RE.search(str(answer or "")))


def detect_fallback_answer(answer: str) -> bool:
    normalized = normalize_text(answer)
    fallback_terms = (
        "guvenilir sekilde bulunamadi",
        "acik ve guvenilir saat bilgisi bulunamadi",
        "kaynaklarda acik bir bilgi tespit edemedim",
        "dokumanlarda yer almiyor",
        "belgelerde bu konuda kesin bir bilgi bulamadim",
        "mevcut yonetmelik yonerge kaynaklarinda",
    )
    return any(term in normalized for term in fallback_terms)


def _contains_term(text: str, term: str) -> bool:
    return normalize_text(term) in normalize_text(text)


def _answer_preview(answer: str, max_chars: int = 400) -> str:
    text = " ".join(str(answer or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _collect_stream_text(chunks) -> str:
    parts: list[str] = []
    for chunk in chunks:
        parts.append(chunk.content if hasattr(chunk, "content") else str(chunk))
    return "".join(parts)


def run_live_answer(engine: SelcukRAGEngine, question: str, prepared: dict) -> tuple[str, str]:
    docs = prepared["docs"]
    query_type = prepared["query_type"]
    if not docs:
        fallback = build_safe_fallback(question, docs, query_type)
        return fallback, fallback

    raw_answer = _collect_stream_text(engine.stream_answer(question, prepared["context"], ""))
    final_answer = strip_model_generated_sources(raw_answer)
    final_answer = ensure_inline_citation(final_answer, docs)
    if is_low_quality_answer(final_answer):
        final_answer = build_safe_fallback(question, docs, query_type)
    return raw_answer, final_answer


def determine_quality_status(result: dict[str, Any]) -> str:
    if result.get("live_llm_error"):
        return "live_llm_error"
    if not result.get("live_llm_used"):
        return "skipped_live_llm"
    if result.get("source_block_leak"):
        return "source_block_leak"
    if result.get("url_leak"):
        return "url_leak"
    if result.get("low_quality_answer") or result.get("long_number_sequence"):
        return "low_quality_answer"
    if result.get("expected_behavior") == "fallback" and not result.get("fallback_detected"):
        return "fallback_mismatch"
    if result.get("expected_behavior") == "answer" and result.get("retrieved_source_count", 0) > 0:
        if not result.get("citation_present"):
            return "citation_missing"
        if result.get("expected_terms_missing"):
            return "expected_terms_miss"
    if result.get("forbidden_terms_found"):
        return "inspect"
    return "ok"


def evaluate_question(engine: SelcukRAGEngine, item: dict[str, Any], *, live_llm: bool) -> dict[str, Any]:
    question = item["question"]
    retrieved_docs = engine.retrieve(question)
    prepared = prepare_context_and_sources(question, retrieved_docs)
    docs = prepared["docs"]
    sources = prepared["sources"]
    raw_answer = ""
    answer = ""
    live_error = ""

    if live_llm:
        try:
            raw_answer, answer = run_live_answer(engine, question, prepared)
        except Exception as exc:  # pragma: no cover - external provider dependent
            live_error = str(exc)
    else:
        answer = build_safe_fallback(question, docs, prepared["query_type"]) if not docs else ""

    inspection_text = raw_answer or answer
    expected_terms = item.get("expected_terms") or []
    forbidden_terms = item.get("forbidden_terms") or []
    expected_terms_found = [term for term in expected_terms if _contains_term(answer, term)]
    expected_terms_missing = [term for term in expected_terms if term not in expected_terms_found]
    forbidden_terms_found = [term for term in forbidden_terms if _contains_term(answer, term)]

    result = {
        "id": item["id"],
        "question": question,
        "category": item.get("category"),
        "expected_behavior": item.get("expected_behavior"),
        "live_llm_used": bool(live_llm and not live_error),
        "answer_text_preview": _answer_preview(answer),
        "retrieved_source_count": len(docs),
        "source_panel_candidate_count": len(sources),
        "citation_present": detect_inline_citation(answer),
        "source_block_leak": detect_source_block_leak(inspection_text),
        "url_leak": detect_url_leak(inspection_text),
        "low_quality_answer": bool(answer) and is_low_quality_answer(answer),
        "long_number_sequence": detect_long_number_sequence(inspection_text),
        "fallback_expected": item.get("expected_behavior") == "fallback",
        "fallback_detected": detect_fallback_answer(answer),
        "expected_terms_found": expected_terms_found,
        "expected_terms_missing": expected_terms_missing,
        "forbidden_terms_found": forbidden_terms_found,
        "quality_checks": item.get("quality_checks") or [],
        "live_llm_error": live_error,
    }
    result["quality_status"] = determine_quality_status(result)
    return result


def build_summary(questions: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [item for item in results if item["quality_status"] != "skipped_live_llm"]
    answer_expected = [item for item in questions if item.get("expected_behavior") == "answer"]
    fallback_expected = [item for item in questions if item.get("expected_behavior") == "fallback"]
    fallback_results = [item for item in evaluated if item.get("fallback_expected")]
    citation_denominator = [item for item in evaluated if item.get("expected_behavior") == "answer"]
    citation_present = [item for item in citation_denominator if item.get("citation_present")]
    critical_statuses = {
        "citation_missing",
        "source_block_leak",
        "url_leak",
        "fallback_mismatch",
        "low_quality_answer",
        "expected_terms_miss",
        "live_llm_error",
    }
    return {
        "total_questions": len(questions),
        "evaluated_questions": len(evaluated),
        "skipped_questions": len(results) - len(evaluated),
        "answer_expected_count": len(answer_expected),
        "fallback_expected_count": len(fallback_expected),
        "citation_present_rate": (len(citation_present) / len(citation_denominator)) if citation_denominator else 0.0,
        "source_block_leak_count": sum(1 for item in evaluated if item["source_block_leak"]),
        "url_leak_count": sum(1 for item in evaluated if item["url_leak"]),
        "fallback_correct_count": sum(1 for item in fallback_results if item["fallback_detected"]),
        "fallback_mismatch_count": sum(1 for item in fallback_results if not item["fallback_detected"]),
        "low_quality_answer_count": sum(1 for item in evaluated if item["low_quality_answer"]),
        "long_number_sequence_count": sum(1 for item in evaluated if item["long_number_sequence"]),
        "critical_failure_count": sum(1 for item in results if item["quality_status"] in critical_statuses),
        "quality_status_counts": dict(sorted(Counter(item["quality_status"] for item in results).items())),
    }


def build_report(questions: list[dict[str, Any]], results: list[dict[str, Any]], *, live_llm: bool) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": generated_at,
        "live_llm_requested": live_llm,
        "summary": {
            "generated_at": generated_at,
            **build_summary(questions, results),
        },
        "results": results,
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    risky = [
        item for item in report["results"]
        if item["quality_status"] not in {"ok", "skipped_live_llm"}
    ][:10]
    lines = [
        "# Answer Quality Evaluation Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Live LLM requested: `{report['live_llm_requested']}`",
        f"- Total questions: {summary['total_questions']}",
        f"- Evaluated questions: {summary['evaluated_questions']}",
        f"- Skipped questions: {summary['skipped_questions']}",
        f"- Citation present rate: {summary['citation_present_rate']:.3f}",
        f"- Fallback correct: {summary['fallback_correct_count']}",
        f"- Fallback mismatch: {summary['fallback_mismatch_count']}",
        f"- Source block leaks: {summary['source_block_leak_count']}",
        f"- URL leaks: {summary['url_leak_count']}",
        f"- Low-quality answers: {summary['low_quality_answer_count']}",
        f"- Critical failures: {summary['critical_failure_count']}",
        "",
        "## Quality Status Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["quality_status_counts"].items())
    lines.extend(["", "## Critical Items", ""])
    if not risky:
        lines.append("- Yok")
    else:
        lines.extend(f"- `{item['id']}`: {item['quality_status']}" for item in risky)
    lines.extend([
        "",
        "## Notes",
        "",
        "- Dry-run mode is CI-safe and does not call external LLM providers.",
        "- Live mode requires `GROQ_API_KEY` and should be run manually.",
    ])
    return "\n".join(lines).strip() + "\n"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--live-llm", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fail-on-critical", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    questions = load_questions(args.questions)
    if args.limit is not None:
        questions = questions[: max(0, args.limit)]

    if args.live_llm and not os.getenv("GROQ_API_KEY"):
        print("ERROR: --live-llm requires GROQ_API_KEY.", file=sys.stderr)
        return 2

    engine = SelcukRAGEngine(enable_llm=args.live_llm)
    results = [evaluate_question(engine, item, live_llm=args.live_llm) for item in questions]
    report = build_report(questions, results, live_llm=args.live_llm)
    write_json(args.out, report)
    args.markdown_out.write_text(build_markdown_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_critical and report["summary"]["critical_failure_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
