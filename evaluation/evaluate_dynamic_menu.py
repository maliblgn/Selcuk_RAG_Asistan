"""Evaluate dynamic dining menu intent and safe fallback behavior."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynamic_menu_reader import (  # noqa: E402
    fetch_dining_menu,
    format_dining_menu_response,
    is_dining_menu_query,
)


def load_questions(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Dynamic menu smoke questions must be a JSON list.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _mock_unavailable_menu() -> dict:
    return {
        "mode": "dynamic_dining_menu",
        "status": "unavailable",
        "source_url": "https://yemek.selcuk.edu.tr/",
        "source_title": "Selcuk Universitesi Yemekhane Menusu",
        "fetched_at": _now(),
        "menu_period": "",
        "items": [],
        "message": "CI-safe dry-run: live fetch yapilmadi.",
    }


def evaluate_question(item: dict, live_fetch: bool = False) -> dict:
    query = item["query"]
    mode_detected = "dynamic_dining_menu" if is_dining_menu_query(query) else "other"
    expected_mode = item.get("expected_mode")
    expected_not_mode = item.get("expected_not_mode")
    mode_ok = True
    if expected_mode:
        mode_ok = mode_detected == expected_mode
    if expected_not_mode:
        mode_ok = mode_detected != expected_not_mode

    unexpected_exception = False
    menu_status = "not_evaluated"
    fallback_safe = False
    response_preview = ""
    if mode_detected == "dynamic_dining_menu":
        try:
            menu_data = fetch_dining_menu(use_cache=False) if live_fetch else _mock_unavailable_menu()
            menu_status = menu_data.get("status") or "unknown"
            response = format_dining_menu_response(menu_data, query)
            response_preview = response[:240]
            fallback_safe = "uydurulmadi" in response.lower() if menu_status != "ok" else True
        except Exception as exc:  # pragma: no cover - defensive safety net
            unexpected_exception = True
            response_preview = str(exc)[:240]

    passed = mode_ok and not unexpected_exception
    if mode_detected == "dynamic_dining_menu" and menu_status != "ok":
        passed = passed and fallback_safe

    return {
        "id": item.get("id"),
        "query": query,
        "expected_mode": expected_mode,
        "expected_not_mode": expected_not_mode,
        "mode_detected": mode_detected,
        "mode_ok": mode_ok,
        "live_fetch": live_fetch,
        "menu_status": menu_status,
        "fallback_safe": fallback_safe,
        "unexpected_exception": unexpected_exception,
        "response_preview": response_preview,
        "passed": passed,
    }


def build_report(questions: list[dict], live_fetch: bool = False) -> dict:
    results = [evaluate_question(item, live_fetch=live_fetch) for item in questions]
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    failed = total - passed
    mode_checks = [item["mode_ok"] for item in results]
    fallback_safe_count = sum(1 for item in results if item["fallback_safe"])
    unexpected_exception_count = sum(1 for item in results if item["unexpected_exception"])
    return {
        "generated_at": _now(),
        "total_questions": total,
        "passed": passed,
        "failed": failed,
        "mode_match_rate": (sum(mode_checks) / total) if total else 0,
        "fallback_safe_count": fallback_safe_count,
        "unexpected_exception_count": unexpected_exception_count,
        "live_fetch": live_fetch,
        "results": results,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Dynamic Dining Menu Evaluation",
        "",
        f"- total_questions: {report['total_questions']}",
        f"- passed: {report['passed']}",
        f"- failed: {report['failed']}",
        f"- mode_match_rate: {report['mode_match_rate']:.3f}",
        f"- fallback_safe_count: {report['fallback_safe_count']}",
        f"- unexpected_exception_count: {report['unexpected_exception_count']}",
        f"- live_fetch: {report['live_fetch']}",
        "",
        "## Results",
    ]
    for item in report["results"]:
        lines.append(
            f"- {item['id']}: mode={item['mode_detected']}, status={item['menu_status']}, passed={item['passed']}"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="evaluation/dynamic_menu_smoke_questions.json")
    parser.add_argument("--out", default="dynamic_menu_report.local.json")
    parser.add_argument("--markdown-out")
    parser.add_argument("--live-fetch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_questions(args.questions), live_fetch=args.live_fetch)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({k: report[k] for k in (
        "total_questions",
        "passed",
        "failed",
        "mode_match_rate",
        "fallback_safe_count",
        "unexpected_exception_count",
        "live_fetch",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
