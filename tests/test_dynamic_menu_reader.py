import json

import pytest

from dynamic_menu_reader import (
    fetch_dining_menu,
    format_dining_menu_response,
    is_dining_menu_query,
)
from evaluation.evaluate_dynamic_menu import build_report, load_questions


def test_dining_menu_intent_positive_examples():
    assert is_dining_menu_query("bugün yemekte ne var")
    assert is_dining_menu_query("yemekhane menüsü nedir")
    assert is_dining_menu_query("aylık yemek listesi")


def test_dining_menu_intent_negative_examples():
    assert not is_dining_menu_query("Yemekhane ile ilgili kaynaklar nelerdir")
    assert not is_dining_menu_query("Yemekhane yönetmeliği var mı?")
    assert not is_dining_menu_query("Yemek bursu yönergesi var mı?")
    assert not is_dining_menu_query("AKTS nedir")


def test_fetch_failure_returns_safe_unavailable(monkeypatch):
    def fake_get(*args, **kwargs):
        raise TimeoutError("network down")

    monkeypatch.setattr("dynamic_menu_reader.requests.get", fake_get)

    result = fetch_dining_menu(use_cache=False)

    assert result["mode"] == "dynamic_dining_menu"
    assert result["status"] == "unavailable"
    assert result["items"] == []


def test_parse_error_response_does_not_invent_menu():
    response = format_dining_menu_response({
        "mode": "dynamic_dining_menu",
        "status": "parse_error",
        "items": [],
        "source_title": "Test",
        "fetched_at": "2026-01-01T00:00:00+00:00",
    })

    assert "uydurulmadi" in response.lower()
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
    }, "bugün yemekte ne var")

    assert "Corba" in response
    assert "Kaynak: Test Menu" in response


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


def test_dynamic_menu_questions_json_is_valid():
    with open("evaluation/dynamic_menu_smoke_questions.json", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, list)
    assert all("id" in item and "query" in item for item in data)
