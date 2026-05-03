"""data_ingestion.py crawler entegrasyonu için birim testleri."""

import pytest
import json

from data_ingestion import filter_already_ingested, load_manifest_urls


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
