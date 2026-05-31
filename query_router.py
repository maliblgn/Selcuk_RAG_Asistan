"""Central query routing for answer modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dynamic_sources.registry import route_dynamic_source
from source_discovery import is_source_discovery_query


MODE_SOURCE_DISCOVERY = "source_discovery"
MODE_DYNAMIC_DINING_MENU = "dynamic_dining_menu"
MODE_SESSION_UPLOAD_RAG = "session_upload_rag"
MODE_RAG = "rag"


@dataclass(frozen=True)
class QueryRoute:
    """Route descriptor for the next answer mode."""

    mode: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _explicit_general_rag_request(query: str) -> bool:
    normalized = str(query or "").casefold()
    return any(
        term in normalized
        for term in (
            "genel selçuk kaynak",
            "genel selcuk kaynak",
            "selçuk kaynaklarında ara",
            "selcuk kaynaklarinda ara",
            "ana kaynaklarda ara",
            "normal rag",
        )
    )


def route_query(
    query: str,
    has_active_session_source: bool = False,
    session_source_enabled: bool = True,
) -> QueryRoute:
    """Route a query using the existing intent detectors and current priority order."""

    text = str(query or "").strip()
    if not text:
        return QueryRoute(
            mode=MODE_RAG,
            reason="empty_query_default",
            metadata={"query_empty": True},
        )

    if is_source_discovery_query(text):
        return QueryRoute(
            mode=MODE_SOURCE_DISCOVERY,
            reason="source_discovery_intent",
            metadata={"priority": 1},
        )

    dynamic_route = route_dynamic_source(text)
    if dynamic_route:
        return QueryRoute(
            mode=dynamic_route.mode,
            reason=dynamic_route.reason,
            metadata={"priority": 2, "reader_id": dynamic_route.reader_id},
        )

    if has_active_session_source and session_source_enabled and not _explicit_general_rag_request(text):
        return QueryRoute(
            mode=MODE_SESSION_UPLOAD_RAG,
            reason="active_session_source",
            metadata={"priority": 3},
        )

    return QueryRoute(
        mode=MODE_RAG,
        reason="default_rag",
        metadata={"priority": 4 if has_active_session_source else 3},
    )
