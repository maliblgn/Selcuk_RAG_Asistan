import json
from pathlib import Path

from evaluation.audit_technology_faculty_sources import load_sources, validate_sources


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "evaluation" / "technology_faculty_sources.json"


def test_technology_faculty_sources_json_is_valid():
    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 6


def test_technology_faculty_source_ids_are_unique():
    sources = load_sources(SOURCES_PATH)
    ids = [source["id"] for source in sources]
    assert len(ids) == len(set(ids))


def test_technology_faculty_sources_required_fields_and_priorities():
    sources = load_sources(SOURCES_PATH)
    required = {
        "id",
        "title",
        "url",
        "source_owner",
        "category",
        "source_type",
        "priority",
        "freshness",
        "expected_topics",
        "ingestion_recommendation",
        "notes",
    }
    valid_priorities = {"high", "medium", "low"}
    for source in sources:
        assert required.issubset(source)
        assert source["priority"] in valid_priorities
        assert source["url"].startswith("https://")
        assert source["expected_topics"]


def test_technology_faculty_coverage_families_exist():
    report = validate_sources(load_sources(SOURCES_PATH))
    coverage = report["coverage"]
    assert coverage["has_staj_source"] is True
    assert coverage["has_ime_source"] is True
    assert coverage["has_regulation_index"] is True
    assert coverage["has_faq_source"] is True
    assert coverage["has_forms_or_workflow_source"] is True


def test_technology_faculty_audit_summary_fields_are_produced():
    report = validate_sources(load_sources(SOURCES_PATH))
    assert report["total_sources"] >= 6
    assert report["high_priority_count"] >= 4
    assert report["pdf_candidate_count"] >= 2
    assert report["web_page_candidate_count"] >= 4
    assert report["expected_topic_count"] >= 10
    assert report["missing_required_fields_count"] == 0
    assert report["dynamic_static_mismatch_count"] == 0
