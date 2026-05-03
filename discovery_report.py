import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from urllib.parse import unquote

from dotenv import load_dotenv

from web_crawler import CrawlerConfig, SelcukCrawler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(BASE_DIR, "source_manifest.json")


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def active_seeds(manifest):
    authorized_mode = os.getenv("AUTHORIZED_SOURCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    return [
        item for item in manifest.get("crawl_seeds", [])
        if (item.get("active", True) or (authorized_mode and item.get("requires_permission"))) and item.get("url")
    ]


def active_direct_sources(manifest):
    authorized_mode = os.getenv("AUTHORIZED_SOURCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    return [
        item for item in manifest.get("known_direct_sources", [])
        if (item.get("active", True) or (authorized_mode and item.get("requires_permission"))) and item.get("url")
    ]


def normalize_text(value):
    value = unquote(value or "")
    return value.lower().replace("%20", " ")


def match_expected_documents(urls, expected_documents):
    normalized_urls = [(url, normalize_text(url)) for url in urls]
    matches = []
    for expected in expected_documents:
        keywords = [normalize_text(keyword) for keyword in expected.get("keywords", []) if keyword]
        matched_urls = []
        for original_url, normalized_url in normalized_urls:
            hit_count = sum(1 for keyword in keywords if keyword in normalized_url)
            if hit_count >= min(2, len(keywords)):
                matched_urls.append(original_url)
        matches.append({
            "id": expected.get("id"),
            "title": expected.get("title"),
            "priority": expected.get("priority"),
            "matched": bool(matched_urls),
            "matched_urls": matched_urls[:10],
        })
    return matches


def run_seed(seed, defaults, allowed_domains):
    fd, state_path = tempfile.mkstemp(prefix="selcuk_discovery_", suffix=".json")
    os.close(fd)
    try:
        config = CrawlerConfig.from_env()
        config.seed_url = seed["url"]
        config.max_depth = int(defaults.get("max_depth", 1))
        config.max_pages = int(defaults.get("max_pages", 30))
        config.crawl_delay = float(defaults.get("delay_sec", 0.5))
        config.state_file = state_path
        if allowed_domains:
            config.allowed_domains = tuple(allowed_domains)

        crawler = SelcukCrawler(config=config)
        result = crawler.crawl()
        return {
            "seed_id": seed.get("id"),
            "seed_title": seed.get("title"),
            "seed_url": seed.get("url"),
            "stats": {
                "pages_crawled": result.stats.pages_crawled,
                "documents_found": result.stats.documents_found,
                "total_discovered": result.stats.total_discovered,
                "skipped_seen": result.stats.skipped_seen,
                "skipped_excluded": result.stats.skipped_excluded,
                "skipped_robots": result.stats.skipped_robots,
                "skipped_binary": result.stats.skipped_binary,
                "errors": result.stats.errors,
                "duration_sec": result.stats.duration_sec,
            },
            "text_pages": result.text_pages,
            "document_links": result.document_links,
            "failed_urls": result.failed_urls,
        }
    finally:
        if os.path.exists(state_path):
            os.remove(state_path)


def build_discovery_report(manifest_path, max_depth=None, max_pages=None):
    manifest = load_manifest(manifest_path)
    defaults = dict(manifest.get("crawl_defaults", {}))
    if max_depth is not None:
        defaults["max_depth"] = max_depth
    if max_pages is not None:
        defaults["max_pages"] = max_pages

    allowed_domains = manifest.get("allowed_domains", [])
    seed_reports = [
        run_seed(seed, defaults, allowed_domains)
        for seed in active_seeds(manifest)
    ]

    all_text_pages = []
    all_document_links = []
    all_failed_urls = []
    for report in seed_reports:
        all_text_pages.extend(report["text_pages"])
        all_document_links.extend(report["document_links"])
        all_failed_urls.extend(report["failed_urls"])

    direct_urls = [item["url"] for item in active_direct_sources(manifest)]
    all_candidate_urls = sorted(set(all_document_links + direct_urls))
    expected_matches = match_expected_documents(
        all_candidate_urls,
        manifest.get("expected_documents", []),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_path": manifest_path,
        "crawl_defaults": defaults,
        "seed_count": len(seed_reports),
        "totals": {
            "unique_text_pages": len(set(all_text_pages)),
            "unique_document_links": len(set(all_document_links)),
            "failed_urls": len(set(all_failed_urls)),
        },
        "seed_reports": seed_reports,
        "known_direct_sources": direct_urls,
        "expected_document_matches": expected_matches,
    }


def print_human(report):
    print("=== Selcuk Web Discovery Report ===")
    print(f"Seeds              : {report['seed_count']}")
    print(f"Unique text pages  : {report['totals']['unique_text_pages']}")
    print(f"Unique documents   : {report['totals']['unique_document_links']}")
    print(f"Failed URLs        : {report['totals']['failed_urls']}")
    print("\nPer seed:")
    for seed in report["seed_reports"]:
        stats = seed["stats"]
        print(
            f"  - {seed['seed_id']}: pages={stats['pages_crawled']} "
            f"docs={stats['documents_found']} links={stats['total_discovered']} "
            f"robots={stats.get('skipped_robots', 0)} errors={stats['errors']}"
        )
    print("\nExpected documents:")
    for item in report["expected_document_matches"]:
        status = "FOUND" if item["matched"] else "MISSING"
        print(f"  - {status}: {item['id']} - {item['title']}")
        for url in item["matched_urls"][:3]:
            print(f"      {url}")


def parse_args():
    parser = argparse.ArgumentParser(description="Resmi web kaynaklarindan dokuman kesif raporu uretir.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Kaynak manifesti JSON yolu")
    parser.add_argument("--max-depth", type=int, default=None, help="Manifest derinligini override eder")
    parser.add_argument("--max-pages", type=int, default=None, help="Manifest sayfa limitini override eder")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", help="JSON raporu dosyaya yaz")
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    report = build_discovery_report(args.manifest, args.max_depth, args.max_pages)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
