"""Text cleanup and quality helpers for session-only PDF extraction."""

from __future__ import annotations

import re
import unicodedata


MOJIBAKE_REPLACEMENTS = {
    "Ã§": "ç",
    "Ã‡": "Ç",
    "Ã¶": "ö",
    "Ã–": "Ö",
    "Ã¼": "ü",
    "Ãœ": "Ü",
    "Ä±": "ı",
    "Ä°": "İ",
    "ÄŸ": "ğ",
    "Äž": "Ğ",
    "ÅŸ": "ş",
    "Åž": "Ş",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "ï¿½": "�",
}

BROKEN_TURKISH_PATTERNS = {
    "U�niversitesi": "Üniversitesi",
    "U�NIVERSITESI": "ÜNİVERSİTESİ",
    "O�ğ": "Öğ",
    "O�ğ": "Öğ",
    "O�g": "Öğ",
    "I�ngilizce": "İngilizce",
    "I�": "İ",
    "S�": "Ş",
    "s�": "ş",
    "G�": "Ğ",
    "g�": "ğ",
    "C�": "Ç",
    "c�": "ç",
}


def clean_extracted_text(text: str) -> str:
    """Normalize common PDF extraction artifacts without guessing missing content."""

    cleaned = unicodedata.normalize("NFKC", str(text or ""))
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = unicodedata.normalize("NFC", cleaned)
    for bad, good in BROKEN_TURKISH_PATTERNS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def score_extracted_text_quality(text: str) -> float:
    """Score readable text higher and replacement/control-heavy text lower."""

    value = clean_extracted_text(text)
    if not value:
        return 0.0
    length = len(value)
    replacement_penalty = value.count("�") * 8.0
    control_penalty = sum(1 for char in value if unicodedata.category(char).startswith("C") and char not in "\n\t") * 3.0
    alpha_count = sum(1 for char in value if char.isalpha())
    whitespace_count = sum(1 for char in value if char.isspace())
    readable_ratio = alpha_count / max(length, 1)
    whitespace_ratio = whitespace_count / max(length, 1)
    length_bonus = min(length / 400.0, 2.0)
    return (readable_ratio * 10.0) + length_bonus - (replacement_penalty / max(length, 1)) - abs(whitespace_ratio - 0.16)


def choose_best_page_text(candidates: list[str]) -> str:
    cleaned = [clean_extracted_text(candidate) for candidate in candidates if str(candidate or "").strip()]
    if not cleaned:
        return ""
    return max(cleaned, key=score_extracted_text_quality)
