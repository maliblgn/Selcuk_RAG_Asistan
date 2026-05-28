"""Shared interface objects for dynamic source readers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class DynamicSourceResult:
    """Normalized result returned by a dynamic source reader."""

    source_id: str
    mode: str
    status: str
    source_url: str = ""
    fetched_at: str = ""
    items: list[Any] = field(default_factory=list)
    message: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, source_id: str, data: dict[str, Any]) -> "DynamicSourceResult":
        return cls(
            source_id=source_id,
            mode=str(data.get("mode") or ""),
            status=str(data.get("status") or "unavailable"),
            source_url=str(data.get("source_url") or ""),
            fetched_at=str(data.get("fetched_at") or ""),
            items=list(data.get("items") or []),
            message=str(data.get("message") or ""),
            diagnostics=dict(data.get("diagnostics") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DynamicSourceHealth:
    """Static health/configuration summary for a dynamic source reader."""

    source_id: str
    mode: str
    status: str = "configured"
    source_url: str = ""
    secret_required: bool = False
    live_fetch_required: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, source_id: str, data: dict[str, Any]) -> "DynamicSourceHealth":
        return cls(
            source_id=source_id,
            mode=str(data.get("mode") or ""),
            status=str(data.get("status") or "configured"),
            source_url=str(data.get("source_url") or ""),
            secret_required=bool(data.get("secret_required")),
            live_fetch_required=bool(data.get("live_fetch_required")),
            diagnostics={
                key: value
                for key, value in dict(data).items()
                if key not in {"mode", "status", "source_url", "secret_required", "live_fetch_required"}
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DynamicSourceReader(Protocol):
    """Protocol implemented by dynamic source readers."""

    reader_id: str
    mode: str

    def is_query(self, query: str) -> bool:
        """Return True when this reader should handle the query."""

    def answer(self, query: str) -> DynamicSourceResult:
        """Return a normalized dynamic source answer result."""

    def health(self) -> DynamicSourceHealth:
        """Return a non-live health/configuration summary."""
