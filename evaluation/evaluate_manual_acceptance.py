"""CI-safe manual acceptance checks for high-risk live demo questions."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynamic_menu_reader import format_dining_menu_response
from query_router import route_query


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_questions(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Manual acceptance questions must be a JSON list.")
    return data


def _clarification_check(query: str) -> bool:
    fixture = {
        "mode": "dynamic_dining_menu",
        "status": "ok",
        "source_title": "Test Menu",
        "fetched_at": "2026-05-01T00:00:00+00:00",
        "items": [
            {"date": "2026-05-01", "display_date": "1 Mayıs 2026", "menu": ["Çorba", "Pilav", "Ayran"]},
            {"date": "2026-05-02", "display_date": "2 Mayıs 2026", "menu": ["Çorba", "Makarna", "Ayran"]},
        ],
    }
    response = format_dining_menu_response(fixture, query).casefold()
    return "tarih" in response or "gün" in response or "gun" in response


def build_report(questions: list[dict]) -> dict:
    failures = []
    mode_matches = 0
    clarification_passed = 0
    for item in questions:
        query = str(item.get("query") or "")
        expected_mode = item.get("expected_mode")
        route = route_query(query)
        reasons = []
        if expected_mode and route.mode != expected_mode:
            reasons.append(f"expected_mode={expected_mode}, actual_mode={route.mode}")
        else:
            mode_matches += 1
        if item.get("expects_clarification"):
            if _clarification_check(query):
                clarification_passed += 1
            else:
                reasons.append("broad dynamic menu query did not ask for a date/day")
        if reasons:
            failures.append({
                "id": item.get("id"),
                "query": query,
                "expected_mode": expected_mode,
                "actual_mode": route.mode,
                "failure_reasons": reasons,
            })
    total = len(questions)
    return {
        "generated_at": _now(),
        "total_questions": total,
        "passed": total - len(failures),
        "failed": len(failures),
        "mode_accuracy": mode_matches / total if total else 1.0,
        "clarification_passed": clarification_passed,
        "critical_failures": failures,
        "status": "failed" if failures else "passed",
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Manual Acceptance Summary",
        "",
        f"- Status: {report['status']}",
        f"- Total questions: {report['total_questions']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['failed']}",
        f"- Mode accuracy: {report['mode_accuracy']:.3f}",
        f"- Clarification checks passed: {report['clarification_passed']}",
    ]
    if report["critical_failures"]:
        lines.extend(["", "## Failures"])
        for failure in report["critical_failures"]:
            lines.append(f"- `{failure['id']}`: {failure['query']} ({'; '.join(failure['failure_reasons'])})")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate manual acceptance questions.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_questions(args.questions))
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown_out)
    print(json.dumps({
        "status": report["status"],
        "total_questions": report["total_questions"],
        "passed": report["passed"],
        "failed": report["failed"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
