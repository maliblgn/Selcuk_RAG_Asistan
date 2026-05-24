"""Validate Technology Faculty source manifests without ingestion."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_FIELDS = {
    "id",
    "title",
    "url",
    "source_owner",
    "category",
    "source_type",
    "priority",
    "freshness",
    "expected_topics",
    "ingestion_recommendation",
    "notes",
}
VALID_PRIORITIES = {"high", "medium", "low"}
STATIC_FRESHNESS_VALUES = {"slow_changing", "medium", "low"}


def load_sources(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Technology Faculty source manifest must be a JSON list.")
    return data


def _normalized_text(value: object) -> str:
    return str(value or "").casefold()


def _has_topic(source: dict, *needles: str) -> bool:
    haystack = " ".join([
        _normalized_text(source.get("id")),
        _normalized_text(source.get("title")),
        _normalized_text(source.get("category")),
        _normalized_text(source.get("source_type")),
        _normalized_text(source.get("ingestion_recommendation")),
        " ".join(_normalized_text(topic) for topic in source.get("expected_topics") or []),
    ])
    return any(needle in haystack for needle in needles)


def _is_pdf_candidate(source: dict) -> bool:
    source_type = _normalized_text(source.get("source_type"))
    path = urlparse(str(source.get("url") or "")).path.casefold()
    return source_type == "pdf" or path.endswith(".pdf")


def _is_web_page_candidate(source: dict) -> bool:
    source_type = _normalized_text(source.get("source_type"))
    return "web_page" in source_type or source_type == "web"


def validate_sources(sources: list[dict]) -> dict:
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    category_counts = Counter()
    source_type_counts = Counter()
    recommendation_counts = Counter()
    items: list[dict] = []
    missing_required_fields_count = 0
    invalid_priority_count = 0
    dynamic_static_mismatch_count = 0
    expected_topics: set[str] = set()

    for source in sources:
        source_id = str(source.get("id") or "")
        missing = sorted(field for field in REQUIRED_FIELDS if not source.get(field))
        topics = source.get("expected_topics") or []
        if not isinstance(topics, list) or not topics:
            if "expected_topics" not in missing:
                missing.append("expected_topics")
        else:
            expected_topics.update(str(topic).casefold() for topic in topics if topic)

        if missing:
            missing_required_fields_count += 1
        if source_id in seen_ids:
            duplicate_ids.add(source_id)
        seen_ids.add(source_id)

        priority = source.get("priority")
        if priority not in VALID_PRIORITIES:
            invalid_priority_count += 1

        freshness = source.get("freshness")
        recommendation = source.get("ingestion_recommendation") or "unknown"
        is_dynamic_mismatch = (
            "dynamic" in _normalized_text(source.get("category"))
            or "dynamic" in _normalized_text(source.get("source_type"))
            or "dynamic" in _normalized_text(recommendation)
            or freshness not in STATIC_FRESHNESS_VALUES
        )
        if is_dynamic_mismatch:
            dynamic_static_mismatch_count += 1

        category = source.get("category") or "unknown"
        source_type = source.get("source_type") or "unknown"
        category_counts[category] += 1
        source_type_counts[source_type] += 1
        recommendation_counts[recommendation] += 1

        items.append({
            "id": source_id,
            "title": source.get("title"),
            "url": source.get("url"),
            "category": category,
            "source_type": source_type,
            "priority": priority,
            "freshness": freshness,
            "expected_topics": topics if isinstance(topics, list) else [],
            "ingestion_recommendation": recommendation,
            "missing_fields": missing,
            "is_pdf_candidate": _is_pdf_candidate(source),
            "is_web_page_candidate": _is_web_page_candidate(source),
            "dynamic_static_mismatch": is_dynamic_mismatch,
            "status": "needs_fix" if missing or priority not in VALID_PRIORITIES or is_dynamic_mismatch else "ok",
        })

    coverage = {
        "has_staj_source": any(_has_topic(source, "staj") for source in sources),
        "has_ime_source": any(_has_topic(source, "ime", "isletmede mesleki egitim") for source in sources),
        "has_regulation_index": any(_has_topic(source, "yonerge", "regulation") for source in sources),
        "has_faq_source": any(_has_topic(source, "sss", "sikca sorulan", "faq") for source in sources),
        "has_forms_or_workflow_source": any(_has_topic(source, "form", "dilekce", "is akis", "workflow") for source in sources),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_sources": len(sources),
        "high_priority_count": sum(1 for item in items if item["priority"] == "high"),
        "pdf_candidate_count": sum(1 for item in items if item["is_pdf_candidate"]),
        "web_page_candidate_count": sum(1 for item in items if item["is_web_page_candidate"]),
        "expected_topic_count": len(expected_topics),
        "missing_required_fields_count": missing_required_fields_count,
        "invalid_priority_count": invalid_priority_count,
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_ids": sorted(duplicate_ids),
        "dynamic_static_mismatch_count": dynamic_static_mismatch_count,
        "coverage": coverage,
        "category_counts": dict(category_counts),
        "source_type_counts": dict(source_type_counts),
        "ingestion_recommendation_counts": dict(recommendation_counts),
        "high_priority_ids": [item["id"] for item in items if item["priority"] == "high"],
        "items": items,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Technology Faculty Sources Audit",
        "",
        f"- Total sources: {report['total_sources']}",
        f"- High priority: {report['high_priority_count']}",
        f"- PDF candidates: {report['pdf_candidate_count']}",
        f"- Web page candidates: {report['web_page_candidate_count']}",
        f"- Unique expected topics: {report['expected_topic_count']}",
        f"- Missing required fields: {report['missing_required_fields_count']}",
        f"- Dynamic/static mismatch: {report['dynamic_static_mismatch_count']}",
        "",
        "## Coverage",
        "",
    ]
    for key, value in report.get("coverage", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## High Priority Sources", ""])
    for item in report.get("items", []):
        if item.get("priority") != "high":
            continue
        lines.append(f"- `{item['id']}` - {item['title']} ({item['source_type']})")
    lines.append("")
    lines.append("Bu audit yalnizca Teknoloji Fakultesi manifestini dogrular; ingestion calistirmaz.")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Technology Faculty source manifest audit.")
    parser.add_argument("--sources", default="evaluation/technology_faculty_sources.json")
    parser.add_argument("--out", default="technology_faculty_sources_audit.local.json")
    parser.add_argument("--markdown-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = load_sources(args.sources)
    report = validate_sources(sources)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({key: report[key] for key in (
        "total_sources",
        "high_priority_count",
        "pdf_candidate_count",
        "web_page_candidate_count",
        "expected_topic_count",
        "missing_required_fields_count",
        "coverage",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
