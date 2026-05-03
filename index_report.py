import argparse
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "chroma_db", "chroma.sqlite3")
DEFAULT_MANIFEST = os.path.join(BASE_DIR, "source_manifest.json")


def _metadata_value(row):
    _id, key, string_value, int_value, float_value, bool_value = row
    if string_value is not None:
        return string_value
    if int_value is not None:
        return int_value
    if float_value is not None:
        return float_value
    if bool_value is not None:
        return bool(bool_value)
    return None


def load_manifest(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload


def inspect_chroma_sqlite(db_path):
    if not os.path.exists(db_path):
        return {
            "exists": False,
            "embedding_count": 0,
            "unique_sources": 0,
            "sources": [],
            "source_type_counts": {},
            "doc_type_counts": {},
            "unit_counts": {},
        }

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        embedding_count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        rows = cur.execute(
            """
            SELECT id, key, string_value, int_value, float_value, bool_value
            FROM embedding_metadata
            """
        ).fetchall()
    finally:
        conn.close()

    metadata_by_id = defaultdict(dict)
    for row in rows:
        item_id, key = row[0], row[1]
        metadata_by_id[item_id][key] = _metadata_value(row)

    source_counts = Counter()
    source_type_counts = Counter()
    doc_type_counts = Counter()
    unit_counts = Counter()
    sample_titles = {}

    for metadata in metadata_by_id.values():
        source = metadata.get("source") or "Bilinmeyen Kaynak"
        source_counts[source] += 1
        if metadata.get("source_type"):
            source_type_counts[metadata["source_type"]] += 1
        if metadata.get("doc_type"):
            doc_type_counts[metadata["doc_type"]] += 1
        if metadata.get("unit"):
            unit_counts[metadata["unit"]] += 1
        if source not in sample_titles and metadata.get("title"):
            sample_titles[source] = metadata["title"]

    sources = [
        {
            "source": source,
            "title": sample_titles.get(source, ""),
            "chunks": count,
        }
        for source, count in source_counts.most_common()
    ]

    return {
        "exists": True,
        "embedding_count": embedding_count,
        "unique_sources": len(source_counts),
        "sources": sources,
        "source_type_counts": dict(source_type_counts),
        "doc_type_counts": dict(doc_type_counts),
        "unit_counts": dict(unit_counts),
    }


def compare_manifest(report, manifest):
    active_sources = []
    for section in ("crawl_seeds", "known_direct_sources", "sources"):
        active_sources.extend(
            {
                **item,
                "manifest_section": section,
            }
            for item in manifest.get(section, [])
            if item.get("active", True) and item.get("url")
        )
    indexed = {item["source"] for item in report.get("sources", [])}
    missing = []
    for item in active_sources:
        url = item.get("url")
        if url not in indexed:
            missing.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "url": url,
                "priority": item.get("priority"),
                "section": item.get("manifest_section"),
            })

    searchable_text = " ".join(
        " ".join(str(value) for value in item.values() if value)
        for item in report.get("sources", [])
    ).lower()
    expected_matches = []
    for item in manifest.get("expected_documents", []):
        keywords = [str(k).lower() for k in item.get("keywords", []) if k]
        matched_keywords = [keyword for keyword in keywords if keyword in searchable_text]
        matched = len(matched_keywords) >= min(2, len(keywords)) if keywords else False
        expected_matches.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "priority": item.get("priority"),
            "matched": matched,
            "matched_keywords": matched_keywords,
            "keywords": keywords,
        })

    return {
        "manifest_active_count": len(active_sources),
        "manifest_missing_from_index": missing,
        "expected_documents": expected_matches,
    }


def build_report(db_path=DEFAULT_DB, manifest_path=DEFAULT_MANIFEST):
    manifest = load_manifest(manifest_path)
    report = inspect_chroma_sqlite(db_path)
    report.update({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": db_path,
        "manifest_path": manifest_path if manifest else None,
    })
    if manifest:
        report["manifest"] = compare_manifest(report, manifest)
    return report


def print_human(report):
    print("=== Selcuk RAG Index Report ===")
    print(f"DB exists          : {report['exists']}")
    print(f"Embedding count    : {report['embedding_count']}")
    print(f"Unique sources     : {report['unique_sources']}")
    print("\nSource type counts:")
    for key, value in sorted(report.get("source_type_counts", {}).items()):
        print(f"  - {key}: {value}")
    print("\nDoc type counts:")
    for key, value in sorted(report.get("doc_type_counts", {}).items()):
        print(f"  - {key}: {value}")
    print("\nIndexed sources:")
    for item in report.get("sources", []):
        title = f" | {item['title']}" if item.get("title") else ""
        print(f"  - {item['chunks']:>4} chunks | {item['source']}{title}")

    manifest = report.get("manifest")
    if manifest:
        print("\nManifest coverage:")
        print(f"  Active sources: {manifest['manifest_active_count']}")
        print(f"  Missing active sources: {len(manifest['manifest_missing_from_index'])}")
        for item in manifest["manifest_missing_from_index"]:
            print(f"    - {item['id']} ({item['section']}): {item['url']}")
        expected = manifest.get("expected_documents", [])
        matched = [item for item in expected if item.get("matched")]
        print(f"  Expected document title/keyword matches: {len(matched)}/{len(expected)}")
        for item in expected:
            status = "FOUND" if item.get("matched") else "MISSING"
            print(f"    - {status}: {item['id']} ({', '.join(item.get('matched_keywords', []))})")


def parse_args():
    parser = argparse.ArgumentParser(description="ChromaDB index kapsam raporu uretir.")
    parser.add_argument("--db", default=DEFAULT_DB, help="chroma.sqlite3 dosya yolu")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Kaynak manifesti JSON yolu")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", help="JSON raporu dosyaya yaz")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_report(args.db, args.manifest)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
