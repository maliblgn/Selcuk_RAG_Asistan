from dataclasses import asdict

from dynamic_sources.base import DynamicSourceHealth, DynamicSourceResult
from dynamic_sources.health import get_safe_dynamic_source_health_summary
from dynamic_sources.registry import get_dynamic_source_readers, route_dynamic_source
from query_router import MODE_SOURCE_DISCOVERY, route_query


def test_registry_contains_dining_menu_reader():
    readers = get_dynamic_source_readers()

    assert readers
    assert readers[0].reader_id == "dining_menu"
    assert readers[0].mode == "dynamic_dining_menu"


def test_dynamic_source_routes_dining_menu_query():
    route = route_dynamic_source("bugun yemekte ne var")

    assert route is not None
    assert route.mode == "dynamic_dining_menu"
    assert route.reader_id == "dining_menu"


def test_dynamic_source_does_not_route_regular_rag_query():
    assert route_dynamic_source("AKTS nedir") is None


def test_source_discovery_priority_is_preserved_for_yemekhane_sources():
    query = "yemekhane ile ilgili kaynaklar nelerdir"

    assert route_dynamic_source(query) is None
    assert route_query(query).mode == MODE_SOURCE_DISCOVERY


def test_dynamic_source_health_summary_is_secret_safe():
    summary = get_safe_dynamic_source_health_summary()
    joined = str(summary).lower()

    assert summary["total_readers"] >= 1
    assert "dining_menu" in summary["reader_ids"]
    assert "api_key" not in joined
    assert "token" not in joined


def test_result_and_health_dataclasses_convert_to_dict():
    result = DynamicSourceResult(
        source_id="test",
        mode="dynamic_test",
        status="ok",
        source_url="https://example.test",
        items=[{"name": "item"}],
    )
    health = DynamicSourceHealth(source_id="test", mode="dynamic_test")

    assert result.to_dict() == asdict(result)
    assert health.to_dict() == asdict(health)


def test_empty_query_does_not_raise():
    assert route_dynamic_source("") is None
    assert route_dynamic_source(None) is None
