import logging
import os
from collections import defaultdict
from typing import Callable, Iterable

from langchain_core.documents import Document

import legal_chunker


logger = logging.getLogger(__name__)


def parse_env_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def legal_chunking_enabled(explicit=False):
    return bool(explicit) or parse_env_bool(os.getenv("LEGAL_CHUNKING_ENABLED"), False)


def _has_page_metadata(doc: Document) -> bool:
    return (doc.metadata or {}).get("page") is not None


def _is_pdf_page_doc(doc: Document) -> bool:
    metadata = doc.metadata or {}
    return metadata.get("source_type") == "web_pdf" and metadata.get("source") and _has_page_metadata(doc)


def _sort_by_page(docs: Iterable[Document]) -> list[Document]:
    def page_value(doc):
        try:
            return int((doc.metadata or {}).get("page"))
        except (TypeError, ValueError):
            return 0

    return sorted(docs, key=page_value)


def _common_metadata(docs: list[Document]) -> dict:
    if not docs:
        return {}
    metadata = dict(docs[0].metadata or {})
    metadata.pop("page", None)
    return metadata


def _split_pdf_group_to_articles(docs: list[Document]) -> list[Document]:
    ordered_docs = _sort_by_page(docs)
    page_texts = [doc.page_content for doc in ordered_docs]
    combined_text = "\n".join(page_texts)
    if not legal_chunker.looks_like_legal_text(combined_text):
        return []
    chunks = legal_chunker.split_pages_by_articles(
        page_texts,
        source_metadata=_common_metadata(ordered_docs),
    )
    if not chunks:
        return []
    return legal_chunker.article_chunks_to_documents(
        chunks,
        source_metadata=_common_metadata(ordered_docs),
    )


def _split_single_doc_to_articles(doc: Document) -> list[Document]:
    if not legal_chunker.looks_like_legal_text(doc.page_content):
        return []
    chunks = legal_chunker.split_text_by_articles(
        doc.page_content,
        source_metadata=doc.metadata,
    )
    if not chunks:
        return []
    return legal_chunker.article_chunks_to_documents(chunks, source_metadata=doc.metadata)


def split_documents_with_optional_legal_chunking(
    docs: list[Document],
    fallback_splitter_func: Callable[[list[Document]], list[Document]],
    enabled=False,
) -> list[Document]:
    """Legal chunking aciksa mevzuat metinlerini madde bazli bol, degilse fallback kullan."""
    if not enabled:
        return fallback_splitter_func(docs)

    pdf_groups = defaultdict(list)
    ordered_units = []
    seen_pdf_sources = set()

    for doc in docs:
        if _is_pdf_page_doc(doc):
            source = doc.metadata["source"]
            pdf_groups[source].append(doc)
            if source not in seen_pdf_sources:
                seen_pdf_sources.add(source)
                ordered_units.append(("pdf_group", source))
        else:
            ordered_units.append(("single", doc))

    result: list[Document] = []
    for unit_type, payload in ordered_units:
        if unit_type == "pdf_group":
            group_docs = pdf_groups[payload]
            try:
                article_docs = _split_pdf_group_to_articles(group_docs)
            except Exception as exc:
                logger.warning("Legal chunker PDF grubu icin hata verdi, fallback kullaniliyor: %s", exc)
                article_docs = []
            if article_docs:
                result.extend(article_docs)
            else:
                result.extend(fallback_splitter_func(group_docs))
            continue

        doc = payload
        try:
            article_docs = _split_single_doc_to_articles(doc)
        except Exception as exc:
            logger.warning("Legal chunker dokuman icin hata verdi, fallback kullaniliyor: %s", exc)
            article_docs = []
        if article_docs:
            result.extend(article_docs)
        else:
            result.extend(fallback_splitter_func([doc]))

    return result
