import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone

from langchain_chroma import Chroma


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_report(db_path, status, reason):
    sqlite_path = os.path.join(db_path, "chroma.sqlite3")
    return {
        "generated_at": _now(),
        "db_path": db_path,
        "sqlite_path": sqlite_path,
        "db_exists": os.path.isdir(db_path),
        "sqlite_exists": os.path.exists(sqlite_path),
        "status": status,
        "ok": False,
        "reason": reason,
        "collection_readable": False,
        "document_count": 0,
        "unique_source_count": 0,
        "source_type_counts": {},
        "error": None,
    }


def check_chroma_health(db_path="chroma_db"):
    """Return a lightweight read-only health report for a Chroma persist directory."""
    db_path = os.path.abspath(db_path)
    sqlite_path = os.path.join(db_path, "chroma.sqlite3")

    if not os.path.isdir(db_path):
        return _empty_report(db_path, "missing", "ChromaDB klasoru bulunamadi.")

    if not os.path.exists(sqlite_path):
        return _empty_report(db_path, "missing_sqlite", "chroma.sqlite3 bulunamadi.")

    report = {
        "generated_at": _now(),
        "db_path": db_path,
        "sqlite_path": sqlite_path,
        "db_exists": True,
        "sqlite_exists": True,
        "status": "unknown",
        "ok": False,
        "reason": "",
        "collection_readable": False,
        "document_count": 0,
        "unique_source_count": 0,
        "source_type_counts": {},
        "error": None,
    }

    try:
        db = Chroma(persist_directory=db_path)
        collection = db._collection
        document_count = int(collection.count())
        data = collection.get(include=["metadatas"])
    except Exception as exc:
        error = str(exc)
        status = "collection_missing" if "does not exist" in error.lower() else "collection_unreadable"
        report.update({
            "status": status,
            "reason": "Chroma collection okunamadi.",
            "error": error,
        })
        return report

    metadatas = data.get("metadatas") or []
    sources = set()
    source_type_counts = Counter()
    for metadata in metadatas:
        metadata = metadata or {}
        if metadata.get("source"):
            sources.add(metadata["source"])
        source_type_counts[metadata.get("source_type") or "unknown"] += 1

    status = "ok" if document_count > 0 else "empty"
    report.update({
        "status": status,
        "ok": status == "ok",
        "reason": "ChromaDB okunabilir." if status == "ok" else "ChromaDB okunabilir fakat collection bos.",
        "collection_readable": True,
        "document_count": document_count,
        "unique_source_count": len(sources),
        "source_type_counts": dict(source_type_counts),
    })
    return report


def print_human(report):
    print("=== ChromaDB Health ===")
    print(f"Status              : {report['status']}")
    print(f"OK                  : {report['ok']}")
    print(f"DB path             : {report['db_path']}")
    print(f"DB exists           : {report['db_exists']}")
    print(f"SQLite exists       : {report['sqlite_exists']}")
    print(f"Collection readable : {report['collection_readable']}")
    print(f"Document count      : {report['document_count']}")
    print(f"Unique sources      : {report['unique_source_count']}")
    print("Source type counts:")
    for key, value in sorted(report.get("source_type_counts", {}).items()):
        print(f"  - {key}: {value}")
    if report.get("error"):
        print(f"Error               : {report['error']}")
    else:
        print(f"Reason              : {report['reason']}")


def parse_args():
    parser = argparse.ArgumentParser(description="ChromaDB healthcheck raporu uretir.")
    parser.add_argument("--db-path", default="chroma_db", help="ChromaDB persist directory")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", help="JSON raporu dosyaya yaz")
    return parser.parse_args()


def main():
    args = parse_args()
    report = check_chroma_health(args.db_path)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
