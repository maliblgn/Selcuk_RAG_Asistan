"""Answer questions using only the active session source."""

from __future__ import annotations

import re

from .extractors import (
    detect_query_intent,
    extract_dates,
    extract_email,
    extract_gpa,
    extract_heading_candidates,
    extract_language_levels,
    extract_phone,
    extract_project_titles,
    extract_requirement_items,
    extract_section_items,
    extract_urls,
)
from .models import SessionRAGResult
from .vector_store import InMemorySessionVectorStore


NO_ACTIVE_SOURCE_MESSAGE = "Aktif geçici kaynak yok. Önce PDF yükleyebilir veya link ekleyebilirsin."
NO_CONTEXT_MESSAGE = (
    "Yüklediğin geçici kaynakta bu soruya açık bir cevap bulamadım. "
    "Bilgi uydurmuyorum. Genel Selçuk kaynaklarında aramamı istersen normal RAG modunda sorabilirsin."
)
META_HELP_MESSAGE = (
    "PDF/link yükleme alanı geçici kaynak eklemek için kullanılır. Yüklenen kaynak işlendiğinde "
    "sidebar'daki aktif kaynak bilgisinde görünür; bu içerik ana Selçuk veritabanına eklenmez."
)


def is_session_meta_query(query: str) -> bool:
    normalized = str(query or "").casefold()
    return any(term in normalized for term in (
        "pdf yükle", "pdf yukle", "link yükle", "link yukle", "yükleme çalışıyor", "yukleme calisiyor",
        "bu özellik ne işe", "bu ozellik ne ise", "sistem çalışıyor", "sistem calisiyor",
    ))


def _citation_for_doc(doc) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    section = metadata.get("section_title")
    if metadata.get("source_type") == "pdf":
        page = metadata.get("page_number")
        base = f"PDF, sayfa {page}" if page else "PDF"
    elif metadata.get("source_type") == "pdf_url":
        page = metadata.get("page_number")
        base = f"PDF URL, sayfa {page}" if page else "PDF URL"
    elif metadata.get("source_type") == "pasted_text":
        base = "Geçici metin"
    elif metadata.get("source_type") == "url":
        base = "Web"
    else:
        base = "Geçici kaynak"
    if section:
        base = f"{base}, {section}"
    return f"[{base}]"


def _context_text(docs) -> str:
    return "\n".join(doc.page_content for doc in docs)


def _docs_for_section(docs, section_types: set[str]):
    filtered = [doc for doc in docs if (getattr(doc, "metadata", {}) or {}).get("section_type") in section_types]
    return filtered or docs


def _source_noun(store: InMemorySessionVectorStore) -> str:
    if store.source.source_type == "pdf":
        return "PDF"
    if store.source.source_type == "pdf_url":
        return "PDF linki"
    if store.source.source_type == "pasted_text":
        return "geçici metin"
    return "kaynak"


def _fallback(store: InMemorySessionVectorStore | None = None) -> SessionRAGResult:
    return SessionRAGResult(
        status="no_relevant_context",
        answer=NO_CONTEXT_MESSAGE,
        citations=[],
        source_summary=store.source.to_dict() if store else None,
        diagnostic_message="no_relevant_context",
    )


def _answer_single(label: str, values: list[str], citation: str, store: InMemorySessionVectorStore) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return f"Yüklediğin {_source_noun(store)}'e göre {label}: {values[0]}. {citation}"
    joined = ", ".join(values)
    return f"Yüklediğin {_source_noun(store)}'e göre {label}: {joined}. {citation}"


def _format_list_answer(prefix: str, items: list[str], citation: str) -> str:
    if not items:
        return ""
    bullets = "\n".join(f"- {item}" for item in items[:12])
    return f"{prefix}\n\n{bullets}\n\n{citation}"


def _first_sentences(text: str, limit: int = 3) -> list[str]:
    cleaned = " ".join(str(text or "").split())
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20][:limit]


def _deterministic_answer(intent_name: str, query: str, docs, store: InMemorySessionVectorStore) -> str:
    section_map = {
        "email": {"contact"},
        "phone": {"contact"},
        "url": {"contact"},
        "language": {"languages"},
        "gpa": {"education"},
        "projects": {"projects"},
        "skills": {"skills"},
        "requirements": {"requirements", "article"},
        "summary": {"summary"},
    }
    answer_docs = _docs_for_section(docs, section_map.get(intent_name, set()))
    text = _context_text(answer_docs)
    citation = _citation_for_doc(answer_docs[0]) if answer_docs else "[Geçici kaynak]"

    if intent_name == "email":
        return _answer_single("e-posta adresi", extract_email(text), citation, store)
    if intent_name == "phone":
        return _answer_single("telefon numarası", extract_phone(text), citation, store)
    if intent_name == "url":
        return _answer_single("ilgili link", extract_urls(text), citation, store)
    if intent_name == "language":
        levels = [f"{language}: {level}" for language, level in extract_language_levels(text)]
        return _format_list_answer(f"Yüklediğin {_source_noun(store)}'e göre dil bilgileri:", levels, citation)
    if intent_name == "gpa":
        return _answer_single("not ortalaması/GPA", extract_gpa(text), citation, store)
    if intent_name == "date":
        return _answer_single("ilgili tarih", extract_dates(text), citation, store)
    if intent_name == "projects":
        items = extract_project_titles(text)
        return _format_list_answer(f"Yüklediğin {_source_noun(store)}'e göre projeler şunlar:", items, citation)
    if intent_name == "skills":
        items = extract_section_items(text, "skills")
        return _format_list_answer(f"Yüklediğin {_source_noun(store)}'e göre beceriler şunlar:", items, citation)
    if intent_name == "requirements":
        items = extract_requirement_items(text)
        return _format_list_answer(f"Yüklediğin {_source_noun(store)}'e göre şartlar/gerekli maddeler:", items, citation)
    if intent_name == "headings":
        items = extract_heading_candidates(store.chunks)
        return _format_list_answer(f"Yüklediğin {_source_noun(store)} içindeki başlıklar:", items, citation)
    if intent_name == "summary":
        if not text.strip():
            text = _context_text(docs[:2])
            citation = _citation_for_doc(docs[0]) if docs else citation
        sentences = _first_sentences(text, limit=3)
        if sentences:
            return f"Yüklediğin {_source_noun(store)} genel olarak şunu anlatıyor: {' '.join(sentences)} {citation}"
    return ""


def _synthesize_general_answer(query: str, docs, store: InMemorySessionVectorStore) -> str:
    if not docs:
        return ""
    citation = _citation_for_doc(docs[0])
    sentences = _first_sentences(_context_text(docs), limit=2)
    if not sentences:
        return ""
    return (
        f"Yüklediğin {_source_noun(store)} içinde soruyla en ilgili bilgi şu: "
        f"{' '.join(sentences)} {citation}"
    )


def answer_from_session_source(query: str, store: InMemorySessionVectorStore | None, top_k: int = 4) -> SessionRAGResult:
    if is_session_meta_query(query):
        return SessionRAGResult(
            status="meta_answer",
            answer=META_HELP_MESSAGE,
            citations=[],
            source_summary=store.source.to_dict() if store else None,
            diagnostic_message="session_meta_query",
        )
    if store is None:
        return SessionRAGResult(
            status="no_active_source",
            answer=NO_ACTIVE_SOURCE_MESSAGE,
            citations=[],
            diagnostic_message="no_active_source",
        )
    intent = detect_query_intent(query)
    scored = store.search(query, top_k=2 if intent.name in {"email", "phone", "language", "gpa", "date"} else top_k)
    if not scored and intent.wants_summary and store.chunks:
        scored = [(chunk, 0.5) for chunk in store.chunks[: min(2, len(store.chunks))]]
    if not scored:
        return _fallback(store)
    docs = store.to_documents(scored)

    answer = _deterministic_answer(intent.name, query, docs, store) or _synthesize_general_answer(query, docs, store)
    if not answer:
        return _fallback(store)
    answer = f"{answer}\n\nBu cevap yalnızca aktif geçici kaynak üzerinden hazırlanmıştır."
    citations = [_citation_for_doc(doc) for doc in docs]
    return SessionRAGResult(
        status="answered",
        answer=answer,
        citations=citations,
        source_summary=store.source.to_dict(),
        docs=docs,
    )


def session_source_status_text(source) -> str:
    if not source:
        return "Aktif geçici kaynak yok."
    return (
        f"Aktif geçici kaynak: {source.source_label or source.title} "
        f"({source.chunk_count} chunk). Bu kaynak ana Selçuk veritabanına eklenmez."
    )
