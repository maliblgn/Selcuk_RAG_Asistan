"""Data models for session-only uploaded sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SessionSource:
    id: str
    source_type: str
    title: str
    original_name_or_url: str
    created_at: str
    document_count: int
    chunk_count: int
    status: str = "ready"
    error_message: str = ""
    source_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionChunk:
    chunk_id: str
    source_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionRAGResult:
    status: str
    answer: str
    citations: list[str]
    source_summary: dict[str, Any] | None = None
    diagnostic_message: str = ""
    docs: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["docs"] = []
        return data

