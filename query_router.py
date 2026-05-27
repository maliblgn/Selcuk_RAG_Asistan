"""Central query routing for answer modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dynamic_menu_reader import is_dining_menu_query
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

    if is_dining_menu_query(text):
        return QueryRoute(
            mode=MODE_DYNAMIC_DINING_MENU,
            reason="dynamic_dining_menu_intent",
            metadata={"priority": 2},
        )

    return QueryRoute(
        mode=MODE_RAG,
        reason="default_rag",
        metadata={"priority": 3},
    )
