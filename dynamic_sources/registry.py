"""Registry for dynamic source readers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dynamic_sources.base import DynamicSourceReader
from dynamic_sources.dining_menu import DiningMenuReader


@dataclass(frozen=True)
class DynamicSourceRoute:
    """Dynamic source routing result."""

    mode: str
    reader_id: str
    reader: DynamicSourceReader
    reason: str
    metadata: dict[str, Any]


def get_dynamic_source_readers() -> list[DynamicSourceReader]:
    """Return registered dynamic source readers in routing order."""

    return [DiningMenuReader()]


def route_dynamic_source(query: str) -> DynamicSourceRoute | None:
    """Route a query to the first matching dynamic source reader."""

    text = str(query or "").strip()
    if not text:
        return None

    for priority, reader in enumerate(get_dynamic_source_readers(), start=1):
        if reader.is_query(text):
            return DynamicSourceRoute(
                mode=reader.mode,
                reader_id=reader.reader_id,
                reader=reader,
                reason="dynamic_source_intent",
                metadata={"priority": priority},
            )
    return None


def get_dynamic_source_health_summary() -> dict[str, Any]:
    """Return a secret-safe health summary for all registered readers."""

    readers = get_dynamic_source_readers()
    items = [reader.health().to_dict() for reader in readers]
    return {
        "total_readers": len(readers),
        "reader_ids": [reader.reader_id for reader in readers],
        "readers": items,
    }
