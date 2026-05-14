import json
from pathlib import Path

from retrieval_normalization import (
    article_match_score,
    load_retrieval_aliases,
    normalize_ascii_lite,
    normalize_text,
    title_similarity_score,
    tokenize_for_match,
)


def test_url_encoded_title_is_decoded_and_normalized():
    assert "lisansustu" in normalize_text("L%C4%B0SANS%C3%9CST%C3%9C.pdf")


def test_turkish_and_ascii_lite_text_can_match():
    assert normalize_ascii_lite("Çift Ana Dal Yönergesi") == "cift ana dal yonergesi"
    assert "kutuphane" in normalize_ascii_lite("Kütüphane Yönergesi")


def test_normalize_text_cleans_spacing_and_punctuation():
    assert normalize_text("  Burs,   Yönergesi!!! ") == "burs yonergesi"


def test_tokenize_for_match_removes_short_tokens():
    assert "akts" in tokenize_for_match("AKTS nedir")
    assert "ne" not in tokenize_for_match("AKTS ne")


def test_title_similarity_score_uses_aliases():
    no_alias = title_similarity_score("odunc verme", "SELÇUK ÜNİVERSİTESİ KÜTÜPHANE YÖNERGESİ")
    with_alias = title_similarity_score(
        "odunc verme",
        "SELÇUK ÜNİVERSİTESİ KÜTÜPHANE YÖNERGESİ",
        aliases=["odunc verme yonergesi"],
    )

    assert with_alias > no_alias


def test_article_match_score_matches_article_no_and_title():
    score = article_match_score("Madde 5 basvuru ve degerlendirme", "5", "Başvuru ve değerlendirme", "")

    assert score >= 6.0


def test_alias_config_loads():
    aliases = load_retrieval_aliases()

    assert "term_aliases" in aliases
    assert "document_aliases" in aliases
    assert "akts" in aliases["term_aliases"]


def test_missing_alias_config_returns_empty_dict(tmp_path):
    aliases = load_retrieval_aliases(tmp_path / "missing.json")

    assert aliases == {"term_aliases": {}, "document_aliases": {}}


def test_alias_config_is_not_question_id_based():
    aliases_text = Path("config/retrieval_aliases.json").read_text(encoding="utf-8")
    aliases = json.loads(aliases_text)

    assert "golden_" not in aliases_text
    assert all(not key.startswith("golden_") for key in aliases.get("term_aliases", {}))
    assert all(not key.startswith("golden_") for key in aliases.get("document_aliases", {}))
