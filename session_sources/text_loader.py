"""Pasted text loader for session-only sources."""

from __future__ import annotations

import hashlib

from .chunker import chunk_text, clean_text
from .models import SessionSource, utc_now


def build_text_session_source(text: str, title: str = "Yapıştırılan metin") -> tuple[SessionSource, list]:
    cleaned = clean_text(text, preserve_newlines=True)
    source_id = "session_text_" + hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
    if len(clean_text(cleaned)) < 80:
        source = SessionSource(
            id=source_id,
            source_type="pasted_text",
            title=title,
            original_name_or_url=title,
            created_at=utc_now(),
            document_count=0,
            chunk_count=0,
            status="error",
            error_message="Geçici metin kaynağı için yeterli okunabilir metin bulunamadı.",
            source_label=f"Geçici metin: {title}",
        )
        return source, []
    chunks = chunk_text(
        source_id,
        cleaned,
        metadata={
            "source_type": "pasted_text",
            "title": title,
            "source_label": f"Geçici metin: {title}",
        },
        min_chars=40,
    )
    source = SessionSource(
        id=source_id,
        source_type="pasted_text",
        title=title,
        original_name_or_url=title,
        created_at=utc_now(),
        document_count=1,
        chunk_count=len(chunks),
        source_label=f"Geçici metin: {title}",
    )
    return source, chunks
