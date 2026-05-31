import json

from dynamic_menu_reader import (
    fetch_dining_menu,
    format_dining_menu_response,
    is_dining_menu_query,
    parse_dining_menu_html,
    parse_dining_menu_text,
    select_menu_for_query,
    select_menu_for_query_details,
)
from evaluation.evaluate_dynamic_menu import build_report, load_questions


def test_dining_menu_intent_positive_examples():
    assert is_dining_menu_query("bugun yemekte ne var")
    assert is_dining_menu_query("21 mayista yemekhanede ne var")
    assert is_dining_menu_query("5 Mayıs'ta yemekhanede ne var")
    assert is_dining_menu_query("ne yemek var")
    assert is_dining_menu_query("yemekhane menusu nedir")
    assert is_dining_menu_query("aylik yemek listesi")


def test_dining_menu_intent_negative_examples():
    assert not is_dining_menu_query("Yemekhane ile ilgili kaynaklar nelerdir")
    assert not is_dining_menu_query("Yemekhane yonetmeligi var mi?")
    assert not is_dining_menu_query("Yemek bursu yonergesi var mi?")
    assert not is_dining_menu_query("AKTS nedir")


def test_fetch_failure_returns_safe_unavailable(monkeypatch):
    def fake_get(*args, **kwargs):
        raise TimeoutError("network down")

    monkeypatch.setattr("dynamic_menu_reader.requests.get", fake_get)

    result = fetch_dining_menu(use_cache=False)

    assert result["mode"] == "dynamic_dining_menu"
    assert result["status"] == "unavailable"
    assert result["items"] == []
    assert "diagnostics" in result


def test_parse_error_response_does_not_invent_menu():
    response = format_dining_menu_response({
        "mode": "dynamic_dining_menu",
        "status": "parse_error",
        "items": [],
        "source_title": "Test",
        "fetched_at": "2026-01-01T00:00:00+00:00",
    })

    assert "uydurulmadi" in response.lower() or "uydurulmadı" in response.lower()
    assert "Mercimek" not in response


def test_success_response_formats_menu_items():
    response = format_dining_menu_response({
        "mode": "dynamic_dining_menu",
        "status": "ok",
        "source_title": "Test Menu",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "items": [
            {"date": "2026-01-01", "meal_type": "ogle", "menu": ["Corba", "Pilav", "Ayran"]}
        ],
    }, "1 ocak 2026 yemekhane menusu")

    assert "Corba" in response
    assert "Kaynak: Test Menu" in response


def test_broad_menu_query_asks_for_date_instead_of_dumping_list():
    menu_data = {
        "mode": "dynamic_dining_menu",
        "status": "ok",
        "source_title": "Test Menu",
        "fetched_at": "2026-05-01T00:00:00+00:00",
        "items": [
            {"date": "2026-05-01", "display_date": "1 Mayis 2026", "meal_type": "ogle", "menu": ["Corba"]},
            {"date": "2026-05-02", "display_date": "2 Mayis 2026", "meal_type": "ogle", "menu": ["Pilav"]},
        ],
    }

    selection = select_menu_for_query_details(menu_data, "Yemekhane menusu ne?")
    response = format_dining_menu_response(menu_data, "Yemekhane menusu ne?")

    assert selection["status"] == "ambiguous_date"
    assert selection["items"] == []
    assert "tarih" in response.lower() or "gun" in response.lower()


def test_html_table_menu_is_parsed():
    html = """
    <html><head><title>Aylik Yemek Menusu</title></head><body>
      <table>
        <tr><th>Tarih</th><th>Menu</th></tr>
        <tr><td>27.05.2026</td><td>Mercimek corbasi, Tavuk sote, Pirinc pilav, Ayran</td></tr>
      </table>
    </body></html>
    """

    result = parse_dining_menu_html(html)

    assert result["status"] == "ok"
    assert result["diagnostics"]["parse_strategy"] == "table"
    assert result["diagnostics"]["parsed_item_count"] == 1
    assert result["items"][0]["date"] == "2026-05-27"
    assert "Tavuk sote" in result["items"][0]["menu"]


def test_plain_text_menu_is_parsed():
    text = "27.05.2026\nMercimek corbasi | Kofte | Bulgur pilav | Yogurt"

    rows = parse_dining_menu_text(text)

    assert rows
    assert rows[0]["date"] == "2026-05-27"
    assert "Kofte" in rows[0]["menu"]


def test_empty_or_random_html_is_parse_error():
    empty = parse_dining_menu_html("<html><body></body></html>")
    random_page = parse_dining_menu_html(
        "<html><body>Selcuk Universitesi Yemekhane Otomasyonu Giris Yap Yonetici Destek</body></html>"
    )

    assert empty["status"] == "parse_error"
    assert random_page["status"] == "parse_error"
    assert random_page["diagnostics"]["parsed_item_count"] == 0


def test_today_query_without_today_menu_has_safe_fallback():
    menu_data = {
        "mode": "dynamic_dining_menu",
        "status": "ok",
        "source_title": "Test Menu",
        "fetched_at": "2026-05-27T00:00:00+00:00",
        "items": [
            {"date": "2026-05-26", "meal_type": "ogle", "menu": ["Corba", "Pilav", "Ayran"]}
        ],
    }

    assert select_menu_for_query(menu_data, "bugun yemekte ne var") == []
    response = format_dining_menu_response(menu_data, "bugun yemekte ne var")

    assert "uydurulmadi" in response.lower() or "uydurulmadı" in response.lower()


def test_diagnostics_are_produced_for_parser_results():
    result = parse_dining_menu_html("<html><body><p>Bugun: Corba, Pilav, Ayran</p></body></html>")

    assert "diagnostics" in result
    assert result["diagnostics"]["raw_length"] > 0
    assert "parse_strategy" in result["diagnostics"]


def test_dynamic_menu_questions_schema_and_report():
    questions = load_questions("evaluation/dynamic_menu_smoke_questions.json")
    assert len(questions) >= 4
    assert any(item.get("expected_mode") == "dynamic_dining_menu" for item in questions)
    assert any(item.get("expected_not_mode") == "dynamic_dining_menu" for item in questions)

    report = build_report(questions, live_fetch=False)

    assert report["total_questions"] == len(questions)
    assert report["failed"] == 0
    assert report["unexpected_exception_count"] == 0
    assert report["fallback_safe_count"] >= 1
    assert "live_fetch_status" in report
    assert "parsed_item_count" in report
    assert "parse_status" in report


def test_dynamic_menu_questions_json_is_valid():
    with open("evaluation/dynamic_menu_smoke_questions.json", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list)
    assert all("id" in item and "query" in item for item in data)
