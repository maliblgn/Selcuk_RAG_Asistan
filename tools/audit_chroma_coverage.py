"""Audit indexed Chroma source/topic coverage without mutating the snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from langchain_chroma import Chroma

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chroma_runtime import get_chroma_runtime_dir


TOPIC_TERMS = {
    "akts": ["akts", "avrupa kredi transfer"],
    "ales": ["ales", "akademik personel"],
    "agno_gano": ["agno", "gano", "not ortalamasi", "not ortalaması"],
    "cift_anadal": ["cift anadal", "çift anadal", "cift ana dal", "çift ana dal", "cap", "çap"],
    "lisansustu": ["lisansustu", "lisansüstü", "yuksek lisans", "yüksek lisans", "doktora"],
    "staj": ["staj"],
    "teknoloji_fakultesi": ["teknoloji fakultesi", "teknoloji fakültesi"],
    "yemekhane": ["yemekhane", "yemek menusu", "yemek menüsü"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(value: object) -> str:
    text = str(value or "").casefold()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "İ": "i",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _source_key(metadata: dict) -> str:
    return str(metadata.get("title") or metadata.get("source_title") or metadata.get("source") or "unknown")


def build_coverage_report(chroma_dir: str = "chroma_db", sample_limit: int = 3) -> dict:
    if chroma_dir == "chroma_db":
        chroma_dir = get_chroma_runtime_dir(chroma_dir)
    db = Chroma(persist_directory=chroma_dir)
    collection = db._collection
    data = collection.get(include=["documents", "metadatas"])
    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []

    source_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    topic_hits: dict[str, set[str]] = defaultdict(set)
    topic_samples: dict[str, list[dict]] = defaultdict(list)

    for document, metadata in zip(documents, metadatas):
        metadata = metadata or {}
        source = _source_key(metadata)
        source_counts[source] += 1
        source_type_counts[str(metadata.get("source_type") or "unknown")] += 1
        searchable = _norm(" ".join([
            str(document or ""),
            str(metadata.get("title") or ""),
            str(metadata.get("source") or ""),
            str(metadata.get("article_title") or ""),
            str(metadata.get("source_family") or ""),
        ]))
        for topic, terms in TOPIC_TERMS.items():
            if any(_norm(term) in searchable for term in terms):
                topic_hits[topic].add(source)
                if len(topic_samples[topic]) < sample_limit:
                    topic_samples[topic].append({
                        "source": source,
                        "article_title": metadata.get("article_title") or "",
                        "snippet": str(document or "")[:240],
                    })

    return {
        "generated_at": _now(),
        "chroma_dir": chroma_dir,
        "document_count": len(documents),
        "unique_source_count": len(source_counts),
        "source_type_counts": dict(source_type_counts),
        "top_sources": [{"source": source, "chunk_count": count} for source, count in source_counts.most_common(20)],
        "topic_coverage": {
            topic: {
                "source_count": len(sources),
                "covered": bool(sources),
                "sample_sources": sorted(sources)[:10],
                "samples": topic_samples.get(topic, []),
            }
            for topic, sources in sorted(topic_hits.items())
        },
        "missing_topics": [topic for topic in TOPIC_TERMS if not topic_hits.get(topic)],
    }


def write_markdown(report: dict, path: str | Path) -> None:
    lines = [
        "# Chroma Coverage Inventory",
        "",
        f"- Chroma dir: {report['chroma_dir']}",
        f"- Documents/chunks: {report['document_count']}",
        f"- Unique sources: {report['unique_source_count']}",
        f"- Missing topics: {', '.join(report['missing_topics']) or 'none'}",
        "",
        "## Topic Coverage",
        "",
        "| Topic | Covered | Source count |",
        "| --- | --- | ---: |",
    ]
    for topic, details in report["topic_coverage"].items():
        lines.append(f"| {topic} | {details['covered']} | {details['source_count']} |")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Chroma topic/source coverage.")
    parser.add_argument("--chroma-dir", default="chroma_db")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_coverage_report(args.chroma_dir)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown_out)
    print(json.dumps({
        "document_count": report["document_count"],
        "unique_source_count": report["unique_source_count"],
        "missing_topics": report["missing_topics"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
