"""Central query routing for answer modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dynamic_sources.registry import route_dynamic_source
from source_discovery import is_source_discovery_query


MODE_SOURCE_DISCOVERY = "source_discovery"
MODE_DYNAMIC_DINING_MENU = "dynamic_dining_menu"
MODE_RAG = "rag"


@dataclass(frozen=True)
class QueryRoute:
    """Route descriptor for the next answer mode."""

    mode: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


def route_query(query: str) -> QueryRoute:
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

    return QueryRoute(
        mode=MODE_RAG,
        reason="default_rag",
        metadata={"priority": 3},
    )
