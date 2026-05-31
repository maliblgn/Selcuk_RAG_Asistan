"""Dynamic reader for Selcuk University dining menu questions."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from datetime import timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from retrieval_normalization import normalize_ascii_lite


DINING_MENU_SOURCE_URL = "https://yemek.selcuk.edu.tr/Menu/MenuGetir"
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
_DATE_QUERY_WORDS = {
    "bugun",
    "bugunku",
    "yarin",
    "yarinki",
    "dun",
    "hafta",
    "haftanin",
    "pazartesi",
    "sali",
    "carsamba",
    "persembe",
    "cuma",
    "cumartesi",
    "pazar",
    "ocak",
    "subat",
    "mart",
    "nisan",
    "mayis",
    "haziran",
    "temmuz",
    "agustos",
    "eylul",
    "ekim",
    "kasim",
    "aralik",
}
_TURKISH_MONTHS = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}
_MONTH_NAME_PATTERN = r"ocak|subat|mart|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik"
_MONTH_CASE_SUFFIX_PATTERN = r"(?:(?:\s*)(?:ta|te|da|de)|\s+ayinda|\s+ayi(?:nda)?)?"
_TURKISH_WEEKDAYS = {
    "pazartesi": 0,
    "sali": 1,
    "carsamba": 2,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}
_WEEKDAY_DISPLAY = {
    0: "Pazartesi",
    1: "Salı",
    2: "Çarşamba",
    3: "Perşembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}
_MONTH_DISPLAY = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}
_FOOD_HINT_WORDS = {
    "ayran",
    "balik",
    "bulgur",
    "cacik",
    "corba",
    "dolma",
    "fasulye",
    "helva",
    "ispanak",
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
    "puding",
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


@dataclass(frozen=True)
class DiningMenuEntry:
    """One date-based dining menu entry parsed from the dynamic source."""

    date: str
    day_name: str
    display_date: str
    items: list[str]
    calories: str | None = None
    has_meal: bool = True
    source_url: str = DINING_MENU_SOURCE_URL
    parse_confidence: str = "medium"

    def to_legacy_item(self) -> dict[str, Any]:
        """Return the item shape used by the existing app and source panel."""

        return {
            "date": self.date,
            "raw_date": self.display_date,
            "day_name": self.day_name,
            "display_date": self.display_date,
            "meal_type": "öğle",
            "menu": list(self.items),
            "calories": self.calories,
            "has_meal": self.has_meal,
            "source_url": self.source_url,
            "parse_confidence": self.parse_confidence,
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

    if tokens & _DATE_QUERY_WORDS and ({"yemekhane", "yemek", "yemekte", "menu", "menusu", "listesi"} & tokens):
        return True

    if re.search(rf"\b\d{{1,2}}\s+(?:{_MONTH_NAME_PATTERN})(?:\s+\d{{4}})?{_MONTH_CASE_SUFFIX_PATTERN}\b", normalized):
        return bool({"yemek", "yemekte", "menu", "menusu", "listesi"} & tokens)

    if re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", normalized):
        return bool({"yemek", "yemekte", "menu", "menusu", "listesi"} & tokens)

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


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _format_display_date(value: date, day_name: str | None = None) -> str:
    day_label = day_name or _WEEKDAY_DISPLAY.get(value.weekday(), "")
    month_label = _MONTH_DISPLAY.get(value.month, str(value.month))
    if day_label:
        return f"{value.day} {month_label} {value.year} {day_label}"
    return f"{value.day} {month_label} {value.year}"


def _infer_menu_year(today: date | None = None, entries: list[dict] | None = None) -> int:
    if entries:
        for item in entries:
            parsed = _parse_iso_date(str(item.get("date") or ""))
            if parsed:
                return parsed.year
    return (today or date.today()).year


def _extract_named_month_date(text: str, year: int) -> date | None:
    normalized = normalize_ascii_lite(text)
    match = re.search(
        rf"\b(\d{{1,2}})\s+({_MONTH_NAME_PATTERN})(?:\s+(\d{{4}}))?{_MONTH_CASE_SUFFIX_PATTERN}\b",
        normalized,
    )
    if not match:
        return None
    day = int(match.group(1))
    month = _TURKISH_MONTHS[match.group(2)]
    parsed_year = int(match.group(3)) if match.group(3) else year
    try:
        return date(parsed_year, month, day)
    except ValueError:
        return None


def _is_weekday_line(value: str) -> bool:
    return normalize_ascii_lite(value) in _TURKISH_WEEKDAYS


def _is_no_meal_line(value: str) -> bool:
    return "ogun yok" in normalize_ascii_lite(value)


def _is_calorie_line(value: str) -> bool:
    return "toplam kalori" in normalize_ascii_lite(value)


def normalize_menu_date(value: str, today: date | None = None) -> str:
    """Normalize common Turkish menu dates into YYYY-MM-DD when possible."""

    today = today or date.today()
    text = _clean_text(value)
    if not text:
        return ""
    lowered = normalize_ascii_lite(text)
    if "bugun" in lowered:
        return today.isoformat()
    if "yarin" in lowered:
        return (today + timedelta(days=1)).isoformat()
    if "dun" in lowered:
        return (today - timedelta(days=1)).isoformat()

    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", text)
    if match:
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

    named = _extract_named_month_date(text, today.year)
    return named.isoformat() if named else ""


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
        key = (item.get("date") or item.get("raw_date") or "", tuple(item.get("menu") or []), item.get("has_meal", True))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _deduplicate_entries(entries: list[DiningMenuEntry]) -> list[DiningMenuEntry]:
    seen_dates: set[str] = set()
    deduped: list[DiningMenuEntry] = []
    for entry in entries:
        key = entry.date or entry.display_date
        if key in seen_dates:
            continue
        seen_dates.add(key)
        deduped.append(entry)
    return sorted(deduped, key=lambda item: item.date or item.display_date)


def _finish_entry(
    entries: list[DiningMenuEntry],
    current_date: date | None,
    day_name: str,
    menu_items: list[str],
    calories: str | None,
    has_meal: bool,
    source_url: str = DINING_MENU_SOURCE_URL,
) -> None:
    if not current_date:
        return
    cleaned_items = [_clean_text(item) for item in menu_items if _clean_text(item)]
    if not cleaned_items and has_meal:
        return
    display_day = day_name or _WEEKDAY_DISPLAY.get(current_date.weekday(), "")
    display_date = _format_display_date(current_date, display_day)
    entries.append(
        DiningMenuEntry(
            date=current_date.isoformat(),
            day_name=display_day,
            display_date=display_date,
            items=cleaned_items[:12],
            calories=calories,
            has_meal=has_meal,
            source_url=source_url,
            parse_confidence="high" if cleaned_items or not has_meal else "medium",
        )
    )


def parse_dining_menu_entries_from_text(
    text: str,
    today: date | None = None,
    source_url: str = DINING_MENU_SOURCE_URL,
) -> list[DiningMenuEntry]:
    """Parse the Selcuk dining page into one entry per date."""

    today = today or date.today()
    lines = [_clean_text(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    entries: list[DiningMenuEntry] = []
    current_date: date | None = None
    current_day = ""
    current_items: list[str] = []
    current_calories: str | None = None
    current_has_meal = True
    pending_day = ""
    expect_calorie_value = False

    def finish_current() -> None:
        _finish_entry(
            entries,
            current_date,
            current_day,
            current_items,
            current_calories,
            current_has_meal,
            source_url=source_url,
        )

    for line in lines:
        normalized = normalize_ascii_lite(line)

        if expect_calorie_value:
            if re.fullmatch(r"\d+(?:[.,]\d+)?", normalized):
                current_calories = line
                expect_calorie_value = False
                continue
            expect_calorie_value = False

        if _is_weekday_line(line):
            pending_day = _WEEKDAY_DISPLAY[_TURKISH_WEEKDAYS[normalized]]
            continue

        parsed_date_text = normalize_menu_date(line, today=today)
        parsed_date = _parse_iso_date(parsed_date_text)
        if parsed_date and re.fullmatch(
            r"\d{1,2}\s+(?:ocak|subat|mart|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik)(?:\s+\d{4})?",
            normalized,
        ):
            finish_current()
            current_date = parsed_date
            current_day = pending_day or _WEEKDAY_DISPLAY.get(parsed_date.weekday(), "")
            current_items = []
            current_calories = None
            current_has_meal = True
            pending_day = ""
            continue

        if parsed_date and re.fullmatch(r"\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?", normalized):
            finish_current()
            current_date = parsed_date
            current_day = pending_day or _WEEKDAY_DISPLAY.get(parsed_date.weekday(), "")
            current_items = []
            current_calories = None
            current_has_meal = True
            pending_day = ""
            continue

        if not current_date:
            continue

        if _is_no_meal_line(line):
            current_has_meal = False
            current_items = []
            continue

        if _is_calorie_line(line):
            expect_calorie_value = True
            continue

        if _looks_like_food_item(line):
            current_items.append(line)

    finish_current()
    return _deduplicate_entries(entries)


def parse_dining_menu_text(text: str, today: date | None = None) -> list[dict]:
    """Parse line-oriented menu text without treating arbitrary page text as food."""

    entries = parse_dining_menu_entries_from_text(text, today=today)
    if entries:
        return [entry.to_legacy_item() for entry in entries]

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
    if normalize_ascii_lite(title) in {"menu", "menus"}:
        title = DINING_MENU_SOURCE_TITLE
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

    strategies = [
        ("json", json_rows),
        ("table", table_rows),
        ("text", text_rows),
    ]
    strategies.sort(
        key=lambda item: (
            len({row.get("date") for row in item[1] if row.get("date")}),
            len(item[1]),
        ),
        reverse=True,
    )
    for strategy, rows in strategies:
        rows = _deduplicate_items(rows)
        if rows:
            diagnostics["parse_strategy"] = strategy
            diagnostics["parsed_item_count"] = len(rows)
            result = _base_result("ok", "Yemekhane menusu dinamik kaynaktan okundu.", final_url, diagnostics)
            result["source_title"] = title or DINING_MENU_SOURCE_TITLE
            result["parser"] = strategy
            result["items"] = rows
            result["menu_period"] = rows[0].get("date") or rows[0].get("raw_date") or "guncel"
            dates = sorted(item.get("date") for item in rows if item.get("date"))
            if dates:
                result["available_start_date"] = dates[0]
                result["available_end_date"] = dates[-1]
                result["menu_period"] = f"{dates[0]} - {dates[-1]}"
            return result

    diagnostics["parse_strategy"] = "none"
    diagnostics["parsed_item_count"] = 0
    return _base_result(
        "parse_error",
        "Yemekhane menusu kaynagina erisildi ancak menu icerigi guvenilir sekilde ayrisitirilamadi.",
        final_url,
        diagnostics,
    )


def _query_target_date(query: str, today: date, entries: list[dict]) -> date | None:
    normalized_query = normalize_ascii_lite(query)
    inferred_year = _infer_menu_year(today=today, entries=entries)

    if "bugun" in normalized_query or "bugunku" in normalized_query or "bu gun" in normalized_query:
        return today
    if "yarin" in normalized_query or "yarinki" in normalized_query:
        return today + timedelta(days=1)
    if "dun" in normalized_query:
        return today - timedelta(days=1)

    numeric = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", normalized_query)
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year_text = numeric.group(3)
        year = inferred_year if not year_text else int(year_text)
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return _extract_named_month_date(query, inferred_year)


def _query_weekday(query: str) -> int | None:
    normalized_query = normalize_ascii_lite(query)
    for name, weekday in _TURKISH_WEEKDAYS.items():
        if re.search(rf"\b{name}\b", normalized_query):
            return weekday
    return None


def _is_week_query(query: str) -> bool:
    normalized_query = normalize_ascii_lite(query)
    return "bu hafta" in normalized_query or "haftanin" in normalized_query or "haftalik" in normalized_query


def _is_month_query(query: str) -> bool:
    normalized_query = normalize_ascii_lite(query)
    return "bu ay" in normalized_query or "aylik" in normalized_query or bool(
        re.search(rf"\b(?:{_MONTH_NAME_PATTERN})(?:\s+ayi|\s+ayinda)\b", normalized_query)
    )


def _available_range_message(items: list[dict]) -> str:
    dates = sorted(item.get("date") for item in items if item.get("date"))
    if not dates:
        return "Mevcut menü listesinde tarih aralığı okunamadı."
    return f"Mevcut listede {dates[0]} - {dates[-1]} arasındaki tarihler var."


def select_menu_for_query_details(menu_data: dict, query: str, today: date | None = None) -> dict[str, Any]:
    """Select date-aware menu rows and explain non-match cases."""

    today = today or date.today()
    items = list(menu_data.get("items") or [])
    normalized_query = normalize_ascii_lite(query)

    if not items:
        return {"status": "no_data", "items": [], "message": "Menü kaydını güvenilir şekilde okuyamadım."}

    target_date = _query_target_date(query, today, items)
    if target_date:
        selected = [item for item in items if item.get("date") == target_date.isoformat()]
        if selected:
            return {"status": "ok", "items": selected[:1], "selection": "single_day"}
        return {
            "status": "no_menu_for_date",
            "items": [],
            "message": f"{target_date.isoformat()} için menü kaydı bulamadım. {_available_range_message(items)}",
        }

    if _is_week_query(query):
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        selected = []
        for item in items:
            parsed = _parse_iso_date(str(item.get("date") or ""))
            if parsed and week_start <= parsed <= week_end:
                selected.append(item)
        if not selected:
            return {
                "status": "no_menu_for_date",
                "items": [],
                "message": f"Bu hafta için menü kaydı bulamadım. {_available_range_message(items)}",
            }
        return {"status": "ok", "items": selected[:5], "selection": "week"}

    weekday = _query_weekday(query)
    if weekday is not None:
        selected = []
        for item in items:
            parsed = _parse_iso_date(str(item.get("date") or ""))
            if parsed and parsed.weekday() == weekday:
                selected.append(item)
        if len(selected) == 1:
            return {"status": "ok", "items": selected, "selection": "single_weekday"}
        if len(selected) > 1:
            return {
                "status": "ambiguous_date",
                "items": [],
                "message": f"Bu menü listesinde birden fazla {_WEEKDAY_DISPLAY[weekday]} var; tarih de belirtir misin?",
            }
        return {
            "status": "no_menu_for_date",
            "items": [],
            "message": f"{_WEEKDAY_DISPLAY[weekday]} için menü kaydı bulamadım. {_available_range_message(items)}",
        }

    if _is_month_query(query):
        return {
            "status": "ambiguous_date",
            "items": [],
            "message": "Ay genelindeki menüyü tamamen dökmüyorum; belirli bir gün veya tarih belirtir misin?",
        }

    if "bugun" in normalized_query:
        return {
            "status": "no_menu_for_date",
            "items": [],
            "message": f"Bugün için güvenilir menü satırı bulamadım. {_available_range_message(items)}",
        }

    return {"status": "ok", "items": items[:5], "selection": "limited"}


def select_menu_for_query(menu_data: dict, query: str, today: date | None = None) -> list[dict]:
    """Select the most relevant menu rows for the query."""

    return list(select_menu_for_query_details(menu_data, query, today=today).get("items") or [])


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
            "Yemekhane menüsü kaynağına şu anda erişemedim veya menü içeriğini güvenilir şekilde okuyamadım. "
            "Bu nedenle menü içeriği uydurulmadı."
        )

    selection = select_menu_for_query_details(menu_data, query)
    selected_items = list(selection.get("items") or [])
    if not selected_items:
        message = selection.get("message")
        if message:
            return f"{message} Menü içeriği uydurulmadı."
        return (
            "Yemekhane menüsü kaynağında bu sorguya uygun güncel menü satırını güvenilir şekilde bulamadım. "
            "Bu nedenle menü içeriği uydurulmadı."
        )

    lines = ["Güncel yemekhane menüsü kaynağından okunan bilgi:"]
    for item in selected_items:
        label = str(item.get("display_date") or item.get("raw_date") or item.get("date") or "Menü")
        lines.extend(["", f"**{label}**"])
        if item.get("has_meal") is False:
            lines.append("- Öğün Yok")
        else:
            for menu_item in item.get("menu", [])[:10]:
                lines.append(f"- {menu_item}")
        if item.get("calories"):
            lines.append(f"Toplam kalori: {item['calories']}")

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
