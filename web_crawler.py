"""
Otonom web crawler modülü — Selçuk Üniversitesi RAG Asistanı.

BFS (Breadth-First Search) tabanlı recursive link discovery.
Mevcut WebScraper altyapısını composition ile kullanır.

Kullanım (CLI):
    python web_crawler.py --seed-url https://www.selcuk.edu.tr --max-depth 1 --max-pages 10
"""

import argparse
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from crawler_config import (
    DOCUMENT_EXTENSIONS,
    SKIP_EXTENSIONS,
    get_exclude_patterns,
    get_priority_patterns,
    get_request_timeout,
    get_user_agents,
    is_url_excluded,
    pick_user_agent,
)
from web_scraper import ScraperConfig, WebScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────── Klasör Yolları ───────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# ═══════════════════════════════════════════════════════════
#  CrawlerConfig
# ═══════════════════════════════════════════════════════════
@dataclass
class CrawlerConfig:
    """Crawler'a özel ayarlar (.env'den okunabilir)."""

    seed_url: str = "https://www.selcuk.edu.tr"
    max_depth: int = 2
    crawl_delay: float = 1.0
    max_pages: int = 500
    allowed_domains: Tuple[str, ...] = ("selcuk.edu.tr",)
    state_file: str = os.path.join(_BASE_DIR, "crawled_urls.json")
    exclude_patterns: Tuple[str, ...] = ()
    priority_patterns: Tuple[str, ...] = ()
    user_agents: Tuple[str, ...] = ()
    request_timeout: int = 15

    @classmethod
    def from_env(cls) -> "CrawlerConfig":
        """Ortam değişkenlerinden CrawlerConfig oluştur."""
        domains_raw = os.getenv("WEB_SCRAPER_ALLOWED_DOMAINS", "selcuk.edu.tr")
        allowed_domains = tuple(d.strip() for d in domains_raw.split(",") if d.strip())
        if not allowed_domains:
            allowed_domains = ("selcuk.edu.tr",)

        return cls(
            seed_url=os.getenv("CRAWL_SEED_URL", "https://www.selcuk.edu.tr"),
            max_depth=_env_int("CRAWL_MAX_DEPTH", 2),
            crawl_delay=_env_float("CRAWL_DELAY", 1.0),
            max_pages=_env_int("CRAWL_MAX_PAGES", 500),
            allowed_domains=allowed_domains,
            state_file=os.path.join(_BASE_DIR, "crawled_urls.json"),
            exclude_patterns=get_exclude_patterns(),
            priority_patterns=get_priority_patterns(),
            user_agents=get_user_agents(),
            request_timeout=get_request_timeout(),
        )


# ═══════════════════════════════════════════════════════════
#  CrawlStats & CrawlResult
# ═══════════════════════════════════════════════════════════
@dataclass
class CrawlStats:
    """Tarama istatistikleri."""

    total_discovered: int = 0
    pages_crawled: int = 0
    documents_found: int = 0
    skipped_seen: int = 0
    skipped_excluded: int = 0
    skipped_robots: int = 0
    skipped_binary: int = 0
    errors: int = 0
    duration_sec: float = 0.0


@dataclass
class CrawlResult:
    """Tarama sonuç raporu."""

    text_pages: List[str] = field(default_factory=list)
    document_links: List[str] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)
    stats: CrawlStats = field(default_factory=CrawlStats)


# ═══════════════════════════════════════════════════════════
#  SelcukCrawler
# ═══════════════════════════════════════════════════════════
class SelcukCrawler:
    """BFS tabanlı otonom web crawler.

    Mevcut WebScraper'ın HTTP session/retry/SSL/robots altyapısını
    composition ile kullanır.
    """

    def __init__(
        self,
        config: CrawlerConfig | None = None,
        scraper: WebScraper | None = None,
    ):
        self.config = config or CrawlerConfig()
        self.scraper = scraper or WebScraper(ScraperConfig.from_env())

    # ─────────────────── Public API ───────────────────

    def crawl(self) -> CrawlResult:
        """Ana BFS tarama döngüsü.

        Returns:
            CrawlResult: text_pages, document_links, failed_urls ve istatistikler.
        """
        start_time = time.time()
        state = self._load_state()
        result = CrawlResult()

        # BFS kuyruğu: (url, depth)
        queue: deque[Tuple[str, int]] = deque()
        seen: Set[str] = set()

        seed = self._normalize_url(self.config.seed_url)
        queue.append((seed, 0))
        seen.add(seed)

        pages_processed = 0

        logger.info(
            "Crawler baslatiliyor: seed=%s, max_depth=%d, max_pages=%d",
            seed,
            self.config.max_depth,
            self.config.max_pages,
        )

        while queue and pages_processed < self.config.max_pages:
            url, depth = queue.popleft()

            # ── Kontroller ──
            if depth > self.config.max_depth:
                continue

            if self._should_skip_from_state(url, state):
                result.stats.skipped_seen += 1
                # State'teki sonuçları da result'a ekle
                entry = state.get("urls", {}).get(url, {})
                ctype = entry.get("content_type", "")
                if ctype == "text_page" and url not in result.text_pages:
                    result.text_pages.append(url)
                elif ctype == "document" and url not in result.document_links:
                    result.document_links.append(url)
                continue

            if not self._is_in_domain(url):
                continue

            if self._is_excluded(url):
                result.stats.skipped_excluded += 1
                continue

            url_class = self._classify_url(url)
            if url_class == "skip":
                result.stats.skipped_binary += 1
                continue

            if not self._is_allowed_by_robots(url):
                logger.warning("robots.txt nedeniyle atlandi: %s", url)
                result.failed_urls.append(url)
                result.stats.skipped_robots += 1
                self._update_state_entry(state, url, "robots_blocked", depth, url_class, 0)
                continue

            if url_class == "document":
                result.document_links.append(url)
                result.stats.documents_found += 1
                self._update_state_entry(state, url, "success", depth, "document", 0)
                continue

            # ── text_page: GET isteği ──
            html = self._fetch_page(url)
            if html is None:
                result.failed_urls.append(url)
                result.stats.errors += 1
                self._update_state_entry(state, url, "error", depth, "text_page", 0)
                pages_processed += 1
                continue

            result.text_pages.append(url)
            result.stats.pages_crawled += 1
            pages_processed += 1

            # ── Link keşfi ──
            discovered_links = self._prioritize_links(self._extract_page_links(html, url))
            result.stats.total_discovered += len(discovered_links)
            valid_links_count = 0

            for link in discovered_links:
                normalized = self._normalize_url(link)
                if normalized in seen:
                    continue
                seen.add(normalized)

                if not self._is_in_domain(normalized):
                    continue

                if self._is_excluded(normalized):
                    result.stats.skipped_excluded += 1
                    continue

                link_class = self._classify_url(normalized)
                if link_class == "skip":
                    result.stats.skipped_binary += 1
                    continue

                if not self._is_allowed_by_robots(normalized):
                    result.stats.skipped_robots += 1
                    self._update_state_entry(
                        state, normalized, "robots_blocked", depth + 1, link_class, 0
                    )
                    continue

                if link_class == "document":
                    if normalized not in result.document_links:
                        result.document_links.append(normalized)
                        result.stats.documents_found += 1
                        self._update_state_entry(
                            state, normalized, "success", depth + 1, "document", 0
                        )
                    continue

                # text_page → kuyruğa ekle
                if depth + 1 <= self.config.max_depth:
                    queue.append((normalized, depth + 1))
                    valid_links_count += 1

            self._update_state_entry(
                state, url, "success", depth, "text_page", valid_links_count
            )

            logger.info(
                "[%d/%d] depth=%d links=%d queue=%d | %s",
                pages_processed,
                self.config.max_pages,
                depth,
                valid_links_count,
                len(queue),
                url[:80],
            )

            # ── Politeness delay ──
            if queue and self.config.crawl_delay > 0:
                time.sleep(self.config.crawl_delay)

        # ── Sonuçları kaydet ──
        elapsed = time.time() - start_time
        result.stats.duration_sec = round(elapsed, 2)

        state["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state["total_crawled"] = len(state.get("urls", {}))
        self._save_state(state)

        logger.info(
            "Crawler tamamlandi: %d sayfa, %d dokuman, %d hata (%.1fs)",
            result.stats.pages_crawled,
            result.stats.documents_found,
            result.stats.errors,
            result.stats.duration_sec,
        )

        return result

    # ─────────────────── Link Çıkarma ───────────────────

    def _extract_page_links(self, html: str, base_url: str) -> List[str]:
        """Sayfadaki tüm <a href> linklerini çıkar ve absolute URL'ye çevir."""
        soup = BeautifulSoup(html, "lxml")
        links: List[str] = []
        seen_in_page: Set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href:
                continue

            # javascript: ve mailto: zaten exclude_patterns'ta ama erken filtrele
            if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

            absolute = urljoin(base_url, href)
            normalized = self._normalize_url(absolute)

            if normalized not in seen_in_page:
                seen_in_page.add(normalized)
                links.append(normalized)

        return links

    # ─────────────────── URL Sınıflandırma ───────────────────

    @staticmethod
    def _classify_url(url: str) -> str:
        """URL'yi sınıflandır: 'text_page', 'document' veya 'skip'.

        Uzantıya göre karar verir. Uzantı yoksa text_page kabul edilir.
        """
        parsed = urlparse(url)
        path_lower = parsed.path.lower()

        # Sondaki / temizle
        clean_path = path_lower.rstrip("/")

        # Uzantı var mı?
        if "." in clean_path.split("/")[-1]:
            for ext in DOCUMENT_EXTENSIONS:
                if clean_path.endswith(ext):
                    return "document"
            for ext in SKIP_EXTENSIONS:
                if clean_path.endswith(ext):
                    return "skip"

        return "text_page"

    # ─────────────────── Domain Lock ───────────────────

    def _is_in_domain(self, url: str) -> bool:
        """URL'nin izin verilen domainler içinde olup olmadığını kontrol et."""
        host = (urlparse(url).hostname or "").lower()
        for domain in self.config.allowed_domains:
            d = domain.lower().strip()
            if host == d or host.endswith(f".{d}"):
                return True
        return False

    # ─────────────────── Exclude Patterns ───────────────────

    def _is_excluded(self, url: str) -> bool:
        """URL'nin hariç tutma desenlerinden birine uyup uymadığını kontrol et."""
        return is_url_excluded(url, self.config.exclude_patterns)

    def _is_allowed_by_robots(self, url: str) -> bool:
        """WebScraper robots politikasini crawler icin de zorunlu uygula."""
        checker = getattr(self.scraper, "_is_allowed_by_robots", None)
        if checker is None:
            return True
        try:
            return bool(checker(url))
        except Exception as exc:
            logger.warning("robots kontrolu basarisiz, URL atlandi: %s (%s)", url, exc)
            return False

    def _priority_score(self, url: str) -> int:
        url_lower = url.lower()
        return sum(1 for pattern in self.config.priority_patterns if pattern.lower() in url_lower)

    def _prioritize_links(self, links: List[str]) -> List[str]:
        """Mevzuat/dokuman olasiligi yuksek URL'leri BFS kuyrugunda one al."""
        return sorted(links, key=lambda link: (-self._priority_score(link), link))

    # ─────────────────── URL Normalizasyon ───────────────────

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URL'yi normalize et: fragment sil, trailing slash düzenle, scheme küçült."""
        url = (url or "").strip()
        if not url:
            return url

        parsed = urlparse(url)

        # Fragment (#section) sil
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",  # fragment kaldırıldı
        ))

        # Trailing slash: root path (/) hariç sondaki / kaldır
        if normalized.endswith("/") and urlparse(normalized).path != "/":
            normalized = normalized.rstrip("/")

        return normalized

    # ─────────────────── HTTP Fetch ───────────────────

    def _fetch_page(self, url: str) -> Optional[str]:
        """Sayfayı GET ile çek, hata durumunda None döndür."""
        try:
            # UA rotation
            ua = self.config.user_agents
            if ua:
                self.scraper.session.headers["User-Agent"] = pick_user_agent()

            response = self.scraper.session.get(
                url,
                timeout=self.config.request_timeout,
                verify=self.scraper.config.verify_ssl,
            )
            response.raise_for_status()

            # Sadece HTML içerik kabul et
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.debug("HTML olmayan icerik atlandi: %s (%s)", url, content_type)
                return None

            return response.text

        except Exception as exc:
            logger.warning("Sayfa cekilemedi: %s (%s)", url, exc)
            return None

    # ─────────────────── State Management ───────────────────

    def _load_state(self) -> Dict:
        """crawler_db üzerinden kayıtları yükle."""
        if self.config.state_file and os.path.exists(self.config.state_file):
            try:
                if os.path.getsize(self.config.state_file) > 0:
                    with open(self.config.state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                        state["_state_file"] = self.config.state_file
                        return state
                return {"urls": {}, "last_run": None, "total_crawled": 0, "_state_file": self.config.state_file}
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("State dosyasi okunamadi, bos state kullaniliyor: %s", exc)
                return {"urls": {}, "last_run": None, "total_crawled": 0, "_state_file": self.config.state_file}

        from crawler_db import get_all_records
        records = get_all_records()
        state_urls = {}
        for rec in records:
            state_urls[rec["url"]] = rec
        return {"urls": state_urls, "last_run": None, "total_crawled": len(state_urls), "_state_file": self.config.state_file}

    def _save_state(self, state: Dict) -> None:
        """crawler_db anlik yazdigi icin toplu kayda gerek yok. Sadece logla."""
        if self.config.state_file:
            try:
                with open(self.config.state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except OSError as exc:
                logger.warning("State dosyasi yazilamadi: %s", exc)

        logger.info(
            "Crawler state db ile senkronize edildi. Toplam %d kayit.",
            state.get("total_crawled", 0),
        )

    def _should_skip_from_state(self, url: str, state: Dict) -> bool:
        """URL daha önce başarıyla taranmış mı?"""
        entry = state.get("urls", {}).get(url)
        if entry is None:
            return False
        return entry.get("status") == "success"

    @staticmethod
    def _update_state_entry(
        state: Dict,
        url: str,
        status: str,
        depth: int,
        content_type: str,
        links_found: int,
    ) -> None:
        """State sözlüğüne bir URL kaydı ekle/güncelle ve veritabanina yaz."""
        if "urls" not in state:
            state["urls"] = {}
        
        now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
        
        # Varsayilan crawler state'i kullanilirken SQLite panel metriklerini de guncelle.
        if os.path.basename(str(state.get("_state_file", "crawled_urls.json"))) == "crawled_urls.json":
            from crawler_db import upsert_url_record
            try:
                upsert_url_record(
                    url=url,
                    status=status,
                    depth=depth,
                    content_type=content_type,
                    links_found=links_found
                )
            except Exception as e:
                logger.error("DB kayit hatasi: %s", e)

        state["urls"][url] = {
            "status": status,
            "crawled_at": now_str,
            "depth": depth,
            "content_type": content_type,
            "links_found": links_found,
        }


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════
def _parse_args():
    parser = argparse.ArgumentParser(
        description="Selcuk Universitesi otonom web crawler."
    )
    parser.add_argument(
        "--seed-url",
        type=str,
        default=None,
        help="Baslangic URL'si (varsayilan: .env'den veya https://www.selcuk.edu.tr)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Tarama derinligi (varsayilan: .env'den veya 2)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maksimum taranacak sayfa sayisi (varsayilan: .env'den veya 500)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Istekler arasi bekleme suresi - saniye (varsayilan: .env'den veya 1.0)",
    )
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Mevcut state dosyasini sifirla",
    )
    return parser.parse_args()


def main():
    from dotenv import load_dotenv

    load_dotenv()

    args = _parse_args()

    config = CrawlerConfig.from_env()

    # CLI argumanlari env'i override eder
    if args.seed_url:
        config.seed_url = args.seed_url
    if args.max_depth is not None:
        config.max_depth = args.max_depth
    if args.max_pages is not None:
        config.max_pages = args.max_pages
    if args.delay is not None:
        config.crawl_delay = args.delay

    if args.clear_state and os.path.exists(config.state_file):
        os.remove(config.state_file)
        logger.info("State dosyasi silindi: %s", config.state_file)

    crawler = SelcukCrawler(config=config)
    result = crawler.crawl()

    # ── Özet Rapor ──
    print("\n" + "=" * 60)
    print("  🕸️  CRAWLER RAPORU")
    print("=" * 60)
    print(f"  Taranan sayfa      : {result.stats.pages_crawled}")
    print(f"  Bulunan döküman    : {result.stats.documents_found}")
    print(f"  Keşfedilen link    : {result.stats.total_discovered}")
    print(f"  Atlanan (state)    : {result.stats.skipped_seen}")
    print(f"  Atlanan (exclude)  : {result.stats.skipped_excluded}")
    print(f"  Atlanan (robots)   : {result.stats.skipped_robots}")
    print(f"  Atlanan (binary)   : {result.stats.skipped_binary}")
    print(f"  Hatalar            : {result.stats.errors}")
    print(f"  Süre               : {result.stats.duration_sec}s")
    print("=" * 60)

    if result.text_pages:
        print(f"\n📄 Metin Sayfaları ({len(result.text_pages)}):")
        for url in result.text_pages[:20]:
            print(f"   • {url}")
        if len(result.text_pages) > 20:
            print(f"   ... ve {len(result.text_pages) - 20} daha")

    if result.document_links:
        print(f"\n📎 Döküman Linkleri ({len(result.document_links)}):")
        for url in result.document_links[:20]:
            print(f"   • {url}")
        if len(result.document_links) > 20:
            print(f"   ... ve {len(result.document_links) - 20} daha")

    if result.failed_urls:
        print(f"\n❌ Başarısız URL'ler ({len(result.failed_urls)}):")
        for url in result.failed_urls[:10]:
            print(f"   • {url}")


if __name__ == "__main__":
    main()
