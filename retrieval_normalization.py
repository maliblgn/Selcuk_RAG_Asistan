"""Shared normalization and alias helpers for retrieval matching."""

from __future__ import annotations

import json
import re
import string
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote


DEFAULT_ALIAS_PATH = Path(__file__).resolve().parent / "config" / "retrieval_aliases.json"
_PUNCT_TRANSLATION = str.maketrans({char: " " for char in string.punctuation})
_TURKISH_ASCII = str.maketrans({
    "ç": "c",
    "ğ": "g",
    "ı": "i",
    "İ": "i",
    "ö": "o",
    "ş": "s",
    "ü": "u",
    "Ç": "c",
    "Ğ": "g",
    "I": "i",
    "Ö": "o",
    "Ş": "s",
    "Ü": "u",
})
_MOJIBAKE_REPLACEMENTS = {
    "Ä°": "i",
    "Ä±": "i",
    "Ä": "g",
    "ÄŸ": "g",
    "Ãœ": "u",
    "Ã¼": "u",
    "Å": "s",
    "ÅŸ": "s",
    "Ã–": "o",
    "Ã¶": "o",
    "Ã‡": "c",
    "Ã§": "c",
    "Ã„Â°": "i",
    "Ã„Â±": "i",
    "Ã„Â": "g",
    "Ã„Å¸": "g",
    "ÃƒÅ“": "u",
    "ÃƒÂ¼": "u",
    "Ã…Â": "s",
    "Ã…Å¸": "s",
    "Ãƒâ€“": "o",
    "ÃƒÂ¶": "o",
    "Ãƒâ€¡": "c",
    "ÃƒÂ§": "c",
}


def normalize_text(text: str) -> str:
    """Return a stable lowercase representation for Turkish retrieval matching."""

    value = unquote(str(text or "")).strip()
    for old, new in _MOJIBAKE_REPLACEMENTS.items():
        value = value.replace(old, new)
    value = value.translate(_TURKISH_ASCII)
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.translate(_PUNCT_TRANSLATION)
    return " ".join(value.split())


def normalize_ascii_lite(text: str) -> str:
    """Normalize text for loose ASCII-only comparisons."""

    value = normalize_text(text)
    value = unicodedata.normalize("NFKD", value)
    return "".join(char for char in value if char.isascii())


def tokenize_for_match(text: str) -> set[str]:
    """Tokenize normalized text and remove very short tokens."""

    return {token for token in re.findall(r"[a-z0-9]+", normalize_ascii_lite(text)) if len(token) >= 3}


@lru_cache(maxsize=8)
def load_retrieval_aliases(path: str | Path = DEFAULT_ALIAS_PATH) -> dict:
    """Load retrieval aliases; missing files safely return an empty config."""

    alias_path = Path(path)
    if not alias_path.exists():
        return {"term_aliases": {}, "document_aliases": {}}
    with alias_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        "term_aliases": data.get("term_aliases") or {},
        "document_aliases": data.get("document_aliases") or {},
    }


def _normalized_alias_entries(aliases: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    entries = []
    for key, values in aliases.items():
        forms = [normalize_ascii_lite(key)]
        forms.extend(normalize_ascii_lite(value) for value in values or [])
        entries.append((normalize_ascii_lite(key), [form for form in forms if form]))
    return entries


def expand_query_alias_text(query: str, aliases: dict | None = None) -> str:
    """Append matched term aliases to a query-like text for scoring only."""

    alias_config = aliases or load_retrieval_aliases()
    query_norm = normalize_ascii_lite(query)
    additions: list[str] = []
    for canonical, forms in _normalized_alias_entries(alias_config.get("term_aliases") or {}):
        if any(form and form in query_norm for form in forms):
            additions.append(canonical)
            additions.extend(forms)
    if not additions:
        return normalize_text(query)
    return " ".join([normalize_text(query), *additions])


def title_similarity_score(query: str, title: str, aliases: list[str] | None = None) -> float:
    """Score loose query-title similarity using tokens, phrases, and aliases."""

    query_norm = normalize_ascii_lite(query)
    title_norm = normalize_ascii_lite(title)
    if not query_norm or not title_norm:
        return 0.0

    query_tokens = tokenize_for_match(query_norm)
    title_tokens = tokenize_for_match(title_norm)
    if not query_tokens or not title_tokens:
        return 0.0

    score = 0.0
    overlap = query_tokens & title_tokens
    if overlap:
        score += min(3.0, len(overlap) / max(len(query_tokens), 1) * 4.0)
        if len(overlap) >= 2:
            score += 1.0

    if query_norm in title_norm or title_norm in query_norm:
        score += 3.0

    for alias in aliases or []:
        alias_norm = normalize_ascii_lite(alias)
        if not alias_norm:
            continue
        alias_tokens = tokenize_for_match(alias_norm)
        if alias_norm in title_norm or alias_norm in query_norm:
            score += 2.5
        elif alias_tokens and alias_tokens.issubset(title_tokens | query_tokens):
            score += 1.5
    return min(score, 8.0)


def document_alias_score(query: str, title: str, aliases: dict | None = None) -> float:
    """Score query/title against configured document-family aliases."""

    alias_config = aliases or load_retrieval_aliases()
    query_norm = normalize_ascii_lite(query)
    title_norm = normalize_ascii_lite(title)
    best = 0.0
    for canonical, forms in _normalized_alias_entries(alias_config.get("document_aliases") or {}):
        query_matches = any(form and form in query_norm for form in forms)
        title_matches = any(form and form in title_norm for form in forms)
        if query_matches and title_matches:
            best = max(best, 5.0)
        elif canonical and canonical in title_norm and any(token in query_norm for token in canonical.split()):
            best = max(best, 2.0)
    return best


def article_match_score(expected_or_query: str, article_no: str, article_title: str, content: str) -> float:
    """Score article number/title/content match for evaluation and rerank hints."""

    expected_norm = normalize_ascii_lite(expected_or_query)
    title_norm = normalize_ascii_lite(article_title)
    content_norm = normalize_ascii_lite(content)
    article_no_norm = normalize_ascii_lite(article_no)
    if not expected_norm:
        return 0.0

    score = 0.0
    if article_no_norm and re.search(rf"\b{re.escape(article_no_norm)}\b", expected_norm):
        score += 4.0
    if title_norm:
        if expected_norm in title_norm or title_norm in expected_norm:
            score += 5.0
        overlap = tokenize_for_match(expected_norm) & tokenize_for_match(title_norm)
        if overlap:
            score += min(3.0, len(overlap) * 1.25)
    if expected_norm in content_norm:
        score += 2.0
    return min(score, 10.0)
