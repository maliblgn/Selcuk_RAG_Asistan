"""Dynamic reader for Selcuk University dining menu questions."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
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
    "corba",
    "fasulye",
    "kebap",
    "komposto",
    "kofte",
    "makarna",
    "mercimek",
    "nohut",
    "patates",
    "pilav",
    "pirinc",
    "salata",
    "sebze",
    "tavuk",
    "tatli",
    "yogurt",
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


def _base_result(status: str, message: str, source_url: str = DINING_MENU_SOURCE_URL) -> dict:
    return {
        "mode": "dynamic_dining_menu",
        "status": status,
        "source_url": source_url,
        "source_title": DINING_MENU_SOURCE_TITLE,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "menu_period": "",
        "items": [],
        "message": message,
    }


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _split_menu_text(text: str) -> list[str]:
    parts = re.split(r"\s*(?:\n|,|;|\||•|-{2,}|/)\s*", text or "")
    cleaned = [_clean_text(part) for part in parts]
    return [part for part in cleaned if len(part) >= 2]


def _contains_food_hint(text: str) -> bool:
    normalized = normalize_ascii_lite(text)
    tokens = re.findall(r"[a-z0-9]{3,}", normalized)
    return any(any(token.startswith(word) for token in tokens) for word in _FOOD_HINT_WORDS)


def _extract_menu_items_from_html(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = _clean_text(soup.title.get_text(" ")) if soup.title else DINING_MENU_SOURCE_TITLE
    rows: list[dict] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ")) for cell in tr.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            joined = " ".join(cells)
            if not cells or len(joined) < 8:
                continue
            if not _contains_food_hint(joined):
                continue
            date = next((cell for cell in cells if re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", cell)), "")
            menu_text = " ".join(cell for cell in cells if cell != date)
            rows.append({
                "date": date,
                "meal_type": "ogun",
                "menu": _split_menu_text(menu_text),
            })

    if not rows:
        text = _clean_text(soup.get_text("\n"))
        candidate_lines = [
            _clean_text(line)
            for line in text.split("\n")
            if _contains_food_hint(line)
        ]
        if candidate_lines:
            rows.append({
                "date": "",
                "meal_type": "ogun",
                "menu": _split_menu_text(" | ".join(candidate_lines[:8])),
            })

    if not rows:
        return _base_result(
            "parse_error",
            "Yemekhane menusu kaynagina erisildi ancak menu icerigi guvenilir sekilde ayrisitirilamadi.",
            final_url,
        )

    result = _base_result("ok", "Yemekhane menusu dinamik kaynaktan okundu.", final_url)
    result["source_title"] = title or DINING_MENU_SOURCE_TITLE
    result["items"] = rows[:14]
    result["menu_period"] = rows[0].get("date") or "guncel"
    return result


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

    try:
        response = requests.get(
            source_url,
            timeout=timeout_sec,
            headers={"User-Agent": BROWSER_USER_AGENT},
        )
        response.raise_for_status()
    except Exception:
        result = _base_result(
            "unavailable",
            "Yemekhane menusu kaynagina su anda erisemedim. Menu icerigi uydurulmadi.",
            source_url,
        )
    else:
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower() and not response.text.strip().startswith("<"):
            result = _base_result(
                "parse_error",
                "Yemekhane menusu kaynagi beklenen HTML icerigini dondurmedi. Menu icerigi uydurulmadi.",
                response.url,
            )
        else:
            result = _extract_menu_items_from_html(response.text, response.url)

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

    normalized_query = normalize_ascii_lite(query)
    selected_items = menu_data.get("items", [])
    if "bugun" in normalized_query and selected_items:
        selected_items = selected_items[:1]
    else:
        selected_items = selected_items[:5]

    lines = ["Guncel yemekhane menusu kaynagindan okunan bilgi:"]
    for item in selected_items:
        label_parts = []
        if item.get("date"):
            label_parts.append(str(item["date"]))
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
