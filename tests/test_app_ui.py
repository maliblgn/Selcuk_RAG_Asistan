from types import SimpleNamespace

from app_ui import APP_NAME, NAV_ITEMS, recent_user_questions, route_badge_for_message, session_source_label


def test_branding_uses_selcuk_ai():
    assert APP_NAME == "Selçuk-AI"


def test_navigation_contains_required_pages():
    pages = {page for page, _label, _icon in NAV_ITEMS}

    assert {"chat", "sources", "dashboard", "ai_tools", "admin", "hakkinda"}.issubset(pages)


def test_recent_user_questions_are_short_and_ordered():
    messages = [
        {"rol": "user", "icerik": "AKTS nedir?"},
        {"rol": "assistant", "icerik": "Cevap"},
        {"rol": "user", "icerik": "Teknoloji Fakültesi staj kaynakları nelerdir?"},
    ]

    assert recent_user_questions(messages, limit=2) == [
        "Teknoloji Fakültesi staj kaynakları nelerdir?",
        "AKTS nedir?",
    ]


def test_session_source_label_handles_missing_and_ready_source():
    assert session_source_label(None) == "Geçici kaynak yok"

    source = SimpleNamespace(source_label="PDF: deneme.pdf", title="deneme.pdf", status="ready")
    assert session_source_label(source) == "PDF: deneme.pdf · ready"


def test_route_badge_detects_session_source_doc():
    doc = SimpleNamespace(metadata={"source_type": "pdf_url", "session_source_id": "s1"})
    assert route_badge_for_message({"docs": [doc]}) == "Geçici Kaynak"


def test_route_badge_detects_source_checked_fallback():
    assert route_badge_for_message({"sources_checked": True}) == "Kaynak Kontrolü"
