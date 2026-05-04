import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import legal_chunker  # noqa: E402
from legal_chunk_preview import (  # noqa: E402
    build_page_texts,
    common_metadata,
    group_items_by_source,
    read_chroma_items,
    select_sources,
)


DEFAULT_SOURCE_DB = os.path.join(BASE_DIR, "chroma_db", "chroma.sqlite3")
DEFAULT_TARGET_DB = os.path.join(BASE_DIR, "chroma_db_legal_test")
DEFAULT_OUT = os.path.join(BASE_DIR, "legal_test_index_report.json")
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


def resolve_path(path):
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(BASE_DIR, path))


def guard_target_db(target_db):
    target = resolve_path(target_db)
    main = os.path.abspath(os.path.join(BASE_DIR, "chroma_db"))
    if target == main:
        raise ValueError("Ana chroma_db hedef DB olarak kullanilamaz.")
    if os.path.basename(target).lower() == "chroma_db":
        raise ValueError("Hedef DB klasoru chroma_db adinda olamaz.")
    return target


def clear_target_db(target_db):
    target = guard_target_db(target_db)
    if os.path.exists(target):
        shutil.rmtree(target)


def page_sort_value(item):
    try:
        return int((item.get("metadata") or {}).get("page"))
    except (TypeError, ValueError):
        return 0


def build_article_documents_for_source(source, items):
    ordered_items = sorted(items, key=lambda item: (page_sort_value(item), item.get("id", 0)))
    metadata = common_metadata(ordered_items)
    metadata.update({
        "source": source,
        "test_index": True,
    })
    chunks = legal_chunker.split_pages_by_articles(
        build_page_texts(ordered_items),
        source_metadata=metadata,
        deduplicate=True,
    )
    docs = legal_chunker.article_chunks_to_documents(chunks, source_metadata=metadata)
    for doc in docs:
        doc.metadata["test_index"] = True
        doc.metadata["chunk_type"] = "article"
        doc.metadata["legal_chunker"] = True
    return docs


def summarize_source(source, items, docs):
    article_numbers = {str(doc.metadata.get("article_no")) for doc in docs}
    return {
        "source": source,
        "title": (items[0].get("metadata") or {}).get("title", "") if items else "",
        "original_chunk_count": len(items),
        "article_count": len(docs),
        "has_article_4": "4" in article_numbers,
        "has_article_43": "43" in article_numbers,
        "has_article_44": "44" in article_numbers,
    }


def select_source_items(source_db, source_contains=None, title_contains=None, limit_sources=2):
    loaded = read_chroma_items(source_db)
    if loaded is None:
        return []
    grouped = group_items_by_source(loaded["items"])
    return select_sources(
        grouped,
        source_contains=source_contains or [],
        title_contains=title_contains or [],
        limit_sources=limit_sources,
    )


def build_legal_test_index(
    source_db=DEFAULT_SOURCE_DB,
    target_db=DEFAULT_TARGET_DB,
    source_contains=None,
    title_contains=None,
    limit_sources=2,
    clear_target=False,
):
    target = guard_target_db(target_db)
    if clear_target:
        clear_target_db(target)

    selected = select_source_items(
        source_db,
        source_contains=source_contains,
        title_contains=title_contains,
        limit_sources=limit_sources,
    )
    all_docs: list[Document] = []
    source_summaries = []
    for source, items in selected:
        docs = build_article_documents_for_source(source, items)
        all_docs.extend(docs)
        source_summaries.append(summarize_source(source, items, docs))

    if all_docs:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        Chroma.from_documents(
            documents=all_docs,
            embedding=embeddings,
            persist_directory=target,
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_db": source_db,
        "target_db": target,
        "embedding_model": EMBEDDING_MODEL,
        "selected_source_count": len(selected),
        "written_article_chunks": len(all_docs),
        "sources": source_summaries,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Read-only ana ChromaDB'den legal chunking test index olusturur.")
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB, help="Ana Chroma sqlite3 yolu")
    parser.add_argument("--source-contains", action="append", default=[], help="Source URL filtresi")
    parser.add_argument("--title-contains", action="append", default=[], help="Title filtresi")
    parser.add_argument("--limit-sources", type=int, default=2, help="Secilecek maksimum kaynak")
    parser.add_argument("--target-db", default=DEFAULT_TARGET_DB, help="Test ChromaDB hedef klasoru")
    parser.add_argument("--out", default=DEFAULT_OUT, help="JSON rapor yolu")
    parser.add_argument("--clear-target", action="store_true", help="Sadece hedef test DB klasorunu temizle")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_legal_test_index(
        source_db=args.source_db,
        target_db=args.target_db,
        source_contains=args.source_contains,
        title_contains=args.title_contains,
        limit_sources=args.limit_sources,
        clear_target=args.clear_target,
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "selected_source_count": report["selected_source_count"],
        "written_article_chunks": report["written_article_chunks"],
        "target_db": report["target_db"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
