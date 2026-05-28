"""Dining menu dynamic source reader wrapper."""

from __future__ import annotations

from dynamic_menu_reader import (
    DINING_MENU_SOURCE_URL,
    fetch_dining_menu,
    get_dynamic_menu_health,
    is_dining_menu_query,
)

from dynamic_sources.base import DynamicSourceHealth, DynamicSourceResult


class DiningMenuReader:
    """Adapter for the existing dynamic dining menu reader functions."""

    reader_id = "dining_menu"
    mode = "dynamic_dining_menu"

    def is_query(self, query: str) -> bool:
        return is_dining_menu_query(query)

    def answer(self, query: str) -> DynamicSourceResult:
        data = fetch_dining_menu()
        return DynamicSourceResult.from_mapping(self.reader_id, data)

    def health(self) -> DynamicSourceHealth:
        data = get_dynamic_menu_health()
        if "source_url" not in data:
            data["source_url"] = DINING_MENU_SOURCE_URL
        return DynamicSourceHealth.from_mapping(self.reader_id, data)
