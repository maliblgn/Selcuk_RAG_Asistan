import argparse
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from data_ingestion import authorized_source_mode_enabled


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(BASE_DIR, "source_manifest.json")


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_source(item):
    active = item.get("active", True)
    requires_permission = item.get("requires_permission", False)
    if active:
        return "active"
    if requires_permission:
        return "authorized_only"
    return "inactive"


def build_inventory(manifest_path):
    manifest = load_manifest(manifest_path)
    authorized_mode = authorized_source_mode_enabled()
    sources = []

    for section in ("crawl_seeds", "known_direct_sources", "sources"):
        for item in manifest.get(section, []):
            status = classify_source(item)
            included_now = status == "active" or (status == "authorized_only" and authorized_mode)
            sources.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "section": section,
                "category": item.get("category"),
                "priority": item.get("priority"),
                "url": item.get("url"),
                "status": status,
                "included_now": included_now,
                "requires_permission": item.get("requires_permission", False),
                "notes": item.get("notes"),
            })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_path": manifest_path,
        "authorized_source_mode": authorized_mode,
        "totals": {
            "active": sum(1 for item in sources if item["status"] == "active"),
            "authorized_only": sum(1 for item in sources if item["status"] == "authorized_only"),
            "inactive": sum(1 for item in sources if item["status"] == "inactive"),
            "included_now": sum(1 for item in sources if item["included_now"]),
        },
        "sources": sources,
        "expected_documents": manifest.get("expected_documents", []),
    }


def print_human(report):
    totals = report["totals"]
    print("=== Source Inventory ===")
    print(f"Authorized mode : {report['authorized_source_mode']}")
    print(f"Included now    : {totals['included_now']}")
    print(f"Active          : {totals['active']}")
    print(f"Authorized only : {totals['authorized_only']}")
    print(f"Inactive        : {totals['inactive']}")
    print("\nSources:")
    for item in report["sources"]:
        marker = "INCLUDED" if item["included_now"] else "SKIPPED"
        print(f"  - {marker} [{item['status']}] {item['id']} - {item['title']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Manifest kaynak envanteri raporu uretir.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Kaynak manifesti JSON yolu")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", help="JSON raporu dosyaya yaz")
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    report = build_inventory(args.manifest)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
