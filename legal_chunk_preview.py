import argparse
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import unquote

import legal_chunker


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "chroma_db", "chroma.sqlite3")
DEFAULT_JSON_OUT = os.path.join(BASE_DIR, "legal_chunk_preview.json")
DEFAULT_MARKDOWN_OUT = os.path.join(BASE_DIR, "docs", "FAZ2C_LEGAL_CHUNK_PREVIEW_RAPORU.md")
CRITICAL_ARTICLES = ("4", "43", "44")


def metadata_value(row):
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


def normalize_for_filter(value):
    decoded = unquote(str(value or ""))
    replacements = {
        "İ": "I",
        "İ": "I",
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
        decoded = decoded.replace(old, new)
    return decoded.casefold()


def compact_text(text, max_chars=500):
    compacted = " ".join((text or "").split())
    if len(compacted) <= max_chars:
        return compacted
    return compacted[: max_chars - 3].rstrip() + "..."


def first_non_empty(values):
    for value in values:
        if value:
            return value
    return ""


def read_chroma_items(db_path=DEFAULT_DB):
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
        value = metadata_value(row)
        if key == "chroma:document":
            documents_by_id[item_id] = value or ""
        else:
            metadata_by_id[item_id][key] = value

    items = []
    for item_id in sorted(set(metadata_by_id) | set(documents_by_id)):
        metadata = metadata_by_id.get(item_id, {})
        items.append({
            "id": item_id,
            "source": metadata.get("source") or "Bilinmeyen Kaynak",
            "title": metadata.get("title") or "",
            "metadata": metadata,
            "document": documents_by_id.get(item_id, ""),
        })

    return {
        "db_exists": True,
        "embedding_count": embedding_count,
        "items": items,
    }


def group_items_by_source(items):
    grouped = defaultdict(list)
    for item in items:
        grouped[item.get("source") or "Bilinmeyen Kaynak"].append(item)
    return grouped


def source_matches_filters(source, items, source_contains=None, title_contains=None):
    source_filters = [normalize_for_filter(value) for value in (source_contains or []) if value]
    title_filters = [normalize_for_filter(value) for value in (title_contains or []) if value]
    titles = " ".join(item.get("title") or item.get("metadata", {}).get("title", "") for item in items)

    source_haystack = normalize_for_filter(source)
    title_haystack = normalize_for_filter(titles)

    source_ok = True if not source_filters else any(value in source_haystack for value in source_filters)
    title_ok = True if not title_filters else any(value in title_haystack for value in title_filters)
    return source_ok and title_ok


def select_sources(grouped, source_contains=None, title_contains=None, limit_sources=None):
    selected = []
    for source, items in grouped.items():
        if source_matches_filters(source, items, source_contains, title_contains):
            selected.append((source, items))
    selected.sort(key=lambda entry: (-len(entry[1]), entry[0]))
    if limit_sources is not None:
        selected = selected[:limit_sources]
    return selected


def page_sort_value(item):
    metadata = item.get("metadata", {})
    try:
        return int(metadata.get("page"))
    except (TypeError, ValueError):
        return 0


def has_page_metadata(items):
    return any(item.get("metadata", {}).get("page") is not None for item in items)


def build_page_texts(items):
    pages = defaultdict(list)
    for item in items:
        metadata = item.get("metadata", {})
        page = metadata.get("page")
        if page is None:
            page = 0
        pages[page].append(item)

    page_texts = []
    for page in sorted(pages, key=lambda value: int(value) if str(value).isdigit() else 0):
        ordered = sorted(pages[page], key=lambda item: item.get("id", 0))
        page_texts.append("\n".join(item.get("document") or "" for item in ordered))
    return page_texts


def build_combined_text(items):
    ordered = sorted(items, key=lambda item: item.get("id", 0))
    return "\n".join(item.get("document") or "" for item in ordered)


def common_metadata(items):
    metadata_items = [item.get("metadata", {}) for item in items]
    titles = [metadata.get("title") for metadata in metadata_items if metadata.get("title")]
    source_types = Counter(metadata.get("source_type") for metadata in metadata_items if metadata.get("source_type"))
    doc_types = Counter(metadata.get("doc_type") for metadata in metadata_items if metadata.get("doc_type"))
    metadata = dict(metadata_items[0]) if metadata_items else {}
    metadata["title"] = first_non_empty(titles)
    if source_types:
        metadata["source_type"] = source_types.most_common(1)[0][0]
    if doc_types:
        metadata["doc_type"] = doc_types.most_common(1)[0][0]
    metadata.pop("page", None)
    return metadata


def first_unique_article_numbers(chunks, limit=10):
    numbers = []
    seen = set()
    for chunk in chunks:
        if chunk.article_no in seen:
            continue
        seen.add(chunk.article_no)
        numbers.append(chunk.article_no)
        if len(numbers) >= limit:
            break
    return numbers


def article_duplicate_numbers(chunks):
    counts = Counter(chunk.article_no for chunk in chunks)
    return [number for number, count in counts.items() if count > 1]


def article_by_no(chunks, article_no):
    for chunk in chunks:
        if chunk.article_no == article_no:
            return chunk
    return None


def summarize_critical_article(summary, chunks, article_no):
    chunk = article_by_no(chunks, article_no)
    prefix = f"article_{article_no}"
    summary[f"has_article_{article_no}"] = chunk is not None
    summary[f"{prefix}_title"] = chunk.article_title if chunk else ""
    summary[f"{prefix}_title_source"] = chunk.title_source if chunk else ""
    summary[f"{prefix}_preview"] = compact_text(chunk.content if chunk else "")
    summary[f"{prefix}_page_start"] = chunk.page_start if chunk else None
    summary[f"{prefix}_page_end"] = chunk.page_end if chunk else None


def preview_source(source, items):
    metadata = common_metadata(items)
    ordered_items = sorted(items, key=lambda item: (page_sort_value(item), item.get("id", 0)))
    if has_page_metadata(ordered_items):
        raw_chunks = legal_chunker.split_pages_by_articles(
            build_page_texts(ordered_items),
            metadata,
            deduplicate=False,
        )
        reconstruction_mode = "page_metadata"
    else:
        raw_chunks = legal_chunker.split_text_by_articles(build_combined_text(ordered_items), metadata)
        reconstruction_mode = "combined_chunks"
    chunks = legal_chunker.deduplicate_articles(raw_chunks)

    summary = {
        "source": source,
        "title": metadata.get("title") or "",
        "original_chunk_count": len(items),
        "article_count": len(chunks),
        "article_count_before_dedup": len(raw_chunks),
        "article_count_after_dedup": len(chunks),
        "unique_article_count": len({chunk.article_no for chunk in chunks}),
        "duplicate_article_numbers": article_duplicate_numbers(chunks),
        "duplicate_article_numbers_before": article_duplicate_numbers(raw_chunks),
        "duplicate_article_numbers_after": article_duplicate_numbers(chunks),
        "first_article_numbers": first_unique_article_numbers(chunks, limit=10),
        "reconstruction_mode": reconstruction_mode,
        "source_type": metadata.get("source_type", ""),
        "doc_type": metadata.get("doc_type", ""),
        "clean_context_prefix_applied": any(chunk.clean_context_prefix_applied for chunk in chunks),
    }
    for article_no in CRITICAL_ARTICLES:
        summarize_critical_article(summary, chunks, article_no)
    return summary


def build_preview(
    db_path=DEFAULT_DB,
    source_contains=None,
    title_contains=None,
    limit_sources=None,
):
    loaded = read_chroma_items(db_path)
    filters = {
        "source_contains": source_contains or [],
        "title_contains": title_contains or [],
        "limit_sources": limit_sources,
    }
    if loaded is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "read_only_chroma_legal_preview",
            "db_path": db_path,
            "db_exists": False,
            "filters": filters,
            "sources": [],
            "totals": {
                "selected_source_count": 0,
                "total_articles": 0,
            },
        }

    grouped = group_items_by_source(loaded["items"])
    selected = select_sources(
        grouped,
        source_contains=source_contains,
        title_contains=title_contains,
        limit_sources=limit_sources,
    )
    sources = [preview_source(source, items) for source, items in selected]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "read_only_chroma_legal_preview",
        "db_path": db_path,
        "db_exists": True,
        "original_embedding_count": loaded["embedding_count"],
        "filters": filters,
        "sources": sources,
        "totals": {
            "selected_source_count": len(sources),
            "total_articles": sum(source.get("article_count_after_dedup", 0) for source in sources),
        },
    }


def markdown_escape(value):
    return str(value or "").replace("|", "\\|")


def _quality_report(path):
    return "2D" in os.path.basename(path).upper()


def write_markdown_report(report, path, command):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    is_quality_report = _quality_report(path)
    title = "Faz 2D Legal Chunker Kalite Raporu" if is_quality_report else "Faz 2C Legal Chunk Preview Raporu"
    lines = [
        f"# {title}",
        "",
        f"Rapor tarihi: {report.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Bu rapor mevcut ChromaDB snapshot'ını değiştirmeden legal chunker çıktısını doğrulamak için üretildi. ChromaDB'ye yazma/silme yapılmadı, data_ingestion çalıştırılmadı, web fetch veya PDF indirme yapılmadı.",
        "",
    ]
    if is_quality_report:
        lines.extend([
            "Faz 2C'de görülen başlık, duplicate madde ve bağlam kalıntısı sorunları için kalite iyileştirmeleri ölçüldü.",
            "",
            "## 2. Yapılan İyileştirmeler",
            "",
            "- `preceding_heading` ile MADDE öncesindeki kısa başlık satırı tercih ediliyor.",
            "- `[Bağlam: ...]`, `[Madde ...]` ve `...[bağlam kısaltıldı]` satırları temizleniyor.",
            "- Duplicate madde numaraları için daha uzun/temsilci içerik korunuyor ve sayfa aralığı birleştiriliyor.",
            "",
            "## 3. Test Sonuçları",
            "",
            "```text",
            "pytest sonucu final Codex cevabında özetlenmiştir.",
            "```",
            "",
            "## 4. Preview Karşılaştırması",
            "",
            "Çalıştırılan komut:",
        ])
    else:
        lines.append("## 2. Çalıştırılan Komut")
    lines.extend([
        "",
        "```powershell",
        command,
        "```",
        "",
        "### Seçilen Kaynaklar" if is_quality_report else "## 3. Seçilen Kaynaklar",
        "",
        "| # | source | title | original_chunk_count |",
        "|---:|---|---|---:|",
    ])
    for index, source in enumerate(report.get("sources", []), start=1):
        lines.append(
            f"| {index} | `{markdown_escape(source.get('source'))}` | "
            f"{markdown_escape(source.get('title'))} | {source.get('original_chunk_count', 0)} |"
        )
    if not report.get("sources"):
        lines.append("| 0 | Kaynak seçilemedi |  | 0 |")

    lines.extend([
        "",
        "### Duplicate Before/After" if is_quality_report else "## 4. Madde Yakalama Özeti",
        "",
        "| source | before | after | duplicate before | duplicate after | Madde 4 | Madde 43 | Madde 44 | İlk 10 madde no |",
        "|---|---:|---:|---|---|---:|---:|---:|---|",
    ])
    for source in report.get("sources", []):
        lines.append(
            f"| {markdown_escape(source.get('title') or source.get('source'))} | "
            f"{source.get('article_count_before_dedup', source.get('article_count', 0))} | "
            f"{source.get('article_count_after_dedup', source.get('article_count', 0))} | "
            f"{markdown_escape(', '.join(source.get('duplicate_article_numbers_before', [])) or 'Yok')} | "
            f"{markdown_escape(', '.join(source.get('duplicate_article_numbers_after', [])) or 'Yok')} | "
            f"{source.get('has_article_4')} | {source.get('has_article_43')} | "
            f"{source.get('has_article_44')} | "
            f"{markdown_escape(', '.join(source.get('first_article_numbers', [])))} |"
        )

    lines.extend([
        "",
        "### Kritik Madde Önizlemeleri" if is_quality_report else "## 5. Kritik Madde Önizlemeleri",
        "",
    ])
    for source in report.get("sources", []):
        lines.extend([
            f"### {source.get('title') or source.get('source')}",
            "",
        ])
        for article_no in CRITICAL_ARTICLES:
            prefix = f"article_{article_no}"
            lines.extend([
                f"**Madde {article_no}**",
                "",
                f"- Bulundu: {source.get(f'has_article_{article_no}')}",
                f"- Başlık: {source.get(f'{prefix}_title') or ''}",
                f"- Başlık kaynağı: {source.get(f'{prefix}_title_source') or ''}",
                f"- Sayfa: {source.get(f'{prefix}_page_start')} - {source.get(f'{prefix}_page_end')}",
                f"- Önizleme: {source.get(f'{prefix}_preview') or ''}",
                "",
            ])

    lines.extend([
        "## 5. Riskler" if is_quality_report else "## 6. Kalite Notları",
        "",
    ])
    for source in report.get("sources", []):
        duplicate_before = source.get("duplicate_article_numbers_before", [])
        duplicate_after = source.get("duplicate_article_numbers_after", [])
        duplicate_before_note = ", ".join(duplicate_before) if duplicate_before else "Yok"
        duplicate_after_note = ", ".join(duplicate_after) if duplicate_after else "Yok"
        lines.extend([
            f"- {source.get('title') or source.get('source')}:",
            "  - article_title alanları önceki başlık satırı uygunsa oradan, değilse MADDE satırındaki ilk cümle/girişten üretildi.",
            f"  - page_start/page_end `{source.get('reconstruction_mode')}` modu ile tahmin edildi.",
            f"  - Duplicate madde numarası before/after: {duplicate_before_note} / {duplicate_after_note}.",
            f"  - Bağlam prefix temizliği uygulandı mı: {source.get('clean_context_prefix_applied')}.",
            "  - Mevcut index chunk sırası, kaynak metni yaklaşık yeniden kurmak için kullanıldı; mevcut chunklar sayfa içinde semantik bölünmüş olabileceğinden bu çıktı dry-run önizleme olarak değerlendirilmelidir.",
        ])
    if not report.get("sources"):
        lines.append("- Filtrelerle eşleşen kaynak bulunamadığı için kalite değerlendirmesi yapılamadı.")

    lines.extend([
        "",
        "## 6. Sonraki Adım" if is_quality_report else "## 7. Sonraki Adım",
        "",
        "Preview başarılıysa bir sonraki adım küçük ve kontrollü bir belge üzerinde legal-chunking ingestion dry-run veya retrieval evaluation hazırlığıdır. Bu adımda da önce dry-run yaklaşımı korunmalı, ChromaDB yeniden üretimi ayrı onayla ele alınmalıdır.",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Mevcut ChromaDB kaynaklarindan legal chunking dry-run preview uretir.")
    parser.add_argument("--db", default=DEFAULT_DB, help="chroma.sqlite3 dosya yolu")
    parser.add_argument("--source-contains", action="append", default=[], help="Source URL filtresi")
    parser.add_argument("--title-contains", action="append", default=[], help="Title metadata filtresi")
    parser.add_argument("--limit-sources", type=int, default=None, help="Secilecek maksimum kaynak sayisi")
    parser.add_argument("--json", action="store_true", help="JSON raporu stdout'a yaz")
    parser.add_argument("--out", default=DEFAULT_JSON_OUT, help="JSON raporu dosyaya yaz")
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT, help="Markdown rapor yolu")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_preview(
        db_path=args.db,
        source_contains=args.source_contains,
        title_contains=args.title_contains,
        limit_sources=args.limit_sources,
    )
    source_part = " ".join(f"--source-contains {value}" for value in args.source_contains)
    title_part = " ".join(f"--title-contains {value}" for value in args.title_contains)
    command = (
        ".\\venv\\Scripts\\python.exe legal_chunk_preview.py "
        f"{source_part} {title_part} --limit-sources {args.limit_sources} --json "
        f"--out {args.out} --markdown-out {args.markdown_out}"
    ).strip()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.markdown_out:
        write_markdown_report(report, args.markdown_out, command)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Selected sources: {report.get('totals', {}).get('selected_source_count', 0)}, "
            f"articles: {report.get('totals', {}).get('total_articles', 0)}"
        )


if __name__ == "__main__":
    main()
