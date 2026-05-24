"""Ingest Technology Faculty static sources into the existing ChromaDB snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import requests
from bs4 import BeautifulSoup
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from requests.exceptions import SSLError
from urllib3.exceptions import InsecureRequestWarning

from content_processor import ContentExtractor
from legal_ingestion import split_documents_with_optional_legal_chunking
from web_scraper import WebScraper


BATCH_ID = "faz8b2_technology_faculty"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
VALID_STATIC_RECOMMENDATIONS = {
    "static_web_or_pdf_ingestion_candidate",
    "static_web_ingestion_candidate",
    "static_pdf_ingestion_candidate",
}


def load_sources(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Technology Faculty source manifest must be a JSON list.")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_static_candidate(source: dict) -> bool:
    return (
        source.get("ingestion_recommendation") in VALID_STATIC_RECOMMENDATIONS
        and source.get("freshness") != "high"
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_with_ssl_fallback(url: str, timeout_sec: int) -> requests.Response:
    try:
        return requests.get(
            url,
            timeout=timeout_sec,
            headers={"User-Agent": BROWSER_USER_AGENT},
            allow_redirects=True,
        )
    except SSLError:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        return requests.get(
            url,
            timeout=timeout_sec,
            headers={"User-Agent": BROWSER_USER_AGENT},
            allow_redirects=True,
            verify=False,
        )


def _metadata_base(source: dict, final_url: str, indexed_at: str) -> dict:
    topics = source.get("expected_topics") or []
    return {
        "source_id": source.get("id"),
        "source": final_url or source.get("url"),
        "url": final_url or source.get("url"),
        "final_url": final_url or source.get("url"),
        "source_owner": source.get("source_owner"),
        "source_family": "technology_faculty",
        "category": source.get("category"),
        "source_type": source.get("source_type"),
        "title": source.get("title"),
        "source_title": source.get("title"),
        "expected_topics": json.dumps(topics, ensure_ascii=False),
        "expected_topics_text": ", ".join(str(topic) for topic in topics),
        "freshness": source.get("freshness"),
        "ingestion_recommendation": source.get("ingestion_recommendation"),
        "ingestion_batch": BATCH_ID,
        "indexed_at": indexed_at,
    }


def _clean_html_to_document(source: dict, response: requests.Response, indexed_at: str) -> Document:
    text = ContentExtractor.extract_main_content(response.text, url=response.url)
    if not text:
        soup = BeautifulSoup(response.text or "", "lxml")
        for tag in soup(["script", "style", "noscript", "svg", "footer", "header", "nav", "form"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    text = (text or "").strip()
    if len(text) < 80:
        raise ValueError(f"HTML content too short: {source.get('id')}")
    metadata = _metadata_base(source, response.url, indexed_at)
    metadata["source_type"] = "web_page"
    metadata["content_hash"] = _sha(text)
    return Document(page_content=text, metadata=metadata)


def _pdf_to_documents(source: dict, response: requests.Response, indexed_at: str) -> list[Document]:
    page_texts, extraction_method = WebScraper().extract_text_from_pdf(response.content, response.url)
    docs: list[Document] = []
    for page_index, text in enumerate(page_texts, start=1):
        cleaned = (text or "").strip()
        if not cleaned:
            continue
        metadata = _metadata_base(source, response.url, indexed_at)
        metadata["source_type"] = "web_pdf"
        metadata["page"] = page_index
        metadata["extraction_method"] = extraction_method
        metadata["content_hash"] = _sha(cleaned)
        docs.append(Document(page_content=cleaned, metadata=metadata))
    if not docs:
        raise ValueError(f"PDF content empty: {source.get('id')}")
    return docs


def fetch_source_documents(source: dict, timeout_sec: int = 30) -> list[Document]:
    if not _is_static_candidate(source):
        raise ValueError(f"Not a static source candidate: {source.get('id')}")
    indexed_at = _now()
    response = _request_with_ssl_fallback(source["url"], timeout_sec=timeout_sec)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    path = urlparse(response.url).path.lower()
    is_pdf = "pdf" in content_type or path.endswith(".pdf")
    if is_pdf:
        return _pdf_to_documents(source, response, indexed_at)
    return [_clean_html_to_document(source, response, indexed_at)]


def fallback_split_documents(docs: list[Document]) -> list[Document]:
    chunk_size = 1000
    chunk_overlap = 200
    result: list[Document] = []
    for doc in docs:
        text = doc.page_content or ""
        if len(text) <= chunk_size:
            result.append(doc)
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                split_at = max(
                    text.rfind("\n\n", start, end),
                    text.rfind("\n", start, end),
                    text.rfind(". ", start, end),
                    text.rfind(" ", start, end),
                )
                if split_at > start + 300:
                    end = split_at + 1
            chunk_text = text[start:end].strip()
            if chunk_text:
                result.append(Document(page_content=chunk_text, metadata=dict(doc.metadata or {})))
            if end >= len(text):
                break
            start = max(end - chunk_overlap, start + 1)
    return result


def chunk_documents(docs: list[Document]) -> list[Document]:
    chunks = split_documents_with_optional_legal_chunking(
        docs,
        fallback_splitter_func=fallback_split_documents,
        enabled=True,
    )
    for index, doc in enumerate(chunks):
        metadata = dict(doc.metadata or {})
        metadata["chunk_index"] = index
        metadata["chunk_content_hash"] = _sha(doc.page_content)
        doc.metadata = metadata
    return chunks


def _get_counts(db: Chroma) -> dict:
    data = db._collection.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    sources = {metadata.get("source") for metadata in metadatas if metadata and metadata.get("source")}
    tech_sources = {
        metadata.get("source_id")
        for metadata in metadatas
        if metadata and metadata.get("source_family") == "technology_faculty" and metadata.get("source_id")
    }
    return {
        "document_count": int(db._collection.count()),
        "unique_source_count": len(sources),
        "technology_source_count": len(tech_sources),
    }


def _delete_existing_technology_docs(db: Chroma, source_ids: list[str]) -> int:
    deleted = 0
    for source_id in source_ids:
        existing = db._collection.get(where={"source_id": source_id}, include=[])
        ids = existing.get("ids") or []
        if ids:
            db._collection.delete(ids=ids)
            deleted += len(ids)
    return deleted


def ingest_sources(sources_path: str | Path, chroma_dir: str = "chroma_db", timeout_sec: int = 30) -> dict:
    sources = [source for source in load_sources(sources_path) if _is_static_candidate(source)]
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    db = Chroma(persist_directory=chroma_dir, embedding_function=embeddings)
    before = _get_counts(db)

    items: list[dict] = []
    all_chunks: list[Document] = []
    for source in sources:
        item = {
            "id": source.get("id"),
            "title": source.get("title"),
            "url": source.get("url"),
            "fetched_documents": 0,
            "chunks": 0,
            "status": "pending",
            "error": None,
        }
        try:
            docs = fetch_source_documents(source, timeout_sec=timeout_sec)
            chunks = chunk_documents(docs)
            for chunk_index, chunk in enumerate(chunks):
                chunk.metadata["source_id"] = source.get("id")
                chunk.metadata["chunk_index"] = chunk_index
            item["fetched_documents"] = len(docs)
            item["chunks"] = len(chunks)
            item["status"] = "ok"
            all_chunks.extend(chunks)
        except Exception as exc:
            item["status"] = "error"
            item["error"] = f"{exc.__class__.__name__}: {exc}"
        items.append(item)

    report_base = {
        "generated_at": _now(),
        "chroma_dir": chroma_dir,
        "batch_id": BATCH_ID,
        "before": before,
        "processed_source_count": len(sources),
        "successful_source_count": sum(1 for item in items if item["status"] == "ok"),
        "failed_source_count": sum(1 for item in items if item["status"] != "ok"),
        "items": items,
    }
    if any(item["status"] != "ok" for item in items):
        return {
            **report_base,
            "after": before,
            "deleted_existing_chunks": 0,
            "added_chunk_count": 0,
            "net_document_count_delta": 0,
            "net_unique_source_count_delta": 0,
            "error": "One or more sources failed; ChromaDB write skipped.",
        }

    source_ids = [str(source["id"]) for source in sources]
    deleted_existing_chunks = _delete_existing_technology_docs(db, source_ids)
    ids = [
        f"tech-faculty::{doc.metadata.get('source_id')}::{index}::{doc.metadata.get('chunk_content_hash')[:12]}"
        for index, doc in enumerate(all_chunks)
    ]
    if all_chunks:
        db.add_documents(all_chunks, ids=ids)

    after = _get_counts(db)
    return {
        **report_base,
        "before": before,
        "after": after,
        "deleted_existing_chunks": deleted_existing_chunks,
        "added_chunk_count": len(all_chunks),
        "net_document_count_delta": after["document_count"] - before["document_count"],
        "net_unique_source_count_delta": after["unique_source_count"] - before["unique_source_count"],
        "error": None,
    }


def write_markdown(report: dict, path: str | Path) -> None:
    before = report["before"]
    after = report["after"]
    lines = [
        "# Technology Faculty Ingestion Report",
        "",
        f"- Batch: `{report['batch_id']}`",
        f"- Sources processed: {report['processed_source_count']}",
        f"- Successful sources: {report['successful_source_count']}",
        f"- Added chunks: {report['added_chunk_count']}",
        f"- Document count: {before['document_count']} -> {after['document_count']}",
        f"- Unique sources: {before['unique_source_count']} -> {after['unique_source_count']}",
        "",
        "## Items",
        "",
    ]
    for item in report.get("items", []):
        lines.append(f"- `{item['id']}` - {item['status']} - chunks: {item['chunks']}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Technology Faculty sources into ChromaDB.")
    parser.add_argument("--sources", default="evaluation/technology_faculty_sources.json")
    parser.add_argument("--chroma-dir", default="chroma_db")
    parser.add_argument("--report", default="technology_faculty_ingestion.local.json")
    parser.add_argument("--markdown-out")
    parser.add_argument("--timeout-sec", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = ingest_sources(args.sources, chroma_dir=args.chroma_dir, timeout_sec=args.timeout_sec)
    exit_code = 1 if report.get("error") else 0
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out and "before" in report:
        write_markdown(report, args.markdown_out)
    print(json.dumps({
        "processed_source_count": report.get("processed_source_count"),
        "successful_source_count": report.get("successful_source_count"),
        "failed_source_count": report.get("failed_source_count"),
        "added_chunk_count": report.get("added_chunk_count"),
        "before": report.get("before"),
        "after": report.get("after"),
        "error": report.get("error"),
    }, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
