import json
from unittest.mock import MagicMock

import check_chroma_health
import rag_engine


def test_missing_db_path_returns_missing(tmp_path):
    report = check_chroma_health.check_chroma_health(tmp_path / "missing")

    assert report["status"] == "missing"
    assert report["ok"] is False
    assert report["db_exists"] is False


def test_missing_sqlite_returns_missing_sqlite(tmp_path):
    db_path = tmp_path / "chroma_db"
    db_path.mkdir()

    report = check_chroma_health.check_chroma_health(db_path)

    assert report["status"] == "missing_sqlite"
    assert report["ok"] is False
    assert report["sqlite_exists"] is False


def test_collection_error_returns_collection_missing(tmp_path, monkeypatch):
    db_path = tmp_path / "chroma_db"
    db_path.mkdir()
    (db_path / "chroma.sqlite3").write_text("", encoding="utf-8")

    def broken_chroma(*args, **kwargs):
        raise RuntimeError("Error getting collection: Collection [abc-123] does not exist.")

    monkeypatch.setattr(check_chroma_health, "Chroma", broken_chroma)

    report = check_chroma_health.check_chroma_health(db_path)

    assert report["status"] == "collection_missing"
    assert report["collection_readable"] is False
    assert "abc-123" in report["error"]


def test_health_json_format_has_expected_fields(tmp_path, monkeypatch):
    db_path = tmp_path / "chroma_db"
    db_path.mkdir()
    (db_path / "chroma.sqlite3").write_text("", encoding="utf-8")
    fake_collection = MagicMock()
    fake_collection.count.return_value = 2
    fake_collection.get.return_value = {
        "metadatas": [
            {"source": "a.pdf", "source_type": "web_pdf"},
            {"source": "b", "source_type": "web_page"},
        ]
    }
    fake_db = MagicMock()
    fake_db._collection = fake_collection
    monkeypatch.setattr(check_chroma_health, "Chroma", MagicMock(return_value=fake_db))

    report = check_chroma_health.check_chroma_health(db_path)
    payload = json.loads(json.dumps(report))

    assert payload["status"] == "ok"
    assert payload["document_count"] == 2
    assert payload["unique_source_count"] == 2
    assert payload["source_type_counts"] == {"web_pdf": 1, "web_page": 1}


def test_chroma_collection_uuid_error_is_detected():
    error = "Error getting collection: Collection [008ae1a6-e807] does not exist."

    assert rag_engine.is_chroma_collection_error(error)


def test_knowledge_base_error_uses_safe_user_message():
    health = {
        "status": "collection_missing",
        "error": "Error getting collection: Collection [008ae1a6-e807] does not exist.",
    }
    error = rag_engine.KnowledgeBaseUnavailableError(health=health)

    assert error.user_message == rag_engine.LIVE_INDEX_UNAVAILABLE_MESSAGE
    assert "008ae1a6" in str(error)
    assert "008ae1a6" not in error.user_message
