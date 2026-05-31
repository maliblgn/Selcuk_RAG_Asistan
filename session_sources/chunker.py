"""Chunk session-only source text while preserving simple metadata."""

from __future__ import annotations

import re
from typing import Any

from .models import SessionChunk


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def chunk_text(
    source_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 1000,
    overlap: int = 150,
    min_chars: int = 80,
) -> list[SessionChunk]:
    metadata = dict(metadata or {})
    cleaned = clean_text(text)
    if len(cleaned) < min_chars:
        return []

    chunks: list[SessionChunk] = []
    start = 0
    index = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            sentence_end = max(cleaned.rfind(".", start, end), cleaned.rfind("\n", start, end))
            if sentence_end > start + min_chars:
                end = sentence_end + 1
        piece = cleaned[start:end].strip()
        if len(piece) >= min_chars:
            chunk_metadata = dict(metadata)
            chunk_metadata["chunk_index"] = index
            chunks.append(SessionChunk(
                chunk_id=f"{source_id}_chunk_{index}",
                source_id=source_id,
                text=piece,
                metadata=chunk_metadata,
            ))
            index += 1
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def chunk_page_texts(source_id: str, pages: list[dict[str, Any]], base_metadata: dict[str, Any]) -> list[SessionChunk]:
    chunks: list[SessionChunk] = []
    for page in pages:
        metadata = dict(base_metadata)
        metadata["page_number"] = page.get("page_number")
        page_chunks = chunk_text(source_id, page.get("text", ""), metadata=metadata)
        chunks.extend(page_chunks)
    return [
        SessionChunk(
            chunk_id=f"{source_id}_chunk_{idx}",
            source_id=chunk.source_id,
            text=chunk.text,
            metadata={**chunk.metadata, "chunk_index": idx},
        )
        for idx, chunk in enumerate(chunks)
    ]

