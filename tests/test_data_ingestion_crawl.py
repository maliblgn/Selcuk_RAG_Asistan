"""data_ingestion.py crawler entegrasyonu için birim testleri."""

import pytest
import json
import sys
import types

from data_ingestion import filter_already_ingested, load_manifest_urls, _load_local_pdf_documents


class TestFilterAlreadyIngested:
    def test_filters_existing_urls(self):
        urls = [
            "https://selcuk.edu.tr/page1",
            "https://selcuk.edu.tr/page2",
            "https://selcuk.edu.tr/page3",
        ]
        existing = {"https://selcuk.edu.tr/page1", "https://selcuk.edu.tr/page3"}

        result = filter_already_ingested(urls, existing)

        assert result == ["https://selcuk.edu.tr/page2"]

    def test_returns_all_when_none_exist(self):
        urls = ["https://selcuk.edu.tr/a", "https://selcuk.edu.tr/b"]
        existing = set()

        result = filter_already_ingested(urls, existing)

        assert result == urls

    def test_returns_empty_when_all_exist(self):
        urls = ["https://selcuk.edu.tr/a"]
        existing = {"https://selcuk.edu.tr/a"}

        result = filter_already_ingested(urls, existing)

        assert result == []


class TestManifestAuthorizedSources:
    def test_skips_permission_sources_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AUTHORIZED_SOURCE_MODE", raising=False)
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({
            "known_direct_sources": [
                {
                    "id": "safe",
                    "url": "https://yemek.selcuk.edu.tr/Menu/MenuGetir",
                    "active": True,
                },
                {
                    "id": "permission",
                    "url": "https://webadmin.selcuk.edu.tr/file.pdf",
                    "active": False,
                    "requires_permission": True,
                },
            ]
        }), encoding="utf-8")

        assert load_manifest_urls(str(manifest)) == [
            "https://yemek.selcuk.edu.tr/Menu/MenuGetir"
        ]

    def test_includes_permission_sources_when_authorized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTHORIZED_SOURCE_MODE", "true")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({
            "known_direct_sources": [
                {
                    "id": "safe",
                    "url": "https://yemek.selcuk.edu.tr/Menu/MenuGetir",
                    "active": True,
                },
                {
                    "id": "permission",
                    "url": "https://webadmin.selcuk.edu.tr/file.pdf",
                    "active": False,
                    "requires_permission": True,
                },
            ]
        }), encoding="utf-8")

        assert load_manifest_urls(str(manifest)) == [
            "https://yemek.selcuk.edu.tr/Menu/MenuGetir",
            "https://webadmin.selcuk.edu.tr/file.pdf",
        ]


class TestLocalPdfIngestion:
    def test_loads_local_pdf_pages_with_metadata(self, tmp_path, monkeypatch):
        pdf_dir = tmp_path / "manual_pdfs"
        pdf_dir.mkdir()
        pdf_path = pdf_dir / "ornek.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")

        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, path):
                assert str(path).endswith("ornek.pdf")
                self.pages = [
                    FakePage("MADDE 1 - Birinci sayfa"),
                    FakePage(""),
                    FakePage("MADDE 2 - Ucuncu sayfa"),
                ]

        monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=FakeReader))

        docs = _load_local_pdf_documents(str(pdf_dir))

        assert len(docs) == 2
        assert docs[0].page_content == "MADDE 1 - Birinci sayfa"
        assert docs[0].metadata["source"].endswith("ornek.pdf")
        assert docs[0].metadata["title"] == "ornek"
        assert docs[0].metadata["source_type"] == "local_pdf"
        assert docs[0].metadata["doc_type"] == "manual_pdf"
        assert docs[0].metadata["page"] == 1
        assert docs[0].metadata["total_pages"] == 3
        assert docs[0].metadata["extraction_method"] == "local_pdf_pypdf"
        assert docs[1].metadata["page"] == 3
