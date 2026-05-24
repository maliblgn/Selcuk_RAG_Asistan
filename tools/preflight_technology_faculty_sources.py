"""Preflight Technology Faculty static source candidates without ingestion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.exceptions import SSLError
from urllib3.exceptions import InsecureRequestWarning


VALID_STATIC_RECOMMENDATIONS = {
    "static_web_or_pdf_ingestion_candidate",
    "static_web_ingestion_candidate",
    "static_pdf_ingestion_candidate",
}
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def load_sources(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Technology Faculty source manifest must be a JSON list.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _robots_status(url: str, user_agent: str) -> dict:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        response = _request_with_ssl_fallback(robots_url, timeout_sec=10, user_agent=user_agent)
        rp.parse(response.text.splitlines())
        return {
            "robots_url": robots_url,
            "robots_allowed": bool(rp.can_fetch(user_agent, url)),
            "robots_error": None,
        }
    except Exception as exc:
        return {
            "robots_url": robots_url,
            "robots_allowed": None,
            "robots_error": str(exc),
        }


def _extract_html_title(text: str) -> str:
    soup = BeautifulSoup(text or "", "lxml")
    heading = soup.find("h1")
    if heading:
        return heading.get_text(separator=" ", strip=True)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _is_static_candidate(source: dict) -> bool:
    recommendation = source.get("ingestion_recommendation")
    freshness = source.get("freshness")
    return recommendation in VALID_STATIC_RECOMMENDATIONS and freshness != "high"


def _request_with_ssl_fallback(url: str, timeout_sec: int, user_agent: str) -> requests.Response:
    try:
        return requests.get(
            url,
            timeout=timeout_sec,
            headers={"User-Agent": user_agent},
            allow_redirects=True,
        )
    except SSLError:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        return requests.get(
            url,
            timeout=timeout_sec,
            headers={"User-Agent": user_agent},
            allow_redirects=True,
            verify=False,
        )


def check_source(source: dict, timeout_sec: int = 20, user_agent: str = BROWSER_USER_AGENT) -> dict:
    url = str(source.get("url") or "").strip()
    item = {
        "id": source.get("id"),
        "title": source.get("title"),
        "url": url,
        "priority": source.get("priority"),
        "source_type": source.get("source_type"),
        "ingestion_recommendation": source.get("ingestion_recommendation"),
        "is_static_candidate": _is_static_candidate(source),
        "http_status": None,
        "final_url": None,
        "content_type": None,
        "content_length": 0,
        "is_pdf": False,
        "is_html": False,
        "title_detected": "",
        "robots_allowed": None,
        "robots_error": None,
        "ok": False,
        "errors": [],
    }

    if not url:
        item["errors"].append("missing_url")
        return item
    if not item["is_static_candidate"]:
        item["errors"].append("not_static_candidate")
        return item

    robots = _robots_status(url, user_agent)
    item.update({
        "robots_allowed": robots["robots_allowed"],
        "robots_error": robots["robots_error"],
        "robots_url": robots["robots_url"],
    })
    if robots["robots_allowed"] is False:
        item["errors"].append("robots_disallow")

    try:
        response = _request_with_ssl_fallback(url, timeout_sec=timeout_sec, user_agent=user_agent)
        item["http_status"] = response.status_code
        item["final_url"] = response.url
        item["content_type"] = response.headers.get("content-type", "")
        item["content_length"] = len(response.content or b"")
        item["is_pdf"] = "pdf" in item["content_type"].lower() or urlparse(response.url).path.lower().endswith(".pdf")
        item["is_html"] = "html" in item["content_type"].lower()

        if response.status_code >= 400:
            item["errors"].append(f"http_{response.status_code}")
        if item["content_length"] <= 0:
            item["errors"].append("empty_content")
        if item["is_html"]:
            item["title_detected"] = _extract_html_title(response.text)
            if not item["title_detected"]:
                item["errors"].append("missing_html_title")
        if not item["is_html"] and not item["is_pdf"]:
            item["errors"].append("unsupported_content_type")
    except requests.RequestException as exc:
        item["errors"].append(f"request_error:{exc.__class__.__name__}")

    item["ok"] = not item["errors"]
    return item


def build_report(sources: list[dict], timeout_sec: int = 20) -> dict:
    items = [check_source(source, timeout_sec=timeout_sec) for source in sources]
    high_priority = [item for item in items if item.get("priority") == "high"]
    successful = [item for item in items if item.get("ok")]
    failed = [item for item in items if not item.get("ok")]
    return {
        "generated_at": _now(),
        "total_sources": len(items),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "high_priority_count": len(high_priority),
        "high_priority_successful_count": sum(1 for item in high_priority if item.get("ok")),
        "pdf_count": sum(1 for item in items if item.get("is_pdf")),
        "html_count": sum(1 for item in items if item.get("is_html")),
        "all_high_priority_accessible": all(item.get("ok") for item in high_priority),
        "items": items,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Technology Faculty Preflight",
        "",
        f"- Total sources: {report['total_sources']}",
        f"- Successful: {report['successful_count']}",
        f"- Failed: {report['failed_count']}",
        f"- High priority successful: {report['high_priority_successful_count']} / {report['high_priority_count']}",
        f"- PDF: {report['pdf_count']}",
        f"- HTML: {report['html_count']}",
        "",
        "## Items",
        "",
    ]
    for item in report.get("items", []):
        status = "ok" if item.get("ok") else "needs_fix"
        errors = ", ".join(item.get("errors") or []) or "-"
        lines.append(f"- `{item['id']}` - {status} - HTTP {item.get('http_status')} - {errors}")
    lines.append("")
    lines.append("Bu preflight yalnizca erisim ve temel icerik kontrolu yapar; ingestion calistirmaz.")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight Technology Faculty source candidates.")
    parser.add_argument("--sources", default="evaluation/technology_faculty_sources.json")
    parser.add_argument("--out", default="technology_faculty_preflight.local.json")
    parser.add_argument("--markdown-out")
    parser.add_argument("--timeout-sec", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_sources(args.sources), timeout_sec=args.timeout_sec)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    print(json.dumps({key: report[key] for key in (
        "total_sources",
        "successful_count",
        "failed_count",
        "high_priority_count",
        "high_priority_successful_count",
        "pdf_count",
        "html_count",
        "all_high_priority_accessible",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
