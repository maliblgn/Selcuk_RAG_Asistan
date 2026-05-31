"""Manual URL loader for session-only sources."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .chunker import chunk_text, clean_text
from .models import SessionSource, utc_now
from .pdf_loader import build_pdf_session_source
from .safety import robots_allowed, validate_final_url, validate_url_safety


MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = "SelcukRAGSessionSource/1.0"


@dataclass(frozen=True)
class URLLoadResult:
    source: SessionSource
    chunks: list
    final_url: str = ""
    status_code: int | None = None


def extract_html_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    title = clean_text(soup.title.get_text(" ")) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside", "header"]):
        tag.decompose()
    pieces = []
    for node in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
        text = clean_text(node.get_text(" "))
        if len(text) >= 20:
            pieces.append(text)
    if not pieces:
        text = clean_text(soup.get_text(" "))
    else:
        text = "\n".join(pieces)
    return title, text


def _error_source(url: str, message: str, status_code: int | None = None) -> URLLoadResult:
    source_id = "session_url_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    source = SessionSource(
        id=source_id,
        source_type="url",
        title=url,
        original_name_or_url=url,
        created_at=utc_now(),
        document_count=0,
        chunk_count=0,
        status="error",
        error_message=message,
        source_label=f"URL: {url}",
    )
    return URLLoadResult(source=source, chunks=[], final_url=url, status_code=status_code)


def load_url_source(url: str, timeout_sec: int = 12) -> URLLoadResult:
    safety = validate_url_safety(url)
    if not safety.ok:
        return _error_source(url, safety.reason)
    robots = robots_allowed(url)
    if not robots.ok:
        return _error_source(url, "Bu site otomatik erişime izin vermiyor veya robots.txt tarafından engelleniyor.")

    try:
        response = requests.get(
            url,
            timeout=timeout_sec,
            allow_redirects=True,
            stream=True,
            headers={"User-Agent": USER_AGENT},
        )
        final = validate_final_url(response.url)
        if not final.ok:
            return _error_source(url, final.reason, response.status_code)
        if response.status_code in {401, 403, 429}:
            return _error_source(url, "Bu sayfaya erişilemedi; site otomatik kazımaya izin vermiyor olabilir.", response.status_code)
        response.raise_for_status()
        content = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
    except Exception:
        return _error_source(url, "Bu sayfaya erişilemedi; site otomatik kazımaya izin vermiyor olabilir.")

    if len(content) > MAX_RESPONSE_BYTES:
        return _error_source(url, "Sayfa boyutu güvenli sınırı aştığı için işlenmedi.", response.status_code)

    content_type = response.headers.get("content-type", "").lower()
    is_pdf = "pdf" in content_type or response.url.lower().split("?", 1)[0].endswith(".pdf") or content.startswith(b"%PDF")
    if is_pdf:
        filename = Path(urlparse(response.url).path).name or "linked.pdf"
        source, chunks = build_pdf_session_source(content, filename=filename)
        source = replace(
            source,
            source_type="pdf_url",
            original_name_or_url=response.url,
            source_label=f"URL PDF: {source.title}",
        )
        chunks = [
            replace(chunk, metadata={**chunk.metadata, "source_type": "pdf_url", "url": response.url, "source_label": source.source_label})
            for chunk in chunks
        ]
        return URLLoadResult(source=source, chunks=chunks, final_url=response.url, status_code=response.status_code)

    text = content.decode(response.encoding or "utf-8", errors="ignore")
    if "html" in content_type or text.lstrip().startswith("<"):
        title, extracted = extract_html_text(text)
    elif "text/plain" in content_type:
        title, extracted = urlparse(response.url).netloc, clean_text(text)
    else:
        return _error_source(url, "Bu link desteklenen text/html, text/plain veya PDF içerik döndürmedi.", response.status_code)

    if len(extracted) < 120:
        return _error_source(url, "Bu sayfa JavaScript ile içerik üretiyor olabilir; okunabilir metin çıkarılamadı.", response.status_code)

    source_id = "session_url_" + hashlib.sha256(response.url.encode("utf-8")).hexdigest()[:12]
    title = title or response.url
    chunks = chunk_text(source_id, extracted, metadata={
        "source_type": "url",
        "url": response.url,
        "title": title,
        "source_label": f"Web kaynak: {title}",
    })
    source = SessionSource(
        id=source_id,
        source_type="url",
        title=title,
        original_name_or_url=url,
        created_at=utc_now(),
        document_count=1,
        chunk_count=len(chunks),
        source_label=f"Web kaynak: {title}",
    )
    return URLLoadResult(source=source, chunks=chunks, final_url=response.url, status_code=response.status_code)
