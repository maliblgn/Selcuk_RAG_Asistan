import json
from pathlib import Path

from evaluation import evaluate_retrieval
from retrieval_normalization import (
    article_metadata_score,
    extract_article_numbers,
    normalize_article_no,
    normalize_article_title,
)


def test_normalize_article_no_handles_common_formats():
    assert normalize_article_no("MADDE 43 - Doktora yeterlik sinavi") == "43"
    assert normalize_article_no("43 uncu madde") == "43"
    assert normalize_article_no("43. madde") == "43"
    assert normalize_article_no("MADDE-43") == "43"


def test_extract_article_numbers_reads_madde_phrases():
    assert "44" in extract_article_numbers("MADDE 44 - Tez izleme komitesi")
    assert "12" in extract_article_numbers("12 nci madde kapsaminda")


def test_normalize_article_title_removes_article_prefix():
    assert normalize_article_title("MADDE 43 - Doktora yeterlik sinavi") == "doktora yeterlik sinavi"
    assert normalize_article_title("43 uncu madde Basari notu") == "basari notu"


def test_article_metadata_score_prefers_correct_number_and_title():
    score = article_metadata_score("43", "Doktora yeterlik sinavi", "MADDE 43", "Doktora yeterlik sinavi", "")
    assert score >= 8.0


def test_article_metadata_score_stays_low_for_wrong_number():
    score = article_metadata_score("43", "Doktora yeterlik sinavi", "44", "Tez izleme komitesi", "")
    assert score < 3.0


def test_article_metadata_score_uses_content_title_support():
    score = article_metadata_score(
        "43",
        "Doktora yeterlik sinavi",
        "",
        "",
        "MADDE 43 Doktora yeterlik sinavi esaslari burada duzenlenir.",
    )
    assert score >= 5.0


def test_evaluate_retrieval_article_hit_tolerates_article_no_format():
    docs = [
        {
            "metadata": {"article_no": "MADDE 43", "article_title": "Doktora yeterlik sinavi"},
            "content": "Doktora yeterlik sinavi hakkinda hukumler.",
        }
    ]
    item = {"expected_article_no": "43", "expected_article_title": "Doktora yeterlik sinavi"}

    assert evaluate_retrieval._article_hit(docs, item, 1) is True


def test_article_matching_has_no_golden_id_specific_hardcode():
    files = [
        Path("retrieval_normalization.py"),
        Path("evaluation/audit_article_metadata.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    golden_ids = [item["id"] for item in json.loads(Path("evaluation/golden_questions.json").read_text(encoding="utf-8"))]

    assert not any(f'"{item_id}"' in combined or f"'{item_id}'" in combined for item_id in golden_ids)
