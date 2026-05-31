"""PDF loader for session-only sources."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import BinaryIO

from pypdf import PdfReader

from .chunker import chunk_page_texts
from .models import SessionSource, utc_now
from .text_quality import choose_best_page_text, clean_extracted_text


def _read_bytes(pdf_file: bytes | BinaryIO) -> bytes:
    if isinstance(pdf_file, bytes):
        return pdf_file
    if hasattr(pdf_file, "getvalue"):
        return pdf_file.getvalue()
    return pdf_file.read()


def _extract_with_pypdf(data: bytes) -> list[str]:
    reader = PdfReader(BytesIO(data))
    return [(page.extract_text() or "") for page in reader.pages]


def _extract_with_pypdf2(data: bytes) -> list[str]:
    try:
        from PyPDF2 import PdfReader as PyPDF2Reader  # type: ignore
    except Exception:
        return []
    try:
        reader = PyPDF2Reader(BytesIO(data))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception:
        return []


def _extract_with_pdfplumber(data: bytes) -> list[str]:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return []
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            return [(page.extract_text() or "") for page in pdf.pages]
    except Exception:
        return []


def load_pdf_pages(pdf_file: bytes | BinaryIO) -> list[dict]:
    data = _read_bytes(pdf_file)
    candidate_sets = [_extract_with_pypdf(data), _extract_with_pypdf2(data), _extract_with_pdfplumber(data)]
    max_pages = max((len(items) for items in candidate_sets), default=0)
    pages = []
    for index in range(max_pages):
        candidates = [items[index] for items in candidate_sets if index < len(items)]
        text = choose_best_page_text(candidates)
        if text:
            pages.append({"page_number": index + 1, "text": clean_extracted_text(text)})
    return pages


def build_pdf_session_source(pdf_file: bytes | BinaryIO, filename: str = "uploaded.pdf") -> tuple[SessionSource, list]:
    data = _read_bytes(pdf_file)
    source_id = "session_pdf_" + hashlib.sha256(data[:1024] + filename.encode("utf-8")).hexdigest()[:12]
    pages = load_pdf_pages(data)
    if not pages:
        source = SessionSource(
            id=source_id,
            source_type="pdf",
            title=filename,
            original_name_or_url=filename,
            created_at=utc_now(),
            document_count=0,
            chunk_count=0,
            status="error",
            error_message="Bu PDF'den okunabilir metin çıkarılamadı. Taranmış/görsel PDF olabilir.",
            source_label=f"PDF: {filename}",
        )
        return source, []
    chunks = chunk_page_texts(source_id, pages, {
        "source_type": "pdf",
        "title": filename,
        "source_label": f"PDF: {filename}",
    })
    source = SessionSource(
        id=source_id,
        source_type="pdf",
        title=filename,
        original_name_or_url=filename,
        created_at=utc_now(),
        document_count=len(pages),
        chunk_count=len(chunks),
        source_label=f"PDF: {filename}",
    )
    return source, chunks
