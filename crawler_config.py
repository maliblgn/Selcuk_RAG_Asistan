"""
Merkezi crawler & scraper konfigürasyonu.

Hem web_crawler.py hem web_scraper.py tarafından kullanılır.
Ortak ayarlar (User-Agent rotation, exclude patterns, timeout)
tek bir yerden yönetilir.
"""

import os
import random
from typing import Tuple

# ─────────────────── User-Agent Havuzu ───────────────────
DEFAULT_USER_AGENTS: Tuple[str, ...] = (
    "Selcuk-RAG-Bot/2.0 (+https://github.com/maliblgn/Selcuk_RAG_Asistan; educational-use)",
    "Mozilla/5.0 (compatible; SelcukEduBot/2.0; +educational-research)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 SelcukRAG/2.0",
)

# ─────────────────── Hariç Tutma Desenleri ───────────────────
DEFAULT_EXCLUDE_PATTERNS: Tuple[str, ...] = (
    "/login",
    "/signin",
    "/logout",
    "/en/",
    "/en?",
    "?lang=en",
    "/admin/",
    "/wp-admin/",
    "/api/",
    "/webmail",
    "/ubs/",
    "/obs/",
    "perbis.selcuk.edu.tr",
    "guvenlik.selcuk.edu.tr",
    "kutuphaneotomasyon.selcuk.edu.tr",
    "bordro.selcuk.edu.tr",
    "odeme.selcuk.edu.tr",
    "obis.selcuk.edu.tr",
    "posta.selcuk.edu.tr",
    "ogrposta.selcuk.edu.tr",
    "javascript:",
    "mailto:",
    "tel:",
)

DEFAULT_PRIORITY_PATTERNS: Tuple[str, ...] = (
    "yonetmelik",
    "yönetmelik",
    "yonerge",
    "yönerge",
    "mevzuat",
    "dokuman",
    "doküman",
    "belge",
    "staj",
    "burs",
    "cift",
    "çift",
    "diploma",
    "mazeret",
    "akademik-takvim",
    "akademik_takvim",
)

# ─────────────────── Dosya Uzantı Sınıflandırma ───────────────────
DOCUMENT_EXTENSIONS: Tuple[str, ...] = (
    ".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls",
)

SKIP_EXTENSIONS: Tuple[str, ...] = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".css", ".js", ".map",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".xml", ".rss", ".atom",
)


def _parse_csv_env(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    """Virgülle ayrılmış env değişkenini tuple'a çevir."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    return items if items else default


def get_user_agents() -> Tuple[str, ...]:
    """User-Agent listesini döndür.

    CRAWL_USER_AGENTS env tanımlıysa onu, değilse varsayılanları kullanır.
    """
    return _parse_csv_env("CRAWL_USER_AGENTS", DEFAULT_USER_AGENTS)


def pick_user_agent() -> str:
    """Rastgele bir User-Agent seç."""
    agents = get_user_agents()
    return random.choice(agents)


def get_exclude_patterns() -> Tuple[str, ...]:
    """Hariç tutma desenleri listesini döndür.

    CRAWL_EXCLUDE_PATTERNS env tanımlıysa onu, değilse varsayılanları kullanır.
    """
    merged = list(DEFAULT_EXCLUDE_PATTERNS)
    for item in _parse_csv_env("CRAWL_EXCLUDE_PATTERNS", ()):
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def get_priority_patterns() -> Tuple[str, ...]:
    """Crawler link siralamasinda one alinacak URL desenleri."""
    return _parse_csv_env("CRAWL_PRIORITY_PATTERNS", DEFAULT_PRIORITY_PATTERNS)


def get_request_timeout() -> int:
    """Crawler request timeout (saniye)."""
    raw = os.getenv("CRAWL_REQUEST_TIMEOUT")
    if raw is None:
        return 15
    try:
        return int(raw)
    except ValueError:
        return 15


def is_url_excluded(url: str, patterns: Tuple[str, ...] | None = None) -> bool:
    """Verilen URL, hariç tutma desenlerinden herhangi birini içeriyor mu?"""
    if patterns is None:
        patterns = get_exclude_patterns()
    url_lower = url.lower()
    return any(pattern.lower() in url_lower for pattern in patterns)
