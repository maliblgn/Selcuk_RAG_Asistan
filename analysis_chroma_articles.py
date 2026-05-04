import argparse
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import unquote


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "chroma_db", "chroma.sqlite3")
DEFAULT_JSON_OUT = os.path.join(BASE_DIR, "chroma_article_analysis.json")
DEFAULT_MARKDOWN_OUT = os.path.join(BASE_DIR, "docs", "FAZ1C_CHROMA_MADDE_ANALIZ_RAPORU.md")

ARTICLE_RE = re.compile(r"(?:^|\n)\s*MADDE\s+(\d+)\s*[-–]", re.IGNORECASE | re.MULTILINE)
TANIMLAR_RE = re.compile(r"tanımlar", re.IGNORECASE)
AKTS_RE = re.compile(r"AKTS", re.IGNORECASE)
YETERLIK_RE = re.compile(r"yeterlik sınav|doktora yeterlik|yeterlilik sınav", re.IGNORECASE)


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


def normalize_for_search(value):
    value = unquote(str(value or ""))
    replacements = {
        "İ": "I",
        "ı": "i",
        "ğ": "g",
        "Ğ": "G",
        "ü": "u",
        "Ü": "U",
        "ş": "s",
        "Ş": "S",
        "ö": "o",
        "Ö": "O",
        "ç": "c",
        "Ç": "C",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value.casefold()


def first_non_empty(values):
    for value in values:
        if value:
            return value
    return ""


def unique_article_numbers(text):
    numbers = []
    seen = set()
    for match in ARTICLE_RE.finditer(text or ""):
        number = match.group(1)
        if number not in seen:
            seen.add(number)
            numbers.append(number)
    return numbers


def text_flags(text):
    text = text or ""
    return {
        "has_tanimlar": bool(TANIMLAR_RE.search(text)),
        "has_akts": bool(AKTS_RE.search(text)),
        "has_yeterlik": bool(YETERLIK_RE.search(text)),
    }


def aggregate_source(source, items):
    chunk_texts = [item.get("document") or "" for item in items]
    combined_text = "\n".join(chunk_texts)
    article_numbers = unique_article_numbers(combined_text)
    metadata_items = [item.get("metadata", {}) for item in items]
    source_types = Counter(item.get("source_type") for item in metadata_items if item.get("source_type"))
    doc_types = Counter(item.get("doc_type") for item in metadata_items if item.get("doc_type"))
    titles = [item.get("title") for item in metadata_items if item.get("title")]
    flags = text_flags(combined_text)

    return {
        "source": source,
        "title": first_non_empty(titles),
        "chunk_count": len(items),
        "source_type": source_types.most_common(1)[0][0] if source_types else "unknown",
        "doc_type": doc_types.most_common(1)[0][0] if doc_types else "unknown",
        "has_madde": bool(article_numbers),
        "estimated_article_count": len(article_numbers),
        "first_article_numbers": article_numbers[:10],
        **flags,
    }


def read_chroma_rows(db_path):
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
    documents_by_id = {}
    for row in rows:
        item_id, key = row[0], row[1]
        value = _metadata_value(row)
        if key == "chroma:document":
            documents_by_id[item_id] = value or ""
        else:
            metadata_by_id[item_id][key] = value

    items = []
    for item_id in set(metadata_by_id) | set(documents_by_id):
        metadata = metadata_by_id.get(item_id, {})
        source = metadata.get("source") or "Bilinmeyen Kaynak"
        items.append({
            "id": item_id,
            "source": source,
            "metadata": metadata,
            "document": documents_by_id.get(item_id, ""),
        })

    return embedding_count, items


def build_analysis(db_path=DEFAULT_DB):
    loaded = read_chroma_rows(db_path)
    if loaded is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "db_path": db_path,
            "db_exists": False,
            "totals": {
                "chunk_count": 0,
                "unique_sources": 0,
                "sources_with_madde": 0,
                "estimated_total_articles": 0,
            },
            "source_type_counts": {},
            "doc_type_counts": {},
            "sources": [],
        }

    embedding_count, items = loaded
    grouped = defaultdict(list)
    source_type_counts = Counter()
    doc_type_counts = Counter()

    for item in items:
        metadata = item.get("metadata", {})
        grouped[item.get("source") or "Bilinmeyen Kaynak"].append(item)
        if metadata.get("source_type"):
            source_type_counts[metadata["source_type"]] += 1
        if metadata.get("doc_type"):
            doc_type_counts[metadata["doc_type"]] += 1

    sources = [aggregate_source(source, source_items) for source, source_items in grouped.items()]
    sources.sort(key=lambda item: (-item["chunk_count"], item["source"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": db_path,
        "db_exists": True,
        "totals": {
            "chunk_count": embedding_count,
            "unique_sources": len(sources),
            "sources_with_madde": sum(1 for source in sources if source["has_madde"]),
            "estimated_total_articles": sum(source["estimated_article_count"] for source in sources),
        },
        "source_type_counts": dict(source_type_counts),
        "doc_type_counts": dict(doc_type_counts),
        "sources": sources,
    }


def is_lisansustu_source(source):
    haystack = normalize_for_search(f"{source.get('title', '')} {source.get('source', '')}")
    return "lisansustu" in haystack


def markdown_table_escape(value):
    return str(value or "").replace("|", "\\|")


def write_markdown_report(report, path, command):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    totals = report.get("totals", {})
    lines = [
        "# Faz 1C Chroma Madde Analiz Raporu",
        "",
        f"Rapor tarihi: {report.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Bu rapor mevcut ChromaDB snapshot'ını değiştirmeden madde bazlı chunklama ihtiyacını analiz eder. ChromaDB'ye yazma/silme yapılmadı, ingestion çalıştırılmadı, PDF indirilmedi ve web fetch yapılmadı.",
        "",
        "## 2. Genel Kapsam",
        "",
        f"- ChromaDB mevcut mu: {report.get('db_exists')}",
        f"- Toplam chunk: {totals.get('chunk_count', 0)}",
        f"- Benzersiz kaynak: {totals.get('unique_sources', 0)}",
        f"- MADDE yapısı görülen kaynak: {totals.get('sources_with_madde', 0)}",
        f"- Tahmini toplam farklı MADDE numarası: {totals.get('estimated_total_articles', 0)}",
        "",
        "Source type dağılımı:",
        "",
        "| source_type | chunk sayısı |",
        "|---|---:|",
    ]
    for key, value in sorted(report.get("source_type_counts", {}).items()):
        lines.append(f"| {markdown_table_escape(key)} | {value} |")

    lines.extend([
        "",
        "Doc type dağılımı:",
        "",
        "| doc_type | chunk sayısı |",
        "|---|---:|",
    ])
    for key, value in sorted(report.get("doc_type_counts", {}).items()):
        lines.append(f"| {markdown_table_escape(key)} | {value} |")

    lines.extend([
        "",
        "## 3. En Çok Chunk İçeren Kaynaklar",
        "",
        "| # | chunk | doc_type | source_type | title | source |",
        "|---:|---:|---|---|---|---|",
    ])
    for index, source in enumerate(report.get("sources", [])[:20], start=1):
        lines.append(
            f"| {index} | {source['chunk_count']} | {markdown_table_escape(source['doc_type'])} | "
            f"{markdown_table_escape(source['source_type'])} | {markdown_table_escape(source['title'])} | "
            f"`{markdown_table_escape(source['source'])}` |"
        )

    madde_sources = [source for source in report.get("sources", []) if source.get("has_madde")]
    lines.extend([
        "",
        "## 4. MADDE Yapısı Tespiti",
        "",
        f"- MADDE yapısı görülen kaynak sayısı: {len(madde_sources)}",
        f"- Tahmini toplam farklı MADDE numarası: {totals.get('estimated_total_articles', 0)}",
        "",
        "| # | chunk | tahmini madde | ilk madde numaraları | title | source |",
        "|---:|---:|---:|---|---|---|",
    ])
    for index, source in enumerate(madde_sources[:15], start=1):
        first_numbers = ", ".join(source.get("first_article_numbers", []))
        lines.append(
            f"| {index} | {source['chunk_count']} | {source['estimated_article_count']} | "
            f"{markdown_table_escape(first_numbers)} | {markdown_table_escape(source['title'])} | "
            f"`{markdown_table_escape(source['source'])}` |"
        )

    lisansustu_sources = [source for source in report.get("sources", []) if is_lisansustu_source(source)]
    lines.extend([
        "",
        "## 5. Lisansüstü Yönetmelik Odak Kontrolü",
        "",
        "| chunk | tahmini madde | AKTS | Tanımlar | Yeterlik | title | source |",
        "|---:|---:|---:|---:|---:|---|---|",
    ])
    for source in lisansustu_sources:
        lines.append(
            f"| {source['chunk_count']} | {source['estimated_article_count']} | "
            f"{source['has_akts']} | {source['has_tanimlar']} | {source['has_yeterlik']} | "
            f"{markdown_table_escape(source['title'])} | `{markdown_table_escape(source['source'])}` |"
        )
    if not lisansustu_sources:
        lines.append("| 0 | 0 | False | False | False | Lisansüstü kaynak bulunamadı |  |")

    lines.extend([
        "",
        "## 6. Sonuç ve Sonraki Adım",
        "",
        "Mevcut ChromaDB içinde yönetmelik/yönerge benzeri PDF kaynaklarında `MADDE` yapısı ölçülebiliyor. Ancak mevcut chunklar sayfa veya semantik bölünmüş olabilir; bir madde birden fazla chunk'a dağılabilir veya tek chunk içinde birden fazla madde bulunabilir. Bu nedenle madde bazlı cevap doğruluğu için bir sonraki fazda `legal_chunker.py` tasarlanmalı ve ingestion'a uygulanmadan önce ayrı örnek metinlerle doğrulanmalıdır.",
        "",
        "## Çalıştırılan Komut",
        "",
        "```powershell",
        command,
        "```",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_human(report):
    totals = report.get("totals", {})
    print("=== Chroma Article Analysis ===")
    print(f"DB exists                 : {report.get('db_exists')}")
    print(f"Chunks                    : {totals.get('chunk_count', 0)}")
    print(f"Unique sources            : {totals.get('unique_sources', 0)}")
    print(f"Sources with MADDE        : {totals.get('sources_with_madde', 0)}")
    print(f"Estimated total articles  : {totals.get('estimated_total_articles', 0)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Mevcut ChromaDB kaynaklarinda MADDE yapisi analizi yapar.")
    parser.add_argument("--db", default=DEFAULT_DB, help="chroma.sqlite3 dosya yolu")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", default=DEFAULT_JSON_OUT, help="JSON raporu dosyaya yaz")
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT, help="Markdown rapor yolu")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_analysis(args.db)
    command = (
        ".\\venv\\Scripts\\python.exe analysis_chroma_articles.py "
        f"--json --out {args.out} --markdown-out {args.markdown_out}"
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.markdown_out:
        write_markdown_report(report, args.markdown_out, command)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
