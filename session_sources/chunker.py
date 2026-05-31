"""Chunk session-only source text while preserving section metadata."""

from __future__ import annotations

import re
from typing import Any

from .extractors import classify_section_title, enrich_metadata_flags
from .models import SessionChunk
from .text_quality import clean_extracted_text


SECTION_HEADING_RE = re.compile(
    r"^\s*(iletişim|iletisim|contact|özet|ozet|profil|eğitim(?: ve nitelikler)?|egitim(?: ve nitelikler)?|"
    r"projeler?|deneyim|beceriler|teknik beceriler|diller|yabancı diller|yabanci diller|"
    r"sertifikalar|başvuru(?: şartları)?|basvuru(?: sartlari)?|şartlar|sartlar|gerekli belgeler|"
    r"amaç|amac|kapsam|tanımlar|tanimlar|madde\s+\d+)\s*:?\s*$",
    re.IGNORECASE,
)


def clean_text(text: str, preserve_newlines: bool = False) -> str:
    cleaned = clean_extracted_text(text)
    if preserve_newlines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
        return "\n".join(line for line in lines if line).strip()
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_heading(line: str) -> bool:
    value = line.strip()
    if not value or len(value) > 80:
        return False
    if SECTION_HEADING_RE.match(value):
        return True
    if value.endswith(":") and len(value.split()) <= 5:
        return bool(classify_section_title(value[:-1]) != "general")
    return False


def _split_sections(text: str) -> list[tuple[str, str]]:
    cleaned = clean_text(text, preserve_newlines=True)
    lines = cleaned.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        if _is_heading(line):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.strip(" :")
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))

    if not any(title for title, _ in sections):
        return []
    return [(title, "\n".join(body).strip()) for title, body in sections if "\n".join(body).strip()]


def _make_chunks_for_piece(
    source_id: str,
    piece: str,
    metadata: dict[str, Any],
    start_index: int,
    chunk_size: int,
    overlap: int,
    min_chars: int,
) -> list[SessionChunk]:
    flattened = clean_text(piece)
    if len(flattened) < min_chars:
        return []
    chunks: list[SessionChunk] = []
    start = 0
    index = start_index
    while start < len(flattened):
        end = min(len(flattened), start + chunk_size)
        if end < len(flattened):
            sentence_end = max(flattened.rfind(".", start, end), flattened.rfind("\n", start, end))
            if sentence_end > start + min_chars:
                end = sentence_end + 1
        if start == 0 and end >= len(flattened):
            chunk_text_value = clean_text(piece, preserve_newlines=True)
        else:
            chunk_text_value = flattened[start:end].strip()
        if len(chunk_text_value) >= min_chars:
            chunk_metadata = enrich_metadata_flags(chunk_text_value, {**metadata, "chunk_index": index})
            chunks.append(SessionChunk(
                chunk_id=f"{source_id}_chunk_{index}",
                source_id=source_id,
                text=chunk_text_value,
                metadata=chunk_metadata,
            ))
            index += 1
        if end >= len(flattened):
            break
        start = max(0, end - overlap)
    return chunks


def chunk_text(
    source_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 1000,
    overlap: int = 150,
    min_chars: int = 80,
) -> list[SessionChunk]:
    metadata = dict(metadata or {})
    cleaned = clean_text(text, preserve_newlines=True)
    if len(clean_text(cleaned)) < min_chars:
        return []

    sections = _split_sections(cleaned)
    chunks: list[SessionChunk] = []
    if sections:
        for section_title, body in sections:
            section_metadata = dict(metadata)
            if section_title:
                section_metadata["section_title"] = section_title
                section_metadata["section_type"] = classify_section_title(section_title)
            chunks.extend(_make_chunks_for_piece(
                source_id,
                body,
                section_metadata,
                len(chunks),
                chunk_size,
                overlap,
                min_chars,
            ))
    else:
        chunks.extend(_make_chunks_for_piece(source_id, cleaned, metadata, 0, chunk_size, overlap, min_chars))

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
