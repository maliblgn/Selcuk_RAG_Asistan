import argparse
import json
import os
import sys
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from web_scraper import WebScraper  # noqa: E402


def build_inventory_from_html(html_path, source_page):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    pdf_links = WebScraper.extract_pdf_link_inventory(html, source_page)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "local_html_pdf_inventory",
        "html_path": html_path,
        "source_page": source_page,
        "pdf_count": len(pdf_links),
        "pdf_links": pdf_links,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Local HTML dosyasindan PDF envanteri cikarir.")
    parser.add_argument("--html", required=True, help="Local HTML dosyasi")
    parser.add_argument("--source-page", required=True, help="Liste sayfasinin orijinal URL'i")
    parser.add_argument("--out", required=True, help="JSON cikti dosyasi")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_inventory_from_html(args.html, args.source_page)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"{report['pdf_count']} PDF linki yazildi: {args.out}")


if __name__ == "__main__":
    main()
