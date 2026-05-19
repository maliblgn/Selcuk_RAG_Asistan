"""Validate web source expansion candidate manifests without ingestion."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_FIELDS = {
    "id",
    "title",
    "url",
    "category",
    "priority",
    "freshness",
    "ingestion_recommendation",
    "notes",
}
VALID_PRIORITIES = {"high", "medium", "low"}


def load_candidates(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Candidate manifest must be a JSON list.")
    return data


def validate_candidates(candidates: list[dict]) -> dict:
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    items: list[dict] = []
    missing_required_fields_count = 0
    invalid_priority_count = 0
    category_counts = Counter()
    action_counts = Counter()

    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        missing = sorted(field for field in REQUIRED_FIELDS if not candidate.get(field))
        if missing:
            missing_required_fields_count += 1
        if candidate_id in seen_ids:
            duplicate_ids.add(candidate_id)
        seen_ids.add(candidate_id)

        priority = candidate.get("priority")
        if priority not in VALID_PRIORITIES:
            invalid_priority_count += 1
        category = candidate.get("category") or "unknown"
        recommendation = candidate.get("ingestion_recommendation") or "unknown"
        category_counts[category] += 1
        action_counts[recommendation] += 1

        is_dynamic = "dynamic" in category or "dynamic" in recommendation
        items.append({
            "id": candidate_id,
            "title": candidate.get("title"),
            "url": candidate.get("url"),
            "category": category,
            "priority": priority,
            "freshness": candidate.get("freshness"),
            "ingestion_recommendation": recommendation,
            "missing_fields": missing,
            "is_dynamic_source": is_dynamic,
            "status": "needs_fix" if missing or priority not in VALID_PRIORITIES else "ok",
        })

    dynamic_source_count = sum(1 for item in items if item["is_dynamic_source"])
    static_ingestion_candidate_count = sum(
        1 for item in items
        if (
            item["ingestion_recommendation"].startswith("static_")
            or item["ingestion_recommendation"].startswith("audit_then_ingest")
        )
    )
    announcement_candidate_count = category_counts.get("announcements", 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_candidates": len(candidates),
        "high_priority_count": sum(1 for item in items if item["priority"] == "high"),
        "dynamic_source_count": dynamic_source_count,
        "static_ingestion_candidate_count": static_ingestion_candidate_count,
        "announcement_candidate_count": announcement_candidate_count,
        "missing_required_fields_count": missing_required_fields_count,
        "invalid_priority_count": invalid_priority_count,
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_ids": sorted(duplicate_ids),
        "category_counts": dict(category_counts),
        "ingestion_recommendation_counts": dict(action_counts),
        "high_priority_ids": [item["id"] for item in items if item["priority"] == "high"],
        "items": items,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Web Source Candidates Audit",
        "",
        f"- Total candidates: {report['total_candidates']}",
        f"- High priority: {report['high_priority_count']}",
        f"- Dynamic sources: {report['dynamic_source_count']}",
        f"- Static ingestion candidates: {report['static_ingestion_candidate_count']}",
        f"- Announcement candidates: {report['announcement_candidate_count']}",
        f"- Missing required fields: {report['missing_required_fields_count']}",
        "",
        "## High Priority Candidates",
        "",
    ]
    for item in report.get("items", []):
        if item.get("priority") != "high":
            continue
        lines.append(f"- `{item['id']}` - {item['title']} ({item['ingestion_recommendation']})")
    lines.append("")
    lines.append("Bu audit yalnizca manifest dogrular; ingestion calistirmaz.")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Web source expansion candidate manifest audit.")
    parser.add_argument("--candidates", default="evaluation/web_source_candidates.json")
    parser.add_argument("--out", default="web_source_candidates_audit.local.json")
    parser.add_argument("--markdown-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = load_candidates(args.candidates)
    report = validate_candidates(candidates)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({key: report[key] for key in (
        "total_candidates",
        "high_priority_count",
        "dynamic_source_count",
        "static_ingestion_candidate_count",
        "announcement_candidate_count",
        "missing_required_fields_count",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
