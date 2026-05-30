from datetime import date

from dynamic_menu_reader import (
    format_dining_menu_response,
    is_dining_menu_query,
    parse_dining_menu_html,
    select_menu_for_query,
    select_menu_for_query_details,
)
from query_router import MODE_DYNAMIC_DINING_MENU, MODE_RAG, MODE_SOURCE_DISCOVERY, route_query


MENU_HTML = """
<html>
  <head><title>Menu</title></head>
  <body>
    <h1>Selçuk Üniversitesi Yemekhane Menüsü</h1>
    <section>
      <h3>Pazartesi</h3>
      <h4>4 Mayıs</h4>
      <div>ETLİ NOHUT</div>
      <div>TERBİYELİ ŞEHRİYE ÇORBASI</div>
      <div>BULGUR PİLAVI</div>
      <div>TAHİN HELVA</div>
      <div>Toplam Kalori:</div><div>0</div>
      <h3>Salı</h3>
      <h4>5 Mayıs</h4>
      <div>EZOGELİN ÇORBASI</div>
      <div>FIRIN TAVUK BAGET</div>
      <div>TEREYAĞLI MAKARNA</div>
      <div>AYRAN</div>
      <div>Toplam Kalori:</div><div>0</div>
      <h3>Çarşamba</h3>
      <h4>20 Mayıs</h4>
      <div>ISPANAK GRATEN</div>
      <div>PUDİNG</div>
      <div>SÜZME MERCİMEK ÇORBA</div>
      <div>BOLONEZ SOSLU MAKARNA</div>
      <div>Toplam Kalori:</div><div>0</div>
      <h3>Pazartesi</h3>
      <h4>18 Mayıs</h4>
      <div>PİRİNÇ PİLAVI</div>
      <div>PATATESLİ PARMAK KÖFTE</div>
      <div>HAYDARİ</div>
      <div>EZOGELİN ÇORBASI</div>
      <div>Toplam Kalori:</div><div>0</div>
    </section>
    <section>
      <div>Pazartesi</div><div>Salı</div><div>Çarşamba</div><div>Perşembe</div><div>Cuma</div>
      <div>1 Mayıs</div><div>Öğün Yok</div>
      <div>4 Mayıs</div>
      <div>ETLİ NOHUT</div>
      <div>TERBİYELİ ŞEHRİYE ÇORBASI</div>
      <div>BULGUR PİLAVI</div>
      <div>TAHİN HELVA</div>
      <div>Toplam Kalori:</div><div>0</div>
      <div>5 Mayıs</div>
      <div>EZOGELİN ÇORBASI</div>
      <div>FIRIN TAVUK BAGET</div>
      <div>TEREYAĞLI MAKARNA</div>
      <div>AYRAN</div>
      <div>Toplam Kalori:</div><div>0</div>
      <div>19 Mayıs</div><div>Öğün Yok</div>
      <div>20 Mayıs</div>
      <div>ISPANAK GRATEN</div>
      <div>PUDİNG</div>
      <div>SÜZME MERCİMEK ÇORBA</div>
      <div>BOLONEZ SOSLU MAKARNA</div>
      <div>Toplam Kalori:</div><div>0</div>
    </section>
  </body>
</html>
"""


def _menu_data():
    return parse_dining_menu_html(MENU_HTML)


def test_endpoint_style_html_is_parsed_and_duplicate_dates_are_deduplicated():
    result = _menu_data()

    dates = [item["date"] for item in result["items"]]

    assert result["status"] == "ok"
    assert "2026-05-04" in dates
    assert "2026-05-05" in dates
    assert "2026-05-19" in dates
    assert len(dates) == len(set(dates))
    assert result["available_start_date"] == "2026-05-01"
    assert result["available_end_date"] == "2026-05-20"


def test_named_dates_select_only_requested_day():
    data = _menu_data()

    may_4 = select_menu_for_query(data, "4 Mayıs yemekte ne var?", today=date(2026, 5, 4))
    may_5 = select_menu_for_query(data, "5 Mayıs menüsü", today=date(2026, 5, 4))
    may_20 = select_menu_for_query(data, "20 Mayıs yemekte ne var?", today=date(2026, 5, 4))

    assert [item["date"] for item in may_4] == ["2026-05-04"]
    assert "ETLİ NOHUT" in may_4[0]["menu"]
    assert [item["date"] for item in may_5] == ["2026-05-05"]
    assert "AYRAN" in may_5[0]["menu"]
    assert [item["date"] for item in may_20] == ["2026-05-20"]
    assert "ISPANAK GRATEN" in may_20[0]["menu"]


def test_no_meal_day_is_reported_without_inventing_food():
    data = _menu_data()
    selected = select_menu_for_query(data, "19 Mayıs yemekte ne var?", today=date(2026, 5, 4))
    response = format_dining_menu_response(data, "19 Mayıs yemekte ne var?")

    assert selected[0]["date"] == "2026-05-19"
    assert selected[0]["has_meal"] is False
    assert "Öğün Yok" in response
    assert "ETLİ NOHUT" not in response


def test_today_outside_available_dates_is_safe_fallback():
    data = _menu_data()
    detail = select_menu_for_query_details(data, "Bugün yemekte ne var?", today=date(2026, 5, 31))
    response = format_dining_menu_response(data, "Bugün yemekte ne var?")

    assert detail["status"] == "no_menu_for_date"
    assert detail["items"] == []
    assert "uydurulmadı" in response


def test_week_query_is_limited_to_current_week_days():
    data = _menu_data()

    selected = select_menu_for_query(data, "Bu hafta yemekhane menüsü ne?", today=date(2026, 5, 4))

    assert [item["date"] for item in selected] == ["2026-05-04", "2026-05-05"]


def test_ambiguous_weekday_asks_for_date_instead_of_dumping_all_mondays():
    data = _menu_data()

    detail = select_menu_for_query_details(data, "Pazartesi menüsü ne?", today=date(2026, 5, 4))
    response = format_dining_menu_response(data, "Pazartesi menüsü ne?")

    assert detail["status"] == "ambiguous_date"
    assert detail["items"] == []
    assert "tarih de belirtir misin" in response


def test_out_of_range_date_reports_available_range():
    data = _menu_data()

    detail = select_menu_for_query_details(data, "30 Mayıs yemekte ne var?", today=date(2026, 5, 4))

    assert detail["status"] == "no_menu_for_date"
    assert "2026-05-01 - 2026-05-20" in detail["message"]


def test_date_aware_queries_route_to_dynamic_menu_without_breaking_other_modes():
    assert is_dining_menu_query("4 Mayıs yemekte ne var?")
    assert route_query("Bugün yemekte ne var?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("Yarın yemekte ne var?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("4 Mayıs yemekte ne var?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("20 Mayıs yemek listesi ne?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("Bu hafta yemekhane menüsü ne?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("yemekhane ile ilgili kaynaklar nelerdir?").mode == MODE_SOURCE_DISCOVERY
    assert route_query("AKTS nedir?").mode == MODE_RAG
