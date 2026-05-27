"""Small chat orchestration helpers for the Streamlit app.

This module intentionally avoids rendering Streamlit UI. It only prepares
answers/documents and updates chat-like message lists so app.py can keep the
layout code while delegating repetitive orchestration details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableSequence

from dynamic_menu_reader import (
    dining_menu_to_documents,
    fetch_dining_menu,
    format_dining_menu_response,
)
from rag_engine import (
    KnowledgeBaseUnavailableError,
    LIVE_INDEX_UNAVAILABLE_MESSAGE,
    is_chroma_collection_error,
)
from source_discovery import (
    build_source_discovery_answer,
    discover_sources,
    source_discovery_sources_to_documents,
)


@dataclass(frozen=True)
class ChatHandlerResult:
    """Prepared assistant response and source-panel documents."""

    answer: str
    docs: list[Any]
    sources_checked: bool = True


def append_assistant_message(
    messages: MutableSequence[dict[str, Any]],
    answer: str,
    question: str | None = None,
    docs: list[Any] | None = None,
    sources_checked: bool | None = None,
) -> dict[str, Any]:
    """Append an assistant message using the app.py message schema."""

    message: dict[str, Any] = {
        "rol": "assistant",
        "icerik": answer,
    }
    if question is not None:
        message["soru"] = question
    if docs is not None:
        message["docs"] = docs
    if sources_checked is not None:
        message["sources_checked"] = sources_checked
    messages.append(message)
    return message


def handle_source_discovery_chat(
    query: str,
    db: Any,
    discover_func: Callable[..., dict[str, Any]] = discover_sources,
) -> ChatHandlerResult:
    """Prepare a source discovery answer without invoking the LLM."""

    result = discover_func(query, db=db)
    docs = source_discovery_sources_to_documents(result.get("sources", []))
    answer = build_source_discovery_answer(result)
    return ChatHandlerResult(answer=answer, docs=docs, sources_checked=True)


def handle_dynamic_menu_chat(
    query: str,
    fetch_func: Callable[[], dict[str, Any]] = fetch_dining_menu,
) -> ChatHandlerResult:
    """Prepare a dynamic dining menu answer without touching static ChromaDB."""

    menu_data = fetch_func()
    docs = dining_menu_to_documents(menu_data)
    answer = format_dining_menu_response(menu_data, query)
    return ChatHandlerResult(answer=answer, docs=docs, sources_checked=True)


def build_safe_error_message(error: Exception, groq_key: str = "") -> tuple[str, str]:
    """Return the user-safe error message and sanitized technical detail."""

    error_text = str(error)
    safe_detail = error_text.replace(groq_key, "[GROQ_API_KEY]") if groq_key else error_text
    error_category = classify_error(error)

    if error_category == "knowledge_base":
        return LIVE_INDEX_UNAVAILABLE_MESSAGE, safe_detail
    if error_category == "rate_limit":
        return "⏳ API istek limiti aşıldı. Lütfen **30 saniye** bekleyip tekrar deneyin.", safe_detail
    if error_category == "authentication":
        return (
            "🔑 API anahtarı geçersiz veya eksik. Lütfen `.env` dosyasındaki "
            "**GROQ_API_KEY** değerini kontrol edin.",
            safe_detail,
        )
    if error_category == "connection":
        return "🌐 Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.", safe_detail
    if error_category == "model":
        return (
            "⚠️ Yapay zeka modeli çağrılırken hata oluştu. Streamlit Secrets içindeki "
            "**GROQ_API_KEY** değerini ve Groq hesabı erişimini kontrol edin.",
            safe_detail,
        )
    return "⚠️ Bir hata oluştu. Lütfen tekrar deneyin.", safe_detail


def classify_error(error: Exception) -> str:
    """Classify app errors for logging while keeping user messages centralized."""

    error_msg = str(error).lower()
    if isinstance(error, KnowledgeBaseUnavailableError) or is_chroma_collection_error(error):
        return "knowledge_base"
    if "rate_limit" in error_msg or "429" in error_msg or "rate limit" in error_msg:
        return "rate_limit"
    if (
        "authentication" in error_msg
        or "invalid_api_key" in error_msg
        or "unauthorized" in error_msg
        or "api_key" in error_msg
        or "401" in error_msg
    ):
        return "authentication"
    if "connection" in error_msg or "timeout" in error_msg or "unreachable" in error_msg:
        return "connection"
    if "groq" in error_msg or "chatgroq" in error_msg or "model" in error_msg:
        return "model"
    return "generic"
