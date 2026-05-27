"""Inspect the dynamic dining menu source without storing raw HTML."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynamic_menu_reader import (  # noqa: E402
    BROWSER_USER_AGENT,
    DINING_MENU_SOURCE_URL,
    fetch_dining_menu,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_debug_report(source_url: str = DINING_MENU_SOURCE_URL, timeout_sec: int = 12) -> dict:
    """Return source health and parser diagnostics without persisting raw content."""

    report = {
        "generated_at": _now(),
        "source_url": source_url,
        "http_status": None,
        "final_url": source_url,
        "content_type": "",
        "response_length": 0,
        "title": "",
        "table_count": 0,
        "candidate_line_count": 0,
        "fetch_error": "",
        "menu_status": "",
        "parsed_item_count": 0,
        "parse_strategy": "none",
    }

    try:
        response = requests.get(
            source_url,
            timeout=timeout_sec,
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        report["http_status"] = response.status_code
        report["final_url"] = response.url
        report["content_type"] = response.headers.get("content-type", "")
        report["response_length"] = len(response.text or "")
        response.raise_for_status()
    except Exception as exc:
        report["fetch_error"] = exc.__class__.__name__
    else:
        soup = BeautifulSoup(response.text or "", "html.parser")
        report["title"] = " ".join(soup.title.get_text(" ").split()) if soup.title else ""
        report["table_count"] = len(soup.find_all("table"))
        text_lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
        report["candidate_line_count"] = sum(1 for line in text_lines if "yemek" in line.lower() or "men" in line.lower())

    menu_data = fetch_dining_menu(source_url=source_url, timeout_sec=timeout_sec, use_cache=False)
    diagnostics = menu_data.get("diagnostics") or {}
    report["menu_status"] = menu_data.get("status") or ""
    report["parsed_item_count"] = diagnostics.get("parsed_item_count", len(menu_data.get("items") or []))
    report["parse_strategy"] = diagnostics.get("parse_strategy") or menu_data.get("parser") or "none"
    report["parser_diagnostics"] = diagnostics
    return report


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Dynamic Dining Menu Source Debug",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- source_url: {report.get('source_url')}",
        f"- final_url: {report.get('final_url')}",
        f"- http_status: {report.get('http_status')}",
        f"- content_type: {report.get('content_type')}",
        f"- response_length: {report.get('response_length')}",
        f"- title: {report.get('title')}",
        f"- table_count: {report.get('table_count')}",
        f"- candidate_line_count: {report.get('candidate_line_count')}",
        f"- menu_status: {report.get('menu_status')}",
        f"- parsed_item_count: {report.get('parsed_item_count')}",
        f"- parse_strategy: {report.get('parse_strategy')}",
        "",
        "Raw HTML is intentionally not written by this debug helper.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", default=DINING_MENU_SOURCE_URL)
    parser.add_argument("--out", default="dynamic_menu_debug.local.json")
    parser.add_argument("--markdown-out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_debug_report(args.source_url)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({
        "http_status": report.get("http_status"),
        "menu_status": report.get("menu_status"),
        "parsed_item_count": report.get("parsed_item_count"),
        "parse_strategy": report.get("parse_strategy"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
