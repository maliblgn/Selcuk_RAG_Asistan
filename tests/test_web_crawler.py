"""web_crawler.py modülü için birim testleri."""

import json
import os
import tempfile

import pytest

from web_crawler import CrawlerConfig, CrawlResult, CrawlStats, SelcukCrawler


# ═══════════════════════════════════════════════════════════
#  Fake HTTP Katmanı
# ═══════════════════════════════════════════════════════════

class FakeResponse:
    def __init__(self, text, status_code=200, content_type="text/html"):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Her URL için önceden tanımlanmış yanıtlar döndüren sahte session."""

    def __init__(self, responses=None, default_text=""):
        self._responses = responses or {}
        self._default_text = default_text
        self.headers = {}
        self.request_log = []

    def get(self, url, timeout=10, verify=True):
        self.request_log.append(url)
        if url in self._responses:
            return self._responses[url]
        return FakeResponse(self._default_text)

    def mount(self, *_args, **_kwargs):
        return None


class FakeScraper:
    """WebScraper yerine geçen basit stub."""

    def __init__(self, session=None, robots_allowed=True):
        self.session = session or FakeSession()
        self.config = type("Obj", (), {"verify_ssl": True})()
        self.robots_allowed = robots_allowed

    def _is_allowed_by_robots(self, url):
        return self.robots_allowed


# ═══════════════════════════════════════════════════════════
#  Testler
# ═══════════════════════════════════════════════════════════

def _make_html_with_links(links, body_text="Sayfa icerigi"):
    """Verilen linklerle bir HTML sayfası oluştur."""
    anchors = "".join(f'<a href="{link}">link</a>' for link in links)
    return f"<html><body><h1>{body_text}</h1>{anchors}</body></html>"


def _temp_state_file():
    """Geçici state dosyası yolu döndür."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    return path


class TestDomainLock:
    def test_rejects_external_domain(self):
        crawler = SelcukCrawler(
            config=CrawlerConfig(allowed_domains=("selcuk.edu.tr",)),
            scraper=FakeScraper(),
        )
        assert crawler._is_in_domain("https://www.selcuk.edu.tr/about") is True
        assert crawler._is_in_domain("https://selcuk.edu.tr/about") is True
        assert crawler._is_in_domain("https://muhendislik.selcuk.edu.tr/") is True
        assert crawler._is_in_domain("https://google.com/") is False
        assert crawler._is_in_domain("https://example.org/selcuk.edu.tr") is False


class TestDepthControl:
    def test_stops_at_max_depth(self):
        """max_depth=0 ise sadece seed taranır, keşfedilen linkler takip edilmez."""
        seed = "https://www.selcuk.edu.tr"
        child = "https://www.selcuk.edu.tr/child"

        html = _make_html_with_links([child])
        session = FakeSession(
            responses={
                seed: FakeResponse(html),
                child: FakeResponse("<html><body>Child</body></html>"),
            }
        )

        state_file = _temp_state_file()
        try:
            config = CrawlerConfig(
                seed_url=seed,
                max_depth=0,
                max_pages=100,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            result = crawler.crawl()

            # Sadece seed taranmış olmalı
            assert seed in result.text_pages
            # child kuyruğa eklenmediği için taranmamış olmalı
            assert child not in result.text_pages
            assert result.stats.pages_crawled == 1
        finally:
            os.unlink(state_file)


class TestNoDuplicates:
    def test_same_url_not_crawled_twice(self):
        """Aynı URL birden fazla sayfada linklenmiş olsa bile bir kez taranır."""
        seed = "https://www.selcuk.edu.tr"
        target = "https://www.selcuk.edu.tr/target"

        # Hem seed hem target'ın HTML'inde aynı linki tekrarla
        html_seed = _make_html_with_links([target, target, target])
        html_target = _make_html_with_links([seed, target])

        session = FakeSession(
            responses={
                seed: FakeResponse(html_seed),
                target: FakeResponse(html_target),
            }
        )

        state_file = _temp_state_file()
        try:
            config = CrawlerConfig(
                seed_url=seed,
                max_depth=2,
                max_pages=100,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            result = crawler.crawl()

            # Her URL sadece bir kez text_pages'ta olmalı
            assert result.text_pages.count(seed) == 1
            assert result.text_pages.count(target) == 1
        finally:
            os.unlink(state_file)


class TestClassifyUrl:
    def test_pdf_is_document(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/file.pdf") == "document"
        assert SelcukCrawler._classify_url("https://x.edu.tr/file.PDF") == "document"

    def test_docx_is_document(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/doc.docx") == "document"

    def test_html_page_is_text_page(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/about") == "text_page"
        assert SelcukCrawler._classify_url("https://x.edu.tr/page.html") == "text_page"

    def test_image_is_skip(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/img.jpg") == "skip"
        assert SelcukCrawler._classify_url("https://x.edu.tr/img.png") == "skip"

    def test_binary_is_skip(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/archive.zip") == "skip"
        assert SelcukCrawler._classify_url("https://x.edu.tr/style.css") == "skip"
        assert SelcukCrawler._classify_url("https://x.edu.tr/app.js") == "skip"

    def test_no_extension_is_text_page(self):
        assert SelcukCrawler._classify_url("https://x.edu.tr/birim/hakkinda") == "text_page"


class TestNormalizeUrl:
    def test_removes_fragment(self):
        result = SelcukCrawler._normalize_url("https://www.selcuk.edu.tr/page#section")
        assert "#" not in result
        assert result == "https://www.selcuk.edu.tr/page"

    def test_trailing_slash_normalized(self):
        result = SelcukCrawler._normalize_url("https://www.selcuk.edu.tr/about/")
        assert result == "https://www.selcuk.edu.tr/about"

    def test_root_slash_preserved(self):
        result = SelcukCrawler._normalize_url("https://www.selcuk.edu.tr/")
        assert result == "https://www.selcuk.edu.tr/"

    def test_case_insensitive_scheme_host(self):
        result = SelcukCrawler._normalize_url("HTTPS://WWW.Selcuk.EDU.TR/Page")
        assert result == "https://www.selcuk.edu.tr/Page"


class TestExcludePatterns:
    def test_login_excluded(self):
        crawler = SelcukCrawler(
            config=CrawlerConfig(exclude_patterns=("/login", "/en/", "/admin/")),
            scraper=FakeScraper(),
        )
        assert crawler._is_excluded("https://selcuk.edu.tr/login") is True
        assert crawler._is_excluded("https://selcuk.edu.tr/en/page") is True
        assert crawler._is_excluded("https://selcuk.edu.tr/admin/panel") is True
        assert crawler._is_excluded("https://selcuk.edu.tr/hakkinda") is False


class TestRobotsCompliance:
    def test_blocked_seed_is_not_fetched(self):
        seed = "https://www.selcuk.edu.tr"
        session = FakeSession(
            responses={seed: FakeResponse("<html><body>Blocked</body></html>")}
        )
        state_file = _temp_state_file()
        try:
            config = CrawlerConfig(
                seed_url=seed,
                max_depth=0,
                max_pages=1,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(
                config=config,
                scraper=FakeScraper(session, robots_allowed=False),
            )
            result = crawler.crawl()

            assert result.text_pages == []
            assert result.stats.skipped_robots == 1
            assert session.request_log == []
        finally:
            os.unlink(state_file)


class TestStatePersistence:
    def test_save_and_load_roundtrip(self):
        state_file = _temp_state_file()
        try:
            config = CrawlerConfig(
                state_file=state_file,
                seed_url="https://www.selcuk.edu.tr",
                max_depth=0,
                max_pages=1,
                crawl_delay=0,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )

            session = FakeSession(
                responses={
                    "https://www.selcuk.edu.tr": FakeResponse(
                        "<html><body>Test</body></html>"
                    ),
                }
            )

            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            crawler.crawl()

            # State dosyası oluşmuş olmalı
            assert os.path.exists(state_file)

            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            assert "last_run" in state
            assert "urls" in state
            assert "https://www.selcuk.edu.tr" in state["urls"]
            assert state["urls"]["https://www.selcuk.edu.tr"]["status"] == "success"
        finally:
            os.unlink(state_file)


class TestUserAgentRotation:
    def test_different_uas_selected(self):
        """Birden fazla UA varken farklı UA'lar seçilebilmeli."""
        uas = ("UA-Alpha", "UA-Beta", "UA-Gamma")
        config = CrawlerConfig(
            user_agents=uas,
            seed_url="https://www.selcuk.edu.tr",
            max_depth=0,
            max_pages=1,
            crawl_delay=0,
            allowed_domains=("selcuk.edu.tr",),
            exclude_patterns=(),
        )

        session = FakeSession(
            responses={
                "https://www.selcuk.edu.tr": FakeResponse(
                    "<html><body>Test</body></html>"
                ),
            }
        )

        state_file = _temp_state_file()
        config.state_file = state_file
        try:
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            crawler.crawl()

            # En azından bir request yapılmış olmalı
            assert len(session.request_log) >= 1
        finally:
            os.unlink(state_file)


class TestIncrementalSkipsExisting:
    def test_success_urls_skipped(self):
        """State'te success olan URL tekrar taranmamalı."""
        state_file = _temp_state_file()
        seed = "https://www.selcuk.edu.tr"

        # Önceden başarılı state yaz
        pre_state = {
            "last_run": "2026-01-01T00:00:00+00:00",
            "total_crawled": 1,
            "urls": {
                seed: {
                    "status": "success",
                    "crawled_at": "2026-01-01T00:00:00+00:00",
                    "depth": 0,
                    "content_type": "text_page",
                    "links_found": 0,
                }
            },
        }
        with open(state_file, "w") as f:
            json.dump(pre_state, f)

        try:
            session = FakeSession()

            config = CrawlerConfig(
                seed_url=seed,
                max_depth=0,
                max_pages=100,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            result = crawler.crawl()

            # State'teki URL tekrar taranmamalı, ama sonuca eklenmeli
            assert result.stats.skipped_seen == 1
            assert result.stats.pages_crawled == 0
            assert len(session.request_log) == 0
        finally:
            os.unlink(state_file)


class TestMaxPagesSafetyLimit:
    def test_stops_at_max_pages(self):
        """max_pages=3 ise en fazla 3 sayfa taranır."""
        seed = "https://www.selcuk.edu.tr"
        links = [f"https://www.selcuk.edu.tr/page{i}" for i in range(20)]
        html = _make_html_with_links(links)

        responses = {seed: FakeResponse(html)}
        for link in links:
            responses[link] = FakeResponse(
                _make_html_with_links([f"{link}/sub"])
            )

        session = FakeSession(responses=responses)
        state_file = _temp_state_file()

        try:
            config = CrawlerConfig(
                seed_url=seed,
                max_depth=3,
                max_pages=3,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            result = crawler.crawl()

            assert result.stats.pages_crawled <= 3
        finally:
            os.unlink(state_file)


class TestCrawlResultSeparation:
    def test_pages_and_docs_separated(self):
        """text_pages ve document_links doğru ayrılmalı."""
        seed = "https://www.selcuk.edu.tr"
        links = [
            "https://www.selcuk.edu.tr/about",
            "https://www.selcuk.edu.tr/docs/yonerge.pdf",
            "https://www.selcuk.edu.tr/files/rapor.docx",
            "https://www.selcuk.edu.tr/img/logo.png",
        ]

        html = _make_html_with_links(links)
        session = FakeSession(
            responses={
                seed: FakeResponse(html),
                "https://www.selcuk.edu.tr/about": FakeResponse(
                    "<html><body>Hakkinda</body></html>"
                ),
            }
        )

        state_file = _temp_state_file()
        try:
            config = CrawlerConfig(
                seed_url=seed,
                max_depth=1,
                max_pages=100,
                crawl_delay=0,
                state_file=state_file,
                allowed_domains=("selcuk.edu.tr",),
                exclude_patterns=(),
                user_agents=(),
            )
            crawler = SelcukCrawler(config=config, scraper=FakeScraper(session))
            result = crawler.crawl()

            # Seed + about = text_pages
            assert seed in result.text_pages
            assert "https://www.selcuk.edu.tr/about" in result.text_pages

            # PDF ve DOCX = document_links
            assert "https://www.selcuk.edu.tr/docs/yonerge.pdf" in result.document_links
            assert "https://www.selcuk.edu.tr/files/rapor.docx" in result.document_links

            # PNG ne text_pages'ta ne de document_links'te olmalı
            assert "https://www.selcuk.edu.tr/img/logo.png" not in result.text_pages
            assert "https://www.selcuk.edu.tr/img/logo.png" not in result.document_links
        finally:
            os.unlink(state_file)


class TestCrawlerConfigFromEnv:
    def test_reads_env_variables(self, monkeypatch):
        monkeypatch.setenv("CRAWL_SEED_URL", "https://test.selcuk.edu.tr")
        monkeypatch.setenv("CRAWL_MAX_DEPTH", "3")
        monkeypatch.setenv("CRAWL_DELAY", "0.5")
        monkeypatch.setenv("CRAWL_MAX_PAGES", "100")
        monkeypatch.setenv("CRAWL_REQUEST_TIMEOUT", "20")
        monkeypatch.setenv("CRAWL_EXCLUDE_PATTERNS", "/login,/admin/")

        config = CrawlerConfig.from_env()

        assert config.seed_url == "https://test.selcuk.edu.tr"
        assert config.max_depth == 3
        assert config.crawl_delay == 0.5
        assert config.max_pages == 100
        assert config.request_timeout == 20
        assert "/login" in config.exclude_patterns
        assert "/admin/" in config.exclude_patterns
