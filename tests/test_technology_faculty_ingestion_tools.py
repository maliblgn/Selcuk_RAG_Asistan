import json
from pathlib import Path

from evaluation.evaluate_source_discovery import evaluate_question, load_questions
from tools.ingest_technology_faculty_sources import fetch_source_documents
from tools.preflight_technology_faculty_sources import check_source


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "evaluation" / "source_discovery_smoke_questions.json"


class FakeDb:
    def get(self, include=None):
        return {
            "documents": [
                "Teknoloji Fakultesi Staj Uygulama Yonergesi staj esaslarini aciklar.",
                "Teknoloji Fakultesi Isletmede Mesleki Egitim kaynaklari ve IME yonergesi.",
            ],
            "metadatas": [
                {
                    "source": "https://example.edu/staj.pdf",
                    "title": "Teknoloji Fakultesi Staj Uygulama Yonergesi",
                    "source_type": "web_pdf",
                    "source_family": "technology_faculty",
                    "expected_topics_text": "staj",
                },
                {
                    "source": "https://example.edu/ime",
                    "title": "Teknoloji Fakultesi Isletmede Mesleki Egitim",
                    "source_type": "web_page",
                    "source_family": "technology_faculty",
                    "expected_topics_text": "isletmede mesleki egitim, ime",
                },
            ],
        }


def test_source_discovery_smoke_questions_schema_is_valid():
    questions = load_questions(QUESTIONS_PATH)
    assert len(questions) >= 3
    for item in questions:
        assert item["expected_mode"] == "source_discovery"
        assert item["expected_min_matches"] >= 1
        assert item["expected_terms"]


def test_evaluate_source_discovery_question_with_fake_db_passes():
    question = {
        "id": "sample",
        "query": "teknoloji fakültesi staj yönergesi var mı",
        "expected_mode": "source_discovery",
        "expected_min_matches": 1,
        "expected_terms": ["staj"],
    }
    result = evaluate_question(question, FakeDb())
    assert result["status"] == "ok"
    assert result["mode_detected"] == "source_discovery"
    assert result["total_matches"] >= 1


def test_preflight_check_source_can_be_mocked(monkeypatch):
    class Response:
        status_code = 200
        url = "https://selcuk.edu.tr/sample"
        headers = {"content-type": "text/html; charset=utf-8"}
        text = "<html><head><title>Teknoloji Fakultesi</title></head><body>Kaynak metni</body></html>"
        content = text.encode("utf-8")

    monkeypatch.setattr(
        "tools.preflight_technology_faculty_sources._request_with_ssl_fallback",
        lambda *args, **kwargs: Response(),
    )
    source = {
        "id": "sample",
        "title": "Sample",
        "url": "https://selcuk.edu.tr/sample",
        "priority": "high",
        "source_type": "web_page",
        "ingestion_recommendation": "static_web_ingestion_candidate",
        "freshness": "slow_changing",
    }
    result = check_source(source)
    assert result["ok"] is True
    assert result["is_html"] is True


def test_fetch_source_documents_html_can_be_mocked(monkeypatch):
    class Response:
        status_code = 200
        url = "https://selcuk.edu.tr/sample"
        headers = {"content-type": "text/html; charset=utf-8"}
        text = "<html><head><title>Teknoloji Fakultesi</title></head><body><main>" + ("staj " * 100) + "</main></body></html>"
        content = text.encode("utf-8")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "tools.ingest_technology_faculty_sources._request_with_ssl_fallback",
        lambda *args, **kwargs: Response(),
    )
    source = {
        "id": "sample",
        "title": "Sample",
        "url": "https://selcuk.edu.tr/sample",
        "source_owner": "Teknoloji Fakultesi",
        "category": "faculty_regulations",
        "source_type": "web_page",
        "priority": "high",
        "freshness": "slow_changing",
        "expected_topics": ["staj"],
        "ingestion_recommendation": "static_web_ingestion_candidate",
    }
    docs = fetch_source_documents(source)
    assert docs
    assert docs[0].metadata["source_family"] == "technology_faculty"
    assert docs[0].metadata["source_id"] == "sample"
