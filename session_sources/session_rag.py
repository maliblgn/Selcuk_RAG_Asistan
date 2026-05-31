"""Answer questions using only the active session source."""

from __future__ import annotations

from .models import SessionRAGResult
from .vector_store import InMemorySessionVectorStore


NO_ACTIVE_SOURCE_MESSAGE = "Aktif geçici kaynak yok. Önce PDF yükleyebilir veya link ekleyebilirsin."
NO_CONTEXT_MESSAGE = (
    "Yüklediğin geçici kaynakta bu soruya açık bir cevap bulamadım. "
    "Bilgi uydurmuyorum. Genel Selçuk kaynaklarında aramamı istersen normal RAG modunda sorabilirsin."
)


def _citation_for_doc(doc) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    if metadata.get("source_type") == "pdf":
        page = metadata.get("page_number")
        return f"[PDF, sayfa {page}]" if page else "[PDF]"
    if metadata.get("source_type") == "url":
        index = int(metadata.get("chunk_index") or 0) + 1
        return f"[Web kaynak, bölüm {index}]"
    return "[Geçici kaynak]"


def answer_from_session_source(query: str, store: InMemorySessionVectorStore | None, top_k: int = 4) -> SessionRAGResult:
    if store is None:
        return SessionRAGResult(
            status="no_active_source",
            answer=NO_ACTIVE_SOURCE_MESSAGE,
            citations=[],
            diagnostic_message="no_active_source",
        )
    scored = store.search(query, top_k=top_k)
    if not scored:
        return SessionRAGResult(
            status="no_relevant_context",
            answer=NO_CONTEXT_MESSAGE,
            citations=[],
            source_summary=store.source.to_dict(),
            diagnostic_message="no_relevant_context",
        )
    docs = store.to_documents(scored)
    citations = []
    lines = ["Yüklediğin geçici kaynaktan bulduğum ilgili bilgi:"]
    for doc in docs[:2]:
        citation = _citation_for_doc(doc)
        citations.append(citation)
        snippet = " ".join(doc.page_content.split())[:700]
        lines.extend(["", f"{snippet} {citation}"])
    lines.extend(["", "Bu cevap yalnızca aktif geçici kaynak üzerinden hazırlanmıştır."])
    return SessionRAGResult(
        status="answered",
        answer="\n".join(lines).strip(),
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
