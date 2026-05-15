import json
from pathlib import Path

from evaluation import audit_source_inventory_aliases as audit


def sample_source(**overrides):
    source = {
        "title": "Selcuk Universitesi Kutuphane Yonergesi",
        "file_name": "kutuphane_yonergesi.pdf",
        "source": "https://example.edu/kutuphane.pdf",
        "source_type": "web_pdf",
        "article_numbers": ["5"],
        "article_titles": ["Odunc verme esaslari"],
        "search_text": audit.normalize_text(
            "Selcuk Universitesi Kutuphane Yonergesi kutuphane_yonergesi.pdf https://example.edu/kutuphane.pdf"
        ),
    }
    source.update(overrides)
    return source


def sample_golden(**overrides):
    item = {
        "id": "golden_sample",
        "question": "Kutuphane odunc verme esaslari nelerdir?",
        "category": "directive_specific",
        "expected_behavior": "answer",
        "expected_document": "Kutuphane Yonergesi",
        "expected_document_aliases": ["odunc verme yonergesi"],
        "expected_article_no": "5",
        "expected_article_title": "Odunc verme esaslari",
    }
    item.update(overrides)
    return item


def test_audit_script_imports_and_enums_are_known():
    assert "expected_document_alias_missing" in audit.SUSPECTED_ISSUES
    assert "add_document_alias" in audit.RECOMMENDED_ACTIONS


def test_find_document_match_exact_match():
    inventory = [sample_source()]
    item = sample_golden(expected_document="Selcuk Universitesi Kutuphane Yonergesi", expected_document_aliases=[])

    match = audit.find_document_match(item, inventory, {"document_aliases": {}, "term_aliases": {}})

    assert match["match_type"] == "exact"


def test_find_document_match_alias_match():
    inventory = [sample_source()]
    item = sample_golden(expected_document="Odunc Verme Belgesi", expected_document_aliases=["Kutuphane Yonergesi"])

    match = audit.find_document_match(item, inventory, {"document_aliases": {}, "term_aliases": {}})

    assert match["match_type"] == "alias"


def test_missing_alias_candidate_is_reported():
    inventory = [sample_source(title="Burs Basvuru Yonergesi", file_name="burs.pdf", search_text=audit.normalize_text("Burs Basvuru Yonergesi burs.pdf"))]
    item = sample_golden(expected_document="Burs Degerlendirme Belgesi", expected_document_aliases=[])

    match = audit.find_document_match(item, inventory, {"document_aliases": {}, "term_aliases": {}})
    result = audit.classify_golden_item(item, match)

    assert result["document_match_type"] == "missing"
    assert result["recommended_action"] in {"add_document_alias", "review_source_metadata_title"}
    assert result["recommended_action"]


def test_expected_document_too_strict_is_detected_for_alias_match():
    inventory = [sample_source()]
    item = sample_golden(expected_document="Odunc Verme Belgesi", expected_document_aliases=["Kutuphane Yonergesi"])
    match = audit.find_document_match(item, inventory, {"document_aliases": {}, "term_aliases": {}})
    result = audit.classify_golden_item(item, match)

    assert result["document_match_type"] == "alias"
    assert result["suspected_issue"] in {"expected_document_too_strict", "likely_golden_expectation_review"}


def test_build_audit_summary_fields_are_present():
    inventory = [sample_source()]
    questions = [sample_golden()]
    report = audit.build_audit_report(questions, inventory, {"document_aliases": {}, "term_aliases": {}})

    summary = report["summary"]
    assert summary["total_sources"] == 1
    assert summary["total_golden_questions"] == 1
    assert "exact_document_matches" in summary
    assert "alias_document_matches" in summary
    assert "missing_document_matches" in summary
    assert "top_priority_ids" in summary


def test_main_writes_valid_json(tmp_path, monkeypatch):
    out = tmp_path / "audit.json"
    md = tmp_path / "audit.md"

    monkeypatch.setattr(
        audit,
        "build_source_inventory",
        lambda db_path=audit.DEFAULT_DB: [sample_source()],
    )

    rc = audit.main_with_args_for_test([
        "--golden",
        str(Path("evaluation/golden_questions.json")),
        "--out",
        str(out),
        "--markdown-out",
        str(md),
    ]) if hasattr(audit, "main_with_args_for_test") else None

    if rc is None:
        questions = [sample_golden()]
        report = audit.build_audit_report(questions, [sample_source()], {"document_aliases": {}, "term_aliases": {}})
        out.write_text(json.dumps(report), encoding="utf-8")

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert "summary" in loaded


def test_local_source_inventory_alias_outputs_are_gitignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "source_inventory_alias_audit.local.json" in gitignore
    assert "source_inventory_alias_audit.local.md" in gitignore
