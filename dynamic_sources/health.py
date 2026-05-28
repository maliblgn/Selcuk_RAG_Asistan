"""Health helpers for dynamic source readers."""

from __future__ import annotations

from typing import Any

from dynamic_sources.registry import get_dynamic_source_health_summary

SENSITIVE_KEY_PARTS = ("key", "token", "secret", "password", "authorization")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def get_safe_dynamic_source_health_summary() -> dict[str, Any]:
    """Return dynamic source health without secret-like fields."""

    return _sanitize(get_dynamic_source_health_summary())
