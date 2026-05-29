"""Evaluate answer grounding evidence without calling the live LLM by default.

This evaluator is deliberately separate from ``evaluate_answer_quality.py``.
Its default mode checks route decisions and supporting evidence: source labels,
document labels, article metadata, expected terms, forbidden terms, and fallback
cases. Live answer checks are opt-in with ``--live-llm`` and are skipped when no
provider key is available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")
os.environ.setdefault("MULTI_QUERY_ENABLED", "false")
os.environ.setdefault("FLASHRANK_ENABLED", "false")

from dynamic_menu_reader import get_dynamic_menu_health  # noqa: E402
from evaluation.evaluate_answer_quality import run_live_answer  # noqa: E402
from query_router import (  # noqa: E402
    MODE_DYNAMIC_DINING_MENU,
    MODE_RAG,
    MODE_SOURCE_DISCOVERY,
    route_query,
)
from rag_engine import SelcukRAGEngine, prepare_context_and_sources  # noqa: E402
from retrieval_normalization import normalize_article_no, normalize_text  # noqa: E402
from source_discovery import discover_sources  # noqa: E402


DEFAULT_QUESTIONS = ROOT_DIR / "evaluation" / "answer_grounding_questions.json"
DEFAULT_JSON_OUT = ROOT_DIR / "answer_grounding_report.local.json"
DEFAULT_MARKDOWN_OUT = ROOT_DIR / "answer_grounding_summary.local.md"
TOP_K = 5

VALID_EXPECTED_MODES = {"rag", "source_discovery", "dynamic_dining_menu", "fallback"}
VALID_ANSWER_TYPES = {
    "definition",
    "requirement",
    "procedure",
    "article_lookup",
    "source_lookup",
    "dynamic",
    "unknown",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_questions(path: Path | str) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Answer grounding question file must contain a JSON list.")
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Question at index {index} must be an object.")
        if item.get("expected_mode") not in VALID_EXPECTED_MODES:
            raise ValueError(f"Question {item.get('id', index)} has invalid expected_mode.")
        if item.get("expected_answer_type") not in VALID_ANSWER_TYPES:
            raise ValueError(f"Question {item.get('id', index)} has invalid expected_answer_type.")
    return data


def _contains_term(text: str, term: str) -> bool:
    return normalize_text(term) in normalize_text(text)


def _find_missing_terms(text: str, terms: list[str] | None) -> list[str]:
    return [term for term in (terms or []) if not _contains_term(text, term)]


def _find_present_terms(text: str, terms: list[str] | None) -> list[str]:
    return [term for term in (terms or []) if _contains_term(text, term)]


def _doc_to_dict(doc: Any, rank: int) -> dict[str, Any]:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    article_no = metadata.get("article_no")
    article_no_norm = normalize_article_no(str(article_no or "")) if article_no not in (None, "") else ""
    return {
        "rank": rank,
        "source": metadata.get("source") or "",
        "title": metadata.get("source_title") or metadata.get("title") or metadata.get("file_name") or "",
        "article_no": article_no_norm or article_no or "",
        "article_title": metadata.get("article_title") or "",
        "source_family": metadata.get("source_family") or "",
        "category": metadata.get("category") or "",
        "content_preview": " ".join(str(getattr(doc, "page_content", "") or "").split())[:500],
    }


def _evidence_text_from_docs(docs: list[Any], sources: list[dict[str, Any]] | None = None) -> str:
    parts: list[str] = []
    for doc in docs or []:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        parts.extend(str(metadata.get(key) or "") for key in (
            "source",
            "source_title",
            "title",
            "file_name",
            "article_no",
            "article_title",
            "source_family",
            "category",
        ))
        parts.append(str(getattr(doc, "page_content", "") or ""))
    for source in sources or []:
        parts.extend(str(source.get(key) or "") for key in ("label", "source", "article_label", "url"))
    return "\n".join(parts)


def _source_discovery_evidence(query: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    result = discover_sources(query)
    sources = result.get("sources") or []
    evidence_text = "\n".join(
        " ".join(
            str(item.get(key) or "")
            for key in ("title", "source_type", "source", "url", "reason", "snippet")
        )
        for item in sources
    )
    return evidence_text, sources, []


def _dynamic_evidence() -> tuple[str, list[dict[str, Any]]]:
    health = get_dynamic_menu_health()
    evidence_text = " ".join(str(value) for value in health.values())
    return evidence_text, [health]


def _expected_article_hit(top_docs: list[dict[str, Any]], expected_article_numbers: list[str] | None) -> bool | None:
    expected = [normalize_article_no(str(value)) or str(value) for value in (expected_article_numbers or []) if str(value or "").strip()]
    if not expected:
        return None
    actual = {normalize_article_no(str(item.get("article_no") or "")) or str(item.get("article_no") or "") for item in top_docs}
    return any(item in actual for item in expected)


def _mode_matches(expected_mode: str, route_mode: str, actual_mode: str) -> bool:
    if expected_mode == "fallback":
        return actual_mode == "fallback"
    return expected_mode == route_mode == actual_mode


def _recommendation(failure_reasons: list[str]) -> str:
    if not failure_reasons:
        return ""
    if "mode_mismatch" in failure_reasons:
        return "Query router intent ve soru seti expectation uyumu kontrol edilmeli."
    if "fallback_mismatch" in failure_reasons:
        return "Fallback beklenen soru icin filtrelenmis evidence uretilip uretilmedigi incelenmeli."
    if any(reason.endswith("_missing") for reason in failure_reasons):
        return "Retrieval evidence, metadata alias veya soru beklentisi birlikte triage edilmeli."
    if "forbidden_terms_found" in failure_reasons:
        return "Evidence icinde yasakli/alakasiz terim baskinligi incelenmeli."
    return "Grounding failure detaylari manuel incelenmeli."


def evaluate_question(
    item: dict[str, Any],
    *,
    engine: SelcukRAGEngine | None = None,
    live_engine: SelcukRAGEngine | None = None,
    live_llm: bool = False,
) -> dict[str, Any]:
    query = item.get("query") or item.get("question") or ""
    expected_mode = item.get("expected_mode") or MODE_RAG
    route = route_query(query)
    actual_mode = route.mode
    failure_reasons: list[str] = []
    top_sources: list[dict[str, Any]] = []
    top_articles: list[dict[str, Any]] = []
    evidence_text = ""
    fallback_predicted = False
    live_answer = ""
    live_answer_pass: bool | None = None
    live_skip_reason = ""

    if route.mode == MODE_SOURCE_DISCOVERY:
        evidence_text, discovered_sources, source_failures = _source_discovery_evidence(query)
        failure_reasons.extend(source_failures)
        top_sources = [
            {
                "rank": item.get("rank"),
                "title": item.get("title"),
                "source": item.get("source") or item.get("url"),
                "source_type": item.get("source_type"),
                "score": item.get("score"),
            }
            for item in discovered_sources[:TOP_K]
        ]
    elif route.mode == MODE_DYNAMIC_DINING_MENU:
        evidence_text, health_items = _dynamic_evidence()
        top_sources = [
            {
                "rank": 1,
                "title": health_items[0].get("source_title"),
                "source": health_items[0].get("source_url"),
                "source_type": "dynamic_menu",
                "score": None,
            }
        ]
    else:
        if engine is None:
            engine = SelcukRAGEngine(enable_llm=False)
        retrieved_docs = engine.retrieve(query)
        prepared = prepare_context_and_sources(query, retrieved_docs)
        docs = prepared.get("docs") or []
        sources = prepared.get("sources") or []
        fallback_predicted = len(docs) == 0
        actual_mode = "fallback" if fallback_predicted and item.get("requires_fallback") else MODE_RAG
        evidence_text = _evidence_text_from_docs(docs, sources)
        top_articles = [_doc_to_dict(doc, rank) for rank, doc in enumerate(docs[:TOP_K], start=1)]
        top_sources = [
            {
                "rank": rank,
                "title": source.get("label"),
                "source": source.get("source") or source.get("url"),
                "article": source.get("article_label"),
                "source_type": "rag_source",
                "score": None,
            }
            for rank, source in enumerate(sources[:TOP_K], start=1)
        ]

        if live_llm:
            if not os.getenv("GROQ_API_KEY"):
                live_skip_reason = "missing_groq_api_key"
            elif live_engine is None:
                live_skip_reason = "live_llm_engine_unavailable"
            else:  # pragma: no cover - external provider dependent
                try:
                    _raw_answer, live_answer = run_live_answer(live_engine, query, prepared)
                except Exception as exc:
                    live_skip_reason = f"live_llm_error:{type(exc).__name__}"

    if item.get("requires_fallback"):
        if not fallback_predicted and route.mode == MODE_RAG:
            failure_reasons.append("fallback_mismatch")
    elif expected_mode == "fallback":
        if actual_mode != "fallback":
            failure_reasons.append("fallback_mismatch")

    mode_ok = _mode_matches(expected_mode, route.mode, actual_mode)
    if not mode_ok:
        failure_reasons.append("mode_mismatch")

    missing_source_keywords = _find_missing_terms(evidence_text, item.get("expected_source_keywords"))
    missing_document_keywords = _find_missing_terms(evidence_text, item.get("expected_document_keywords"))
    missing_expected_terms = _find_missing_terms(evidence_text, item.get("expected_terms"))
    forbidden_terms_found = _find_present_terms(evidence_text, item.get("forbidden_terms"))
    article_hit = _expected_article_hit(top_articles, item.get("expected_article_numbers"))

    if missing_source_keywords:
        failure_reasons.append("source_keywords_missing")
    if missing_document_keywords:
        failure_reasons.append("document_keywords_missing")
    if missing_expected_terms:
        failure_reasons.append("expected_terms_missing")
    if article_hit is False:
        failure_reasons.append("article_number_missing")
    if forbidden_terms_found:
        failure_reasons.append("forbidden_terms_found")

    if live_llm and live_answer:
        live_missing = _find_missing_terms(live_answer + "\n" + evidence_text, item.get("expected_terms"))
        live_forbidden = _find_present_terms(live_answer, item.get("forbidden_terms"))
        live_answer_pass = not live_missing and not live_forbidden
        if not live_answer_pass:
            failure_reasons.append("live_answer_grounding_mismatch")
    elif live_llm:
        live_answer_pass = None

    passed = not failure_reasons
    return {
        "id": item.get("id"),
        "query": query,
        "expected_mode": expected_mode,
        "actual_mode": actual_mode,
        "route_mode": route.mode,
        "route_reason": route.reason,
        "expected_answer_type": item.get("expected_answer_type"),
        "passed": passed,
        "failure_reasons": sorted(set(failure_reasons)),
        "top_sources": top_sources,
        "top_articles": top_articles,
        "missing_terms": {
            "source_keywords": missing_source_keywords,
            "document_keywords": missing_document_keywords,
            "expected_terms": missing_expected_terms,
            "article_numbers": item.get("expected_article_numbers") if article_hit is False else [],
        },
        "forbidden_terms_found": forbidden_terms_found,
        "requires_fallback": bool(item.get("requires_fallback")),
        "fallback_predicted": fallback_predicted,
        "source_keyword_hit": not missing_source_keywords,
        "document_keyword_hit": not missing_document_keywords,
        "article_hit": article_hit,
        "expected_terms_hit": not missing_expected_terms,
        "forbidden_terms_ok": not forbidden_terms_found,
        "live_llm_requested": live_llm,
        "live_answer_checked": bool(live_answer),
        "live_answer_pass": live_answer_pass,
        "live_skip_reason": live_skip_reason,
        "recommendation": _recommendation(failure_reasons),
    }


def _ratio(values: list[bool | None]) -> float | None:
    eligible = [value for value in values if value is not None]
    if not eligible:
        return None
    return sum(1 for value in eligible if value) / len(eligible)


def build_summary(questions: list[dict[str, Any]], results: list[dict[str, Any]], *, live_llm: bool) -> dict[str, Any]:
    critical_statuses = {
        "mode_mismatch",
        "fallback_mismatch",
        "forbidden_terms_found",
        "source_discovery_no_match",
    }
    fallback_results = [result for result in results if result.get("requires_fallback")]
    live_checked = [result for result in results if result.get("live_answer_checked")]
    critical_failures = [
        result for result in results
        if any(reason in critical_statuses for reason in result.get("failure_reasons", []))
    ]
    return {
        "generated_at": _now(),
        "total_questions": len(questions),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
        "skipped": 0,
        "mode_accuracy": _ratio([not ("mode_mismatch" in result["failure_reasons"]) for result in results]) or 0.0,
        "evidence_pass_rate": _ratio([result["passed"] for result in results]) or 0.0,
        "source_keyword_hit_rate": _ratio([result["source_keyword_hit"] for result in results]) or 0.0,
        "document_keyword_hit_rate": _ratio([result["document_keyword_hit"] for result in results]) or 0.0,
        "article_hit_rate": _ratio([result["article_hit"] for result in results]),
        "expected_terms_hit_rate": _ratio([result["expected_terms_hit"] for result in results]) or 0.0,
        "forbidden_terms_violation_count": sum(1 for result in results if result["forbidden_terms_found"]),
        "fallback_pass_rate": _ratio([result["fallback_predicted"] for result in fallback_results]),
        "live_answer_pass_rate": _ratio([result["live_answer_pass"] for result in live_checked]) if live_llm else None,
        "critical_failures": [
            {
                "question_id": result["id"],
                "query": result["query"],
                "failure_reasons": result["failure_reasons"],
                "recommendation": result["recommendation"],
            }
            for result in critical_failures
        ],
        "critical_failure_count": len(critical_failures),
        "failure_reason_counts": dict(sorted(Counter(reason for result in results for reason in result["failure_reasons"]).items())),
        "mode_counts": dict(sorted(Counter(result["actual_mode"] for result in results).items())),
    }


def build_report(questions: list[dict[str, Any]], results: list[dict[str, Any]], *, live_llm: bool) -> dict[str, Any]:
    return {
        "generated_at": _now(),
        "live_llm_requested": live_llm,
        "llm_calls": any(result.get("live_answer_checked") for result in results),
        "summary": build_summary(questions, results, live_llm=live_llm),
        "results": results,
    }


def evaluate_questions(
    questions: list[dict[str, Any]],
    *,
    live_llm: bool = False,
    engine_factory: Callable[[bool], SelcukRAGEngine] | None = None,
) -> dict[str, Any]:
    needs_rag = any(route_query(item.get("query") or item.get("question") or "").mode == MODE_RAG for item in questions)
    factory = engine_factory or (lambda enable_llm: SelcukRAGEngine(enable_llm=enable_llm))
    engine = factory(False) if needs_rag else None
    live_engine = None
    if live_llm and os.getenv("GROQ_API_KEY") and needs_rag:
        live_engine = factory(True)
    results = [
        evaluate_question(item, engine=engine, live_engine=live_engine, live_llm=live_llm)
        for item in questions
    ]
    return build_report(questions, results, live_llm=live_llm)


def build_markdown_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    failed = [result for result in report["results"] if not result["passed"]][:12]
    lines = [
        "# Answer Grounding Evaluation Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Live LLM requested: `{report['live_llm_requested']}`",
        f"- LLM calls made: `{report['llm_calls']}`",
        f"- Total questions: {summary['total_questions']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Mode accuracy: {summary['mode_accuracy']:.3f}",
        f"- Evidence pass rate: {summary['evidence_pass_rate']:.3f}",
        f"- Source keyword hit rate: {summary['source_keyword_hit_rate']:.3f}",
        f"- Document keyword hit rate: {summary['document_keyword_hit_rate']:.3f}",
        f"- Expected terms hit rate: {summary['expected_terms_hit_rate']:.3f}",
        f"- Forbidden term violations: {summary['forbidden_terms_violation_count']}",
        f"- Critical failures: {summary['critical_failure_count']}",
        "",
        "## Failure Reason Counts",
        "",
    ]
    if summary["failure_reason_counts"]:
        lines.extend(f"- `{key}`: {value}" for key, value in summary["failure_reason_counts"].items())
    else:
        lines.append("- Yok")
    lines.extend(["", "## Failed Items", ""])
    if not failed:
        lines.append("- Yok")
    for result in failed:
        lines.extend([
            f"- `{result['id']}`: {', '.join(result['failure_reasons'])}",
            f"  - Query: {result['query']}",
            f"  - Expected/actual mode: {result['expected_mode']} / {result['actual_mode']}",
            f"  - Recommendation: {result['recommendation']}",
        ])
    lines.extend([
        "",
        "## Notes",
        "",
        "- Default mode is CI-safe evidence-only and does not call a live LLM.",
        "- Live mode is opt-in with `--live-llm`; missing provider keys are skipped safely.",
    ])
    return "\n".join(lines).strip() + "\n"


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        print("Live LLM requested but GROQ_API_KEY is not available; live checks will be skipped.", file=sys.stderr)

    report = evaluate_questions(questions, live_llm=args.live_llm)
    write_json(args.out, report)
    args.markdown_out.write_text(build_markdown_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_critical and report["summary"]["critical_failure_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
