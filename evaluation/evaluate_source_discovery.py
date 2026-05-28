"""Evaluate source discovery mode against a small smoke set."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_chroma import Chroma

from chroma_runtime import get_chroma_runtime_dir
from retrieval_normalization import normalize_text
from source_discovery import discover_sources, is_source_discovery_query


def load_questions(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Source discovery questions must be a JSON list.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _term_hits(result: dict, expected_terms: list[str]) -> tuple[list[str], list[str]]:
    haystack = normalize_text(" ".join(
        " ".join(str(source.get(field) or "") for field in ("title", "url", "reason", "matched_terms"))
        for source in result.get("sources", [])
    ))
    found: list[str] = []
    missing: list[str] = []
    for term in expected_terms or []:
        if normalize_text(term) in haystack:
            found.append(term)
        else:
            missing.append(term)
    return found, missing


def evaluate_question(item: dict, db: Chroma, max_sources: int = 8) -> dict:
    query = item["query"]
    mode_detected = is_source_discovery_query(query)
    result = discover_sources(query, db=db, max_sources=max_sources) if mode_detected else {
        "status": "not_source_discovery",
        "total_matches": 0,
        "sources": [],
    }
    expected_terms = item.get("expected_terms") or []
    found_terms, missing_terms = _term_hits(result, expected_terms)
    min_matches = int(item.get("expected_min_matches") or 0)
    mode_ok = mode_detected if item.get("expected_mode") == "source_discovery" else not mode_detected
    min_match_ok = int(result.get("total_matches") or 0) >= min_matches
    expected_terms_ok = not missing_terms
    status = "ok" if mode_ok and min_match_ok and expected_terms_ok else "failed"
    return {
        "id": item.get("id"),
        "query": query,
        "expected_mode": item.get("expected_mode"),
        "mode_detected": "source_discovery" if mode_detected else "normal_rag",
        "mode_ok": mode_ok,
        "status": status,
        "discovery_status": result.get("status"),
        "total_matches": result.get("total_matches", 0),
        "expected_min_matches": min_matches,
        "min_match_ok": min_match_ok,
        "expected_terms_found": found_terms,
        "expected_terms_missing": missing_terms,
        "expected_terms_ok": expected_terms_ok,
        "top_sources": [
            {
                "rank": source.get("rank"),
                "title": source.get("title"),
                "url": source.get("url"),
                "score": source.get("score"),
            }
            for source in result.get("sources", [])[:5]
        ],
    }


def build_report(questions: list[dict], db_path: str = "chroma_db") -> dict:
    db = Chroma(persist_directory=get_chroma_runtime_dir(db_path))
    results = [evaluate_question(item, db) for item in questions]
    total = len(results)
    passed = sum(1 for item in results if item["status"] == "ok")
    mode_ok = sum(1 for item in results if item["mode_ok"])
    min_match_ok = sum(1 for item in results if item["min_match_ok"])
    terms_ok = sum(1 for item in results if item["expected_terms_ok"])
    no_match_count = sum(1 for item in results if item["discovery_status"] == "no_match")
    return {
        "generated_at": _now(),
        "total_questions": total,
        "passed": passed,
        "failed": total - passed,
        "mode_match_rate": mode_ok / total if total else 0.0,
        "min_match_pass_rate": min_match_ok / total if total else 0.0,
        "expected_terms_hit_rate": terms_ok / total if total else 0.0,
        "no_unwanted_answer_generation": all(item["mode_detected"] == "source_discovery" for item in results),
        "no_match_count": no_match_count,
        "results": results,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Source Discovery Evaluation",
        "",
        f"- Total questions: {report['total_questions']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['failed']}",
        f"- Mode match rate: {report['mode_match_rate']:.3f}",
        f"- Min match pass rate: {report['min_match_pass_rate']:.3f}",
        f"- Expected terms hit rate: {report['expected_terms_hit_rate']:.3f}",
        f"- No match count: {report['no_match_count']}",
        "",
        "## Results",
        "",
    ]
    for item in report.get("results", []):
        lines.append(f"- `{item['id']}` - {item['status']} - matches: {item['total_matches']}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate source discovery smoke questions.")
    parser.add_argument("--questions", default="evaluation/source_discovery_smoke_questions.json")
    parser.add_argument("--out", default="source_discovery_report.local.json")
    parser.add_argument("--markdown-out")
    parser.add_argument("--db-path", default="chroma_db")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_questions(args.questions), db_path=args.db_path)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({key: report[key] for key in (
        "total_questions",
        "passed",
        "failed",
        "mode_match_rate",
        "min_match_pass_rate",
        "expected_terms_hit_rate",
        "no_match_count",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
