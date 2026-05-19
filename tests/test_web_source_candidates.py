import json
from pathlib import Path

from evaluation.audit_web_source_candidates import load_candidates, validate_candidates


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "evaluation" / "web_source_candidates.json"


def test_web_source_candidates_json_is_valid():
    data = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 5


def test_web_source_candidate_ids_are_unique():
    candidates = load_candidates(CANDIDATES_PATH)
    ids = [item["id"] for item in candidates]
    assert len(ids) == len(set(ids))


def test_web_source_candidates_required_fields_and_priorities():
    candidates = load_candidates(CANDIDATES_PATH)
    required = {"id", "title", "url", "category", "priority", "freshness", "ingestion_recommendation", "notes"}
    valid_priorities = {"high", "medium", "low"}
    for candidate in candidates:
        assert required.issubset(candidate)
        assert candidate["priority"] in valid_priorities
        assert candidate["url"].startswith("https://")


def test_expected_candidate_families_exist():
    candidates = load_candidates(CANDIDATES_PATH)
    ids = {item["id"] for item in candidates}
    categories = {item["category"] for item in candidates}
    assert "dynamic_menu" in categories
    assert "teknoloji_fakultesi_yonerge_yonetmelikler" in ids
    assert "sks_beslenme_hizmetleri" in ids
    assert "ogrenci_duyurulari" in ids


def test_audit_script_summary_fields_are_produced():
    report = validate_candidates(load_candidates(CANDIDATES_PATH))
    assert report["total_candidates"] >= 5
    assert report["high_priority_count"] >= 4
    assert report["dynamic_source_count"] >= 1
    assert report["static_ingestion_candidate_count"] >= 2
    assert report["announcement_candidate_count"] >= 1
    assert report["missing_required_fields_count"] == 0
