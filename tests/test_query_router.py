from query_router import (
    MODE_DYNAMIC_DINING_MENU,
    MODE_RAG,
    MODE_SOURCE_DISCOVERY,
    QueryRoute,
    route_query,
)


def test_source_discovery_routes_are_preserved():
    assert route_query("yemekhane ile ilgili kaynaklar nelerdir").mode == MODE_SOURCE_DISCOVERY
    assert route_query("teknoloji fakültesi ile alakalı kaynak var mı").mode == MODE_SOURCE_DISCOVERY


def test_dynamic_dining_menu_routes_are_preserved():
    assert route_query("bugun yemekte ne var").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("bugün yemekte ne var").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("yemekhane menüsü nedir").mode == MODE_DYNAMIC_DINING_MENU


def test_rag_routes_are_preserved_for_regular_questions():
    assert route_query("AKTS nedir").mode == MODE_RAG
    assert route_query("ALES nedir").mode == MODE_RAG


def test_yemekhane_regulation_is_not_dynamic_menu():
    route = route_query("Yemekhane yönetmeliği var mı?")

    assert route.mode != MODE_DYNAMIC_DINING_MENU
    assert route.mode in {MODE_SOURCE_DISCOVERY, MODE_RAG}


def test_empty_query_defaults_safely_to_rag():
    route = route_query("")

    assert isinstance(route, QueryRoute)
    assert route.mode == MODE_RAG
    assert route.metadata["query_empty"] is True


def test_case_and_turkish_character_variations_work():
    assert route_query("BUGÜN YEMEKTE NE VAR?").mode == MODE_DYNAMIC_DINING_MENU
    assert route_query("KÜTÜPHANE HAKKINDA HANGİ BELGELER VAR?").mode == MODE_SOURCE_DISCOVERY
