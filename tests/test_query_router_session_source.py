from query_router import MODE_DYNAMIC_DINING_MENU, MODE_RAG, MODE_SESSION_UPLOAD_RAG, MODE_SOURCE_DISCOVERY, route_query


def test_active_session_source_routes_regular_question_to_session_rag():
    route = route_query("Bu belgede başvuru nereye yapılır?", has_active_session_source=True)

    assert route.mode == MODE_SESSION_UPLOAD_RAG


def test_session_source_does_not_override_source_discovery_or_dynamic_menu():
    assert route_query("Staj yönergesi var mı?", has_active_session_source=True).mode == MODE_SOURCE_DISCOVERY
    assert route_query("Bugün yemekte ne var?", has_active_session_source=True).mode == MODE_DYNAMIC_DINING_MENU


def test_session_source_toggle_off_or_general_request_routes_to_rag():
    assert route_query("AKTS nedir?", has_active_session_source=True, session_source_enabled=False).mode == MODE_RAG
    assert route_query("AKTS nedir? Genel Selçuk kaynaklarında ara", has_active_session_source=True).mode == MODE_RAG
