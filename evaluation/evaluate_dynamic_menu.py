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
    get_dynamic_menu_health,
    is_dining_menu_query,
    select_menu_for_query_details,
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
        "diagnostics": {
            "parsed_item_count": 0,
            "parse_strategy": "none",
        },
    }


def evaluate_question(item: dict, live_fetch: bool = False) -> dict:
    query = item["query"]
    mode_detected = "dynamic_dining_menu" if is_dining_menu_query(query) else "other"
    expected_mode = item.get("expected_mode")
    expected_not_mode = item.get("expected_not_mode")
    expected_behavior = item.get("expected_behavior")
    mode_ok = True
    if expected_mode:
        mode_ok = mode_detected == expected_mode
    if expected_not_mode:
        mode_ok = mode_detected != expected_not_mode

    unexpected_exception = False
    menu_status = "not_evaluated"
    parsed_item_count = 0
    parse_strategy = "none"
    fallback_safe = False
    actual_behavior = "not_evaluated"
    behavior_ok = True
    response_preview = ""
    if mode_detected == "dynamic_dining_menu":
        try:
            menu_data = fetch_dining_menu(use_cache=False) if live_fetch else _mock_unavailable_menu()
            menu_status = menu_data.get("status") or "unknown"
            diagnostics = menu_data.get("diagnostics") or {}
            parsed_item_count = int(diagnostics.get("parsed_item_count") or len(menu_data.get("items") or []))
            parse_strategy = diagnostics.get("parse_strategy") or menu_data.get("parser") or "none"
            response = format_dining_menu_response(menu_data, query)
            response_preview = response[:240]
            lowered_response = response.lower()
            fallback_safe = (
                "uydurulmadi" in lowered_response or "uydurulmadı" in lowered_response
            ) if menu_status != "ok" else True
            if menu_status != "ok":
                actual_behavior = "safe_fallback"
            elif live_fetch:
                selection = select_menu_for_query_details(menu_data, query)
                if selection.get("status") == "no_menu_for_date":
                    actual_behavior = "safe_fallback"
                elif selection.get("selection") == "week":
                    actual_behavior = "range_menu"
                elif selection.get("selection") in {"single_day", "single_weekday"}:
                    selected = selection.get("items") or []
                    actual_behavior = "no_meal" if selected and selected[0].get("has_meal") is False else "single_day_menu"
                elif selection.get("selection") == "month_limited":
                    actual_behavior = "range_menu"
                else:
                    actual_behavior = selection.get("status") or "unknown"
        except Exception as exc:  # pragma: no cover - defensive safety net
            unexpected_exception = True
            response_preview = str(exc)[:240]
    elif expected_behavior == "source_discovery_not_dynamic":
        actual_behavior = "source_discovery_not_dynamic"

    if expected_behavior and live_fetch:
        behavior_ok = actual_behavior == expected_behavior
    elif expected_behavior == "source_discovery_not_dynamic":
        behavior_ok = mode_detected != "dynamic_dining_menu"

    passed = mode_ok and behavior_ok and not unexpected_exception
    if mode_detected == "dynamic_dining_menu" and menu_status != "ok":
        passed = passed and fallback_safe

    return {
        "id": item.get("id"),
        "query": query,
        "expected_mode": expected_mode,
        "expected_not_mode": expected_not_mode,
        "expected_behavior": expected_behavior,
        "mode_detected": mode_detected,
        "mode_ok": mode_ok,
        "actual_behavior": actual_behavior,
        "behavior_ok": behavior_ok,
        "live_fetch": live_fetch,
        "menu_status": menu_status,
        "parsed_item_count": parsed_item_count,
        "parse_strategy": parse_strategy,
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
    dynamic_results = [item for item in results if item["mode_detected"] == "dynamic_dining_menu"]
    live_statuses = [item["menu_status"] for item in dynamic_results]
    parsed_item_count = sum(item.get("parsed_item_count", 0) for item in dynamic_results)
    parse_status = "not_live"
    if live_fetch:
        if unexpected_exception_count:
            parse_status = "exception"
        elif any(status == "ok" for status in live_statuses):
            parse_status = "ok"
        elif live_statuses:
            parse_status = live_statuses[0]
    return {
        "generated_at": _now(),
        "dynamic_menu_health": get_dynamic_menu_health(),
        "total_questions": total,
        "passed": passed,
        "failed": failed,
        "mode_match_rate": (sum(mode_checks) / total) if total else 0,
        "fallback_safe_count": fallback_safe_count,
        "unexpected_exception_count": unexpected_exception_count,
        "live_fetch": live_fetch,
        "live_fetch_status": live_statuses[0] if live_fetch and live_statuses else "not_run",
        "parsed_item_count": parsed_item_count,
        "parse_status": parse_status,
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
        f"- live_fetch_status: {report['live_fetch_status']}",
        f"- parsed_item_count: {report['parsed_item_count']}",
        f"- parse_status: {report['parse_status']}",
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
        "live_fetch_status",
        "parsed_item_count",
        "parse_status",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
