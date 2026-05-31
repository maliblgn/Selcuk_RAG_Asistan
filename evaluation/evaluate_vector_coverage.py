"""Evaluate generated/manual vector coverage prompts in a CI-safe way."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query_router import route_query


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_questions(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]
    if not isinstance(data, list):
        raise ValueError("Vector coverage questions must be a list or {'questions': list}.")
    return data


def evaluate_questions(questions: list[dict]) -> dict:
    failures = []
    passed = 0
    for item in questions:
        query = str(item.get("query") or "")
        route = route_query(query)
        expected = item.get("expected_mode")
        ok = True
        reasons = []
        if expected in {"rag", "source_discovery", "dynamic_dining_menu"} and route.mode != expected:
            ok = False
            reasons.append(f"expected_mode={expected}, actual_mode={route.mode}")
        if expected == "rag_or_source_discovery" and route.mode not in {"rag", "source_discovery"}:
            ok = False
            reasons.append(f"expected rag/source_discovery, actual_mode={route.mode}")
        if ok:
            passed += 1
        else:
            failures.append({
                "id": item.get("id"),
                "query": query,
                "actual_mode": route.mode,
                "failure_reasons": reasons,
            })
    return {
        "generated_at": _now(),
        "total_questions": len(questions),
        "passed": passed,
        "failed": len(failures),
        "mode_pass_rate": passed / len(questions) if questions else 1.0,
        "critical_failures": failures,
        "status": "failed" if failures else "passed",
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Vector Coverage Evaluation",
        "",
        f"- Status: {report['status']}",
        f"- Total questions: {report['total_questions']}",
        f"- Passed: {report['passed']}",
        f"- Failed: {report['failed']}",
        f"- Mode pass rate: {report['mode_pass_rate']:.3f}",
    ]
    if report["critical_failures"]:
        lines.extend(["", "## Failures"])
        for failure in report["critical_failures"]:
            lines.append(f"- `{failure['id']}`: {failure['query']} ({'; '.join(failure['failure_reasons'])})")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate vector coverage question routing.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_questions(load_questions(args.questions))
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
