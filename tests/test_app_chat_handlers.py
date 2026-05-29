from app_chat_handlers import (
    append_assistant_message,
    build_safe_error_message,
    classify_error,
    handle_dynamic_menu_chat,
    handle_source_discovery_chat,
)


def test_append_assistant_message_uses_app_message_schema():
    messages = []

    message = append_assistant_message(
        messages,
        "cevap",
        question="soru",
        docs=["doc"],
        sources_checked=True,
    )

    assert messages == [message]
    assert message == {
        "rol": "assistant",
        "icerik": "cevap",
        "soru": "soru",
        "docs": ["doc"],
        "sources_checked": True,
    }


def test_build_safe_error_message_sanitizes_api_key():
    message, detail = build_safe_error_message(
        RuntimeError("model failed with secret-key"),
        groq_key="secret-key",
    )

    assert "Yapay zeka modeli" in message
    assert "secret-key" not in detail
    assert "[GROQ_API_KEY]" in detail


def test_error_classifier_handles_generic_errors():
    assert classify_error(RuntimeError("plain failure")) == "generic"


def test_dynamic_menu_handler_keeps_safe_parse_error_fallback():
    def fake_fetch():
        return {
            "mode": "dynamic_dining_menu",
            "status": "parse_error",
            "source_url": "https://example.test/menu",
            "source_title": "Menu",
            "fetched_at": "2026-05-27T00:00:00+00:00",
            "items": [],
            "message": "parse failed",
            "diagnostics": {"parsed_item_count": 0},
        }

    result = handle_dynamic_menu_chat("bugun yemekte ne var", fetch_func=fake_fetch)

    assert result.sources_checked is True
    assert result.docs
    assert "uydurulmadi" in result.answer
    assert "Mercimek" not in result.answer


def test_source_discovery_handler_no_match_is_safe():
    def fake_discover(query, db=None):
        return {
            "mode": "source_discovery",
            "query": query,
            "topic": "olmayan konu",
            "total_matches": 0,
            "sources": [],
            "status": "no_match",
        }

    result = handle_source_discovery_chat("olmayan konu kaynak var mi", db=None, discover_func=fake_discover)

    assert result.sources_checked is True
    assert result.docs == []
    assert "güvenilir bir kaynak eşleşmesi bulamadım" in result.answer
    assert "kaynak uydurmadım" in result.answer


def test_helpers_tolerate_empty_values():
    messages = []

    append_assistant_message(messages, "", docs=None, sources_checked=None)
    message, detail = build_safe_error_message(Exception(""))

    assert messages == [{"rol": "assistant", "icerik": ""}]
    assert message
    assert detail == ""
