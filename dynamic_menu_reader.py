"""Dynamic reader for Selcuk University dining menu questions."""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from retrieval_normalization import normalize_ascii_lite


DINING_MENU_SOURCE_URL = "https://yemek.selcuk.edu.tr/"
DINING_MENU_SOURCE_TITLE = "Selcuk Universitesi Yemekhane Menusu"
DINING_MENU_CACHE_TTL_SECONDS = 60 * 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_CACHE: dict[str, Any] = {
    "fetched_at_monotonic": 0.0,
    "data": None,
}

_DYNAMIC_MENU_PATTERNS = (
    "bugun yemekte ne var",
    "bugun yemek ne",
    "yemekte ne var",
    "yemekhane menusu",
    "yemek menusu",
    "aylik yemek listesi",
    "aylik menu",
    "bu ay yemekte",
    "bu ayin yemekhane menusu",
    "ogle yemegi",
    "aksam yemegi",
    "yemek listesi",
)

_MENU_WORDS = {"menu", "menusu", "yemekte", "yemek", "listesi", "ogle", "aksam", "bugun", "aylik"}
_FOOD_HINT_WORDS = {
    "ayran",
    "balik",
    "bulgur",
    "cacik",
    "corba",
    "dolma",
    "fasulye",
    "helva",
    "kebap",
    "komposto",
    "kofte",
    "makarna",
    "mercimek",
    "musakka",
    "nohut",
    "patates",
    "pilav",
    "pirinc",
    "salata",
    "sebze",
    "sote",
    "tavuk",
    "tatli",
    "yogurt",
}
_NOISE_WORDS = {
    "destek",
    "giris",
    "kilavuz",
    "login",
    "ogrenci",
    "parola",
    "sifre",
    "sistem",
    "universitesi",
    "yonetici",
}
_NON_MENU_CONTEXT_WORDS = {
    "belge",
    "belgeler",
    "dokuman",
    "dokumanlar",
    "kaynak",
    "kaynaklar",
    "yonerge",
    "yonergesi",
    "yonetmelik",
    "yonetmeligi",
    "burs",
    "saat",
    "saatler",
    "hizmet",
    "hizmetleri",
}


def is_dining_menu_query(query: str) -> bool:
    """Return True when the user is asking for current dining menu content."""

    normalized = normalize_ascii_lite(query)
    if not normalized:
        return False

    tokens = set(re.findall(r"[a-z0-9]{2,}", normalized))
    if tokens & _NON_MENU_CONTEXT_WORDS and not {"menu", "menusu", "yemekte"} & tokens:
        return False

    if any(pattern in normalized for pattern in _DYNAMIC_MENU_PATTERNS):
        return True

    has_dining_context = "yemekhane" in tokens or "yemek" in tokens
    has_menu_context = bool(tokens & _MENU_WORDS)
    return has_dining_context and has_menu_context and not (tokens & _NON_MENU_CONTEXT_WORDS - {"yemek"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base_result(
    status: str,
    message: str,
    source_url: str = DINING_MENU_SOURCE_URL,
    diagnostics: dict[str, Any] | None = None,
) -> dict:
    diagnostics = diagnostics or {}
    return {
        "mode": "dynamic_dining_menu",
        "status": status,
        "source_url": source_url,
        "source_title": DINING_MENU_SOURCE_TITLE,
        "fetched_at": _now(),
        "parser": diagnostics.get("parse_strategy") or "none",
        "menu_period": "",
        "items": [],
        "message": message,
        "diagnostics": {
            "http_status": diagnostics.get("http_status"),
            "content_type": diagnostics.get("content_type", ""),
            "raw_length": diagnostics.get("raw_length", 0),
            "parsed_item_count": diagnostics.get("parsed_item_count", 0),
            "parse_strategy": diagnostics.get("parse_strategy", "none"),
            "table_count": diagnostics.get("table_count", 0),
            "candidate_line_count": diagnostics.get("candidate_line_count", 0),
            "title": diagnostics.get("title", ""),
        },
    }


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _split_menu_text(text: str) -> list[str]:
    parts = re.split(r"\s*(?:\n|,|;|\||•|-{2,}|/)\s*", text or "")
    cleaned = [_clean_text(part) for part in parts]
    return [part for part in cleaned if _looks_like_food_item(part)]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", normalize_ascii_lite(text))


def _contains_food_hint(text: str) -> bool:
    tokens = _tokens(text)
    return any(any(token.startswith(word) for token in tokens) for word in _FOOD_HINT_WORDS)


def _looks_like_food_item(text: str) -> bool:
    cleaned = _clean_text(text)
    if len(cleaned) < 3 or len(cleaned) > 90:
        return False
    normalized_tokens = set(_tokens(cleaned))
    if normalized_tokens & _NOISE_WORDS:
        return False
    return _contains_food_hint(cleaned)


def normalize_menu_date(value: str, today: date | None = None) -> str:
    """Normalize common Turkish menu dates into YYYY-MM-DD when possible."""

    today = today or date.today()
    text = _clean_text(value)
    if not text:
        return ""
    lowered = normalize_ascii_lite(text)
    if "bugun" in lowered:
        return today.isoformat()

    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", text)
    if not match:
        return ""

    day = int(match.group(1))
    month = int(match.group(2))
    year_text = match.group(3)
    year = today.year if not year_text else int(year_text)
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _build_menu_item(date_text: str, meal_type: str, menu_text: str, today: date | None = None) -> dict | None:
    menu = _split_menu_text(menu_text)
    if not menu:
        return None
    return {
        "date": normalize_menu_date(date_text, today=today),
        "raw_date": _clean_text(date_text),
        "meal_type": meal_type or "ogun",
        "menu": menu[:12],
    }


def _deduplicate_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("date") or item.get("raw_date") or "", tuple(item.get("menu") or []))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def parse_dining_menu_text(text: str, today: date | None = None) -> list[dict]:
    """Parse line-oriented menu text without treating arbitrary page text as food."""

    rows: list[dict] = []
    lines = [_clean_text(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    current_date = ""

    for line in lines:
        maybe_date = normalize_menu_date(line, today=today)
        if maybe_date:
            current_date = line
        if not _contains_food_hint(line):
            continue
        item = _build_menu_item(current_date, "ogun", line, today=today)
        if item:
            rows.append(item)

    if rows:
        return _deduplicate_items(rows)

    compact = _clean_text(text)
    if not _contains_food_hint(compact):
        return []
    item = _build_menu_item("", "ogun", compact, today=today)
    return [item] if item else []


def _parse_json_like_menu(value: Any, today: date | None = None) -> list[dict]:
    rows: list[dict] = []
    if isinstance(value, dict):
        joined = " ".join(str(item) for item in value.values())
        date_text = next((str(v) for k, v in value.items() if "date" in str(k).lower() or "tarih" in str(k).lower()), "")
        if _contains_food_hint(joined):
            item = _build_menu_item(date_text, "ogun", joined, today=today)
            if item:
                rows.append(item)
        for nested in value.values():
            rows.extend(_parse_json_like_menu(nested, today=today))
    elif isinstance(value, list):
        for nested in value:
            rows.extend(_parse_json_like_menu(nested, today=today))
    elif isinstance(value, str) and _contains_food_hint(value):
        item = _build_menu_item("", "ogun", value, today=today)
        if item:
            rows.append(item)
    return _deduplicate_items(rows)


def _parse_script_json(soup: BeautifulSoup, today: date | None = None) -> list[dict]:
    rows: list[dict] = []
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text(" ")
        if not script_text or not _contains_food_hint(script_text):
            continue
        for match in re.finditer(r"(\{.*?\}|\[.*?\])", script_text, flags=re.DOTALL):
            snippet = match.group(1)
            if len(snippet) > 20000:
                continue
            try:
                parsed = json.loads(snippet)
            except Exception:
                continue
            rows.extend(_parse_json_like_menu(parsed, today=today))
    return _deduplicate_items(rows)


def _parse_table_menus(soup: BeautifulSoup, today: date | None = None) -> list[dict]:
    rows: list[dict] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ")) for cell in tr.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            joined = " | ".join(cells)
            if not cells or len(joined) < 8 or not _contains_food_hint(joined):
                continue
            date_cell = next((cell for cell in cells if normalize_menu_date(cell, today=today)), "")
            menu_text = " | ".join(cell for cell in cells if cell != date_cell)
            item = _build_menu_item(date_cell, "ogun", menu_text, today=today)
            if item:
                rows.append(item)
    return _deduplicate_items(rows)


def parse_dining_menu_html(html: str, final_url: str = DINING_MENU_SOURCE_URL, diagnostics: dict[str, Any] | None = None) -> dict:
    """Parse dining menu HTML using table, embedded JSON, then text fallback strategies."""

    diagnostics = diagnostics or {}
    soup = BeautifulSoup(html or "", "html.parser")
    title = _clean_text(soup.title.get_text(" ")) if soup.title else DINING_MENU_SOURCE_TITLE
    diagnostics.update({
        "raw_length": len(html or ""),
        "table_count": len(soup.find_all("table")),
        "title": title,
    })

    json_rows = _parse_script_json(soup)
    table_rows = _parse_table_menus(soup)

    text_soup = BeautifulSoup(html or "", "html.parser")
    for tag in text_soup(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = text_soup.get_text("\n")
    candidate_lines = [line for line in visible_text.splitlines() if _contains_food_hint(line)]
    diagnostics["candidate_line_count"] = len(candidate_lines)
    text_rows = parse_dining_menu_text(visible_text)

    strategies = (
        ("json", json_rows),
        ("table", table_rows),
        ("text", text_rows),
    )
    for strategy, rows in strategies:
        rows = _deduplicate_items(rows)
        if rows:
            diagnostics["parse_strategy"] = strategy
            diagnostics["parsed_item_count"] = len(rows)
            result = _base_result("ok", "Yemekhane menusu dinamik kaynaktan okundu.", final_url, diagnostics)
            result["source_title"] = title or DINING_MENU_SOURCE_TITLE
            result["parser"] = strategy
            result["items"] = rows[:14]
            result["menu_period"] = rows[0].get("date") or rows[0].get("raw_date") or "guncel"
            return result

    diagnostics["parse_strategy"] = "none"
    diagnostics["parsed_item_count"] = 0
    return _base_result(
        "parse_error",
        "Yemekhane menusu kaynagina erisildi ancak menu icerigi guvenilir sekilde ayrisitirilamadi.",
        final_url,
        diagnostics,
    )


def select_menu_for_query(menu_data: dict, query: str, today: date | None = None) -> list[dict]:
    """Select the most relevant menu rows for the query."""

    today = today or date.today()
    items = list(menu_data.get("items") or [])
    normalized_query = normalize_ascii_lite(query)
    if "bugun" in normalized_query:
        today_items = [item for item in items if item.get("date") == today.isoformat()]
        if today_items:
            return today_items[:2]
        return []
    return items[:5]


def fetch_dining_menu(
    source_url: str = DINING_MENU_SOURCE_URL,
    timeout_sec: int = 12,
    use_cache: bool = True,
) -> dict:
    """Fetch and parse the current dining menu without raising UI-breaking errors."""

    now = time.monotonic()
    cached = _CACHE.get("data")
    if use_cache and cached and now - float(_CACHE.get("fetched_at_monotonic") or 0) < DINING_MENU_CACHE_TTL_SECONDS:
        return dict(cached)

    diagnostics: dict[str, Any] = {
        "http_status": None,
        "content_type": "",
        "raw_length": 0,
        "parse_strategy": "none",
    }

    try:
        response = requests.get(
            source_url,
            timeout=timeout_sec,
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        diagnostics["http_status"] = response.status_code
        diagnostics["content_type"] = response.headers.get("content-type", "")
        diagnostics["raw_length"] = len(response.text or "")
        response.raise_for_status()
    except Exception:
        result = _base_result(
            "unavailable",
            "Yemekhane menusu kaynagina su anda erisemedim. Menu icerigi uydurulmadi.",
            source_url,
            diagnostics,
        )
    else:
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower() and not response.text.strip().startswith("<"):
            result = _base_result(
                "parse_error",
                "Yemekhane menusu kaynagi beklenen HTML icerigini dondurmedi. Menu icerigi uydurulmadi.",
                response.url,
                diagnostics,
            )
        else:
            result = parse_dining_menu_html(response.text, response.url, diagnostics)

    _CACHE["fetched_at_monotonic"] = now
    _CACHE["data"] = dict(result)
    return result


def format_dining_menu_response(menu_data: dict, query: str = "") -> str:
    """Format dynamic dining menu data for the chat response."""

    status = menu_data.get("status")
    source_title = menu_data.get("source_title") or DINING_MENU_SOURCE_TITLE
    fetched_at = menu_data.get("fetched_at") or ""

    if status != "ok" or not menu_data.get("items"):
        return (
            "Yemekhane menusu kaynagina su anda erisemedim veya menu icerigini guvenilir sekilde okuyamadim. "
            "Bu nedenle menu icerigi uydurulmadi."
        )

    selected_items = select_menu_for_query(menu_data, query)
    if not selected_items:
        return (
            "Yemekhane menusu kaynaginda bu sorguya uygun guncel menu satirini guvenilir sekilde bulamadim. "
            "Bu nedenle menu icerigi uydurulmadi."
        )

    lines = ["Guncel yemekhane menusu kaynagindan okunan bilgi:"]
    for item in selected_items:
        label_parts = []
        if item.get("date") or item.get("raw_date"):
            label_parts.append(str(item.get("date") or item.get("raw_date")))
        if item.get("meal_type"):
            label_parts.append(str(item["meal_type"]))
        label = " - ".join(label_parts) or "Menu"
        lines.extend(["", f"**{label}**"])
        for menu_item in item.get("menu", [])[:10]:
            lines.append(f"- {menu_item}")

    lines.extend([
        "",
        f"Kaynak: {source_title}",
        f"Son kontrol: {fetched_at}",
    ])
    return "\n".join(lines).strip()


def dining_menu_to_documents(menu_data: dict) -> list[Document]:
    """Build a lightweight dynamic source document for the source panel."""

    if not menu_data.get("source_url"):
        return []
    snippet = menu_data.get("message") or "Yemekhane menusu dinamik kaynak kontrolu."
    if menu_data.get("items"):
        first_menu = ", ".join(menu_data["items"][0].get("menu", [])[:6])
        if first_menu:
            snippet = first_menu
    return [
        Document(
            page_content=snippet,
            metadata={
                "source": menu_data.get("source_url") or DINING_MENU_SOURCE_URL,
                "title": menu_data.get("source_title") or DINING_MENU_SOURCE_TITLE,
                "source_type": "dynamic_menu",
                "source_family": "dining_menu",
                "fetched_at": menu_data.get("fetched_at") or "",
            },
        )
    ]


def get_dynamic_menu_health() -> dict[str, Any]:
    """Return static dynamic-menu configuration health without doing a live fetch."""

    return {
        "mode": "dynamic_dining_menu",
        "source_url": DINING_MENU_SOURCE_URL,
        "source_title": DINING_MENU_SOURCE_TITLE,
        "cache_ttl_seconds": DINING_MENU_CACHE_TTL_SECONDS,
        "supported_parse_strategies": ["json", "table", "text"],
        "live_fetch_required": False,
        "secret_required": False,
    }
