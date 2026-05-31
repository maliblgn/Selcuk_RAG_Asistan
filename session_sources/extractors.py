"""Targeted extractors and intent helpers for session-only answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from retrieval_normalization import normalize_ascii_lite


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"https?://[^\s)>\]]+|(?:github|linkedin)\.com/[^\s)>\]]+", re.IGNORECASE)
GPA_RE = re.compile(r"\b(?:gpa|agno|gano|not ortalamas[ıi])\s*[:=-]?\s*([0-4](?:[.,]\d{1,2})?)\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b\d{1,2}\s+(?:ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)\s+\d{4}\b", re.IGNORECASE)

LANGUAGE_LEVEL_RE = re.compile(
    r"\b(Türkçe|Turkce|İngilizce|Ingilizce|Almanca|Fransızca|Arapça|İspanyolca|Rusça)\b"
    r"(?:\s*[:=-]\s*|\s+)(A1|A2|B1|B2|C1|C2|başlangıç|orta|ileri|native|ana dil|akıcı)\b",
    re.IGNORECASE,
)


SECTION_KEYWORDS = {
    "contact": ["iletişim", "iletisim", "contact", "e-posta", "email", "mail", "telefon"],
    "summary": ["özet", "ozet", "profil", "hakkında", "hakkinda", "amaç", "amac"],
    "education": ["eğitim", "egitim", "üniversite", "universite", "okul", "gpa", "agno", "gano"],
    "projects": ["proje", "projeler", "çalışmalar", "calismalar"],
    "skills": ["beceri", "beceriler", "yetenek", "teknoloji", "teknolojiler", "programlama"],
    "languages": ["dil", "diller", "ingilizce", "yabancı dil", "yabanci dil"],
    "requirements": ["şart", "sart", "koşul", "kosul", "gerekli belge", "başvuru", "basvuru"],
    "article": ["madde", "tanımlar", "tanimlar", "kapsam"],
}

SECTION_TITLES = {
    "iletişim": "contact",
    "iletisim": "contact",
    "contact": "contact",
    "özet": "summary",
    "ozet": "summary",
    "profil": "summary",
    "eğitim": "education",
    "egitim": "education",
    "eğitim ve nitelikler": "education",
    "egitim ve nitelikler": "education",
    "projeler": "projects",
    "proje": "projects",
    "deneyim": "experience",
    "beceriler": "skills",
    "teknik beceriler": "skills",
    "diller": "languages",
    "yabancı diller": "languages",
    "yabanci diller": "languages",
    "sertifikalar": "certificates",
    "başvuru": "requirements",
    "basvuru": "requirements",
    "başvuru şartları": "requirements",
    "basvuru sartlari": "requirements",
    "şartlar": "requirements",
    "sartlar": "requirements",
    "gerekli belgeler": "requirements",
    "madde": "article",
    "amaç": "article",
    "amac": "article",
    "kapsam": "article",
    "tanımlar": "article",
    "tanimlar": "article",
}


@dataclass(frozen=True)
class SessionQueryIntent:
    name: str
    wants_list: bool = False
    wants_summary: bool = False


def normalize(text: str) -> str:
    return normalize_ascii_lite(text)


def detect_query_intent(query: str) -> SessionQueryIntent:
    normalized = normalize(query)
    if any(term in normalized for term in ["mail", "email", "e posta", "eposta"]):
        return SessionQueryIntent("email")
    if any(term in normalized for term in ["telefon", "numara", "phone"]):
        return SessionQueryIntent("phone")
    if any(term in normalized for term in ["linkedin", "github", "web sitesi", "url", "link"]):
        return SessionQueryIntent("url")
    if any(term in normalized for term in ["ingilizce", "yabanci dil", "dil seviyesi", "diller"]):
        return SessionQueryIntent("language", wants_list="diller" in normalized)
    if any(term in normalized for term in ["gpa", "agno", "gano", "not ortalamasi"]):
        return SessionQueryIntent("gpa")
    if any(term in normalized for term in ["proje", "projeler"]):
        return SessionQueryIntent("projects", wants_list=True)
    if any(term in normalized for term in ["beceri", "yetenek", "teknoloji", "programlama"]):
        return SessionQueryIntent("skills", wants_list=True)
    if any(term in normalized for term in ["sart", "kosul", "gerekli belge", "basvuru belgesi"]):
        return SessionQueryIntent("requirements", wants_list=True)
    if any(term in normalized for term in ["baslik", "basliklar"]):
        return SessionQueryIntent("headings", wants_list=True)
    if any(term in normalized for term in ["tarih", "son teslim", "deadline"]):
        return SessionQueryIntent("date")
    if any(term in normalized for term in ["ne hakkinda", "ana konu", "konusu", "ozet", "ozetle", "kimdir", "anlat"]):
        return SessionQueryIntent("summary", wants_summary=True)
    return SessionQueryIntent("general")


def classify_section_title(title: str) -> str:
    normalized = normalize(title).strip(" :-")
    if re.match(r"^madde\s+\d+", normalized):
        return "article"
    return SECTION_TITLES.get(normalized, "general")


def enrich_metadata_flags(text: str, metadata: dict) -> dict:
    enriched = dict(metadata or {})
    normalized = normalize(text)
    enriched["contains_email"] = bool(extract_email(text))
    enriched["contains_phone"] = bool(extract_phone(text))
    enriched["contains_date"] = bool(extract_dates(text))
    enriched["contains_list"] = bool(re.search(r"(^|\n|\s)([-*•]|\d+[.)]|[a-zçğıöşü][)])\s+", text, re.IGNORECASE))
    enriched["contains_language_level"] = bool(extract_language_levels(text))
    enriched["contains_project_terms"] = any(term in normalized for term in ["proje", "github", "uygulama", "model"])
    enriched["contains_requirement_terms"] = any(term in normalized for term in ["sart", "kosul", "gerekli", "basvuru", "belge"])
    if "section_title" in enriched and "section_type" not in enriched:
        enriched["section_type"] = classify_section_title(str(enriched["section_title"]))
    return enriched


def extract_email(text: str) -> list[str]:
    return sorted(set(EMAIL_RE.findall(text or "")))


def extract_phone(text: str) -> list[str]:
    values = []
    for match in PHONE_RE.findall(text or ""):
        digits = re.sub(r"\D", "", match)
        if 8 <= len(digits) <= 15:
            values.append(match.strip())
    return sorted(set(values))


def extract_urls(text: str) -> list[str]:
    return sorted(set(item.rstrip(".,;") for item in URL_RE.findall(text or "")))


def extract_language_levels(text: str) -> list[tuple[str, str]]:
    matches = set((lang.strip(), level.strip()) for lang, level in LANGUAGE_LEVEL_RE.findall(text or ""))
    normalized = normalize(text)
    for language in ["ingilizce", "almanca", "fransizca", "arapca", "ispanyolca", "rusca"]:
        pattern = rf"\b{language}\b\s*[:=-]?\s*(a1|a2|b1|b2|c1|c2|baslangic|orta|ileri|akici)"
        for level in re.findall(pattern, normalized, flags=re.IGNORECASE):
            matches.add((language.title(), level.upper()))
    return sorted(matches)


def extract_gpa(text: str) -> list[str]:
    return sorted(set(match.replace(",", ".") for match in GPA_RE.findall(text or "")))


def extract_dates(text: str) -> list[str]:
    return sorted(set(match.strip() for match in DATE_RE.findall(text or "")))


def extract_section_items(section_text: str, section_type: str = "general") -> list[str]:
    prepared = re.sub(r"\s+([-*•])\s+", r"\n\1 ", str(section_text or ""))
    prepared = re.sub(r"\s+(\d+[.)])\s+", r"\n\1 ", prepared)
    lines = [line.strip(" -•\t") for line in prepared.splitlines() if line.strip()]
    items = []
    for line in lines:
        cleaned = re.sub(r"^([-*•]|\d+[.)]|[a-zçğıöşü][)])\s*", "", line, flags=re.IGNORECASE).strip()
        if not cleaned or len(cleaned) < 3:
            continue
        if section_type in {"projects", "skills", "languages", "requirements"}:
            if ":" in cleaned or "-" in cleaned or len(cleaned.split()) <= 14:
                items.append(cleaned)
        elif re.match(r"^([-*•]|\d+[.)]|[a-zçğıöşü][)])\s+", line, re.IGNORECASE):
            items.append(cleaned)
    return _dedupe(items)


def extract_project_titles(section_text: str) -> list[str]:
    return extract_section_items(section_text, "projects")


def extract_requirement_items(section_text: str) -> list[str]:
    return extract_section_items(section_text, "requirements")


def extract_heading_candidates(chunks: list) -> list[str]:
    headings = []
    for chunk in chunks:
        title = (getattr(chunk, "metadata", {}) or {}).get("section_title")
        if title:
            headings.append(str(title))
        for line in str(getattr(chunk, "text", "") or "").splitlines():
            candidate = line.strip(" :-")
            if 4 <= len(candidate) <= 80 and not re.search(r"[.!?]$", candidate):
                if len(candidate.split()) <= 6:
                    headings.append(candidate)
    return _dedupe(headings)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = normalize(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result
