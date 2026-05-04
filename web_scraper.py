import logging
import random
import os
from io import BytesIO
import re
import time
import hashlib
from dataclasses import dataclass
from typing import List, Sequence, Tuple
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from pypdf import PdfReader
from requests.exceptions import SSLError, Timeout
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Web scraping isleminde olusan kontrollu hatalar."""


@dataclass
class ScraperConfig:
    allowed_domains: Sequence[str] = ("selcuk.edu.tr",)
    enable_domain_whitelist: bool = False
    timeout_sec: int = 10
    max_retries: int = 3
    backoff_sec: float = 1.0
    min_content_chars: int = 300
    # Tek string veya tuple kabul eder; tuple ise her istekte rastgele seçim yapılır
    user_agent: str | Tuple[str, ...] = "Selcuk-RAG-Bot/1.0 (+educational-use)"
    verify_ssl: bool = True
    allow_insecure_ssl_fallback: bool = True

    @classmethod
    def from_env(cls):
        enable_domain_whitelist = _env_bool("WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST", False)
        domains_raw = os.getenv("WEB_SCRAPER_ALLOWED_DOMAINS", "selcuk.edu.tr")
        allowed_domains = tuple(d.strip() for d in domains_raw.split(",") if d.strip())
        if not allowed_domains:
            allowed_domains = ("selcuk.edu.tr",)

        return cls(
            allowed_domains=allowed_domains,
            enable_domain_whitelist=enable_domain_whitelist,
            timeout_sec=_env_int("WEB_SCRAPER_TIMEOUT_SEC", 10),
            max_retries=_env_int("WEB_SCRAPER_MAX_RETRIES", 3),
            backoff_sec=_env_float("WEB_SCRAPER_BACKOFF_SEC", 1.0),
            min_content_chars=_env_int("WEB_SCRAPER_MIN_CONTENT_CHARS", 300),
            user_agent=_parse_user_agent_env(),
            verify_ssl=_env_bool("WEB_SCRAPER_VERIFY_SSL", True),
            allow_insecure_ssl_fallback=_env_bool("WEB_SCRAPER_ALLOW_INSECURE_FALLBACK", True),
        )


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
        logger.warning("Gecersiz %s degeri (%s), varsayilan kullaniliyor: %s", name, value, default)
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Gecersiz %s degeri (%s), varsayilan kullaniliyor: %s", name, value, default)
        return default


def _parse_user_agent_env() -> "str | Tuple[str, ...]":
    """WEB_SCRAPER_USER_AGENT env'ini oku; virgul varsa tuple olarak dondur."""
    raw = os.getenv("WEB_SCRAPER_USER_AGENT", "").strip()
    if not raw:
        # crawler_config mevcutsa oradan al, yoksa varsayilan
        try:
            from crawler_config import get_user_agents
            return get_user_agents()
        except ImportError:
            return "Selcuk-RAG-Bot/1.0 (+educational-use)"
    if "," in raw:
        return tuple(ua.strip() for ua in raw.split(",") if ua.strip())
    return raw


class URLValidator:
    @staticmethod
    def normalize_url(url: str) -> str:
        return (url or "").strip()

    @staticmethod
    def normalize_discovered_url(url: str) -> str:
        """HTML icinden bulunan URL'leri requests icin guvenli hale getir."""
        raw = (url or "").strip()
        if not raw:
            return raw
        parsed = urlparse(raw)
        path = quote(unquote(parsed.path), safe="/:%[]")
        query = quote(unquote(parsed.query), safe="=&?/:,%[]")
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            query,
            "",
        ))

    @staticmethod
    def split_url_and_selector(url_entry: str) -> Tuple[str, str | None]:
        raw = (url_entry or "").strip()
        if "|css=" in raw:
            base, selector = raw.split("|css=", 1)
            return base.strip(), selector.strip() or None
        if "|selector=" in raw:
            base, selector = raw.split("|selector=", 1)
            return base.strip(), selector.strip() or None
        return raw, None

    @staticmethod
    def is_valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def is_allowed_domain(url: str, allowed_domains: Sequence[str]) -> bool:
        host = (urlparse(url).hostname or "").lower()
        for domain in allowed_domains:
            d = domain.lower().strip()
            if host == d or host.endswith(f".{d}"):
                return True
        return False

    @staticmethod
    def is_allowed_by_robots(url: str, user_agent: str) -> bool:
        if _env_bool("WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE", False):
            logger.warning("AUTHORIZED robots override aktif; robots kontrolu izinli modda gecildi: %s", url)
            return True
        if isinstance(user_agent, tuple):
            user_agent = user_agent[0] if user_agent else "*"
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp.can_fetch(user_agent, url)
        except Exception as exc:
            logger.warning("robots.txt okunamadi, URL guvenli tarafta bloklandi (%s): %s", robots_url, exc)
            return False

    @staticmethod
    def is_allowed_by_robots_strict(url: str, user_agent: str) -> bool:
        """robots.txt kontrolunu authorized override kullanmadan yap."""
        if isinstance(user_agent, tuple):
            user_agent = user_agent[0] if user_agent else "*"
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp.can_fetch(user_agent, url)
        except Exception as exc:
            logger.warning("robots.txt okunamadi, URL guvenli tarafta bloklandi (%s): %s", robots_url, exc)
            return False


class ContentCleaner:
    @staticmethod
    def clean_html_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    @staticmethod
    def validate_content_quality(text: str, min_chars: int) -> bool:
        return bool(text and len(text.strip()) >= min_chars)

    @staticmethod
    def clean_page_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "noscript", "svg", "footer", "header", "nav", "form"]):
            tag.decompose()

        selector_candidates = [
            "main",
            "article",
            "#content",
            ".content",
            ".icerik",
            ".detail",
            ".post-content",
            ".entry-content",
            ".haber-icerik",
            ".duyuru-icerik",
            "body",
        ]

        best_text = ""
        for selector in selector_candidates:
            for node in soup.select(selector):
                text = node.get_text(separator="\n", strip=True)
                if len(text) > len(best_text):
                    best_text = text

        lines = [line.strip() for line in best_text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned


class WebScraper:
    def __init__(self, config: ScraperConfig | None = None, session: requests.Session | None = None):
        self.config = config or ScraperConfig()
        self.session = session or requests.Session()
        # UA rotation: tuple ise ilk değeri varsayılan header olarak ata
        ua = self.config.user_agent
        initial_ua = ua[0] if isinstance(ua, tuple) else ua
        self.session.headers.update({"User-Agent": initial_ua})
        self._robots_cache = {}

        if not self.config.verify_ssl:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        retries = Retry(
            total=self.config.max_retries,
            connect=self.config.max_retries,
            read=self.config.max_retries,
            status=self.config.max_retries,
            backoff_factor=self.config.backoff_sec,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["HEAD", "GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def scrape_url(self, url: str) -> Document:
        normalized, css_selector = URLValidator.split_url_and_selector(url)
        normalized = URLValidator.normalize_url(normalized)
        if not URLValidator.is_valid_url(normalized):
            raise ScrapingError(f"Gecersiz URL: {url}")

        if self.config.enable_domain_whitelist and not URLValidator.is_allowed_domain(
            normalized,
            self.config.allowed_domains,
        ):
            raise ScrapingError(f"Whitelist disi domain: {normalized}")

        if not self._is_allowed_by_robots(normalized):
            raise ScrapingError(f"robots.txt erisim izni vermiyor: {normalized}")

        response = self._request_with_retry(normalized, "URL cekilemedi")
        return self._build_page_document_from_html(normalized, response.text, css_selector=css_selector)

    def scrape_page_linked_pdfs(self, page_url: str) -> Tuple[List[Document], List[str]]:
        normalized, css_selector = URLValidator.split_url_and_selector(page_url)
        normalized = URLValidator.normalize_url(normalized)
        errors: List[str] = []

        if not URLValidator.is_valid_url(normalized):
            return [], [f"Gecersiz URL: {page_url}"]
        if self.config.enable_domain_whitelist and not URLValidator.is_allowed_domain(
            normalized,
            self.config.allowed_domains,
        ):
            return [], [f"Whitelist disi domain: {normalized}"]
        if not self._is_allowed_by_robots(normalized):
            return [], [f"robots.txt erisim izni vermiyor: {normalized}"]

        try:
            response = self._request_with_retry(normalized, "URL cekilemedi")
        except ScrapingError as exc:
            return [], [str(exc)]

        pdf_links = self.extract_pdf_links(response.text, normalized)
        docs: List[Document] = []

        # PDF olmasa bile sayfa icerigini dokumana donustururuz.
        try:
            docs.append(
                self._build_page_document_from_html(
                    normalized,
                    response.text,
                    css_selector=css_selector,
                )
            )
        except ScrapingError as exc:
            errors.append(str(exc))

        for pdf_url in pdf_links:
            try:
                docs.extend(self._pdf_url_to_documents(pdf_url))
            except ScrapingError as exc:
                logger.warning("PDF atlaniyor: %s", exc)
                errors.append(str(exc))

        if not docs:
            errors.append(f"Sayfadan icerik alinamiadi: {normalized}")

        return docs, errors

    def scrape_urls(self, urls: Sequence[str], delay_sec: float = 0.0) -> Tuple[List[Document], List[str]]:
        docs: List[Document] = []
        errors: List[str] = []

        for idx, url in enumerate(urls):
            try:
                docs.append(self.scrape_url(url))
            except ScrapingError as exc:
                logger.warning("Scraping atlaniyor: %s", exc)
                errors.append(str(exc))

            if delay_sec > 0 and idx < len(urls) - 1:
                time.sleep(delay_sec)

        return docs, errors

    def scrape_urls_with_linked_pdfs(
        self, urls: Sequence[str], include_page_text: bool = True, delay_sec: float = 0.0
    ) -> Tuple[List[Document], List[str]]:
        docs: List[Document] = []
        errors: List[str] = []

        for idx, raw_url in enumerate(urls):
            normalized, _ = URLValidator.split_url_and_selector(raw_url)
            normalized = URLValidator.normalize_url(normalized)
            if normalized.lower().endswith(".pdf"):
                try:
                    docs.extend(self._pdf_url_to_documents(raw_url))
                except ScrapingError as exc:
                    errors.append(str(exc))
            else:
                page_docs, page_errors = self.scrape_page_linked_pdfs(raw_url)
                docs.extend(page_docs)
                errors.extend(page_errors)

                if include_page_text:
                    page_only_docs = [
                        d for d in page_docs
                        if hasattr(d, "metadata") and isinstance(getattr(d, "metadata"), dict)
                        and d.metadata.get("source_type") == "web_page"
                    ]
                    if not page_only_docs:
                        try:
                            docs.append(self.scrape_url(raw_url))
                        except ScrapingError as exc:
                            errors.append(str(exc))

            if delay_sec > 0 and idx < len(urls) - 1:
                time.sleep(delay_sec)

        return docs, errors

    @staticmethod
    def _extract_title(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        return (soup.title.string.strip() if soup.title and soup.title.string else "")

    @staticmethod
    def _extract_primary_heading(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        heading = soup.find("h1")
        return heading.get_text(separator=" ", strip=True) if heading else ""

    @staticmethod
    def extract_pdf_links(html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        found: List[str] = []
        seen = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href:
                continue
            absolute = URLValidator.normalize_discovered_url(urljoin(base_url, href))
            if ".pdf" not in absolute.lower():
                continue
            if absolute not in seen:
                seen.add(absolute)
                found.append(absolute)
        return found

    @staticmethod
    def _title_from_pdf_url(pdf_url: str) -> str:
        parsed = urlparse(pdf_url)
        filename = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
        if filename.lower().endswith(".pdf"):
            filename = filename[:-4]
        filename = filename.replace("_", " ").replace("-", " ")
        filename = re.sub(r"\s+", " ", filename).strip()
        filename = re.sub(r"[\s_,-]*(?:\d{12,}|[0-9a-fA-F]{24,})$", "", filename).strip()
        return filename or "PDF Belgesi"

    @classmethod
    def extract_pdf_link_inventory(cls, html: str, base_url: str) -> List[dict]:
        """HTML icindeki PDF linklerini baslik ve normalize URL bilgisiyle cikar."""
        soup = BeautifulSoup(html, "lxml")
        found: List[dict] = []
        seen = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href:
                continue

            absolute = urljoin(base_url, href)
            normalized = URLValidator.normalize_discovered_url(absolute)
            if ".pdf" not in normalized.lower():
                continue
            if normalized in seen:
                continue
            seen.add(normalized)

            title = anchor.get_text(separator=" ", strip=True)
            if not title:
                title = cls._title_from_pdf_url(normalized)

            found.append({
                "title": title,
                "url": absolute,
                "normalized_url": normalized,
                "domain": urlparse(normalized).netloc,
                "source_page": base_url,
            })

        return found

    def _pdf_url_to_documents(self, pdf_url: str) -> List[Document]:
        pdf_url, _ = URLValidator.split_url_and_selector(pdf_url)
        if not URLValidator.is_valid_url(pdf_url):
            raise ScrapingError(f"Gecersiz PDF URL: {pdf_url}")
        if self.config.enable_domain_whitelist and not URLValidator.is_allowed_domain(
            pdf_url,
            self.config.allowed_domains,
        ):
            raise ScrapingError(f"Whitelist disi PDF domaini: {pdf_url}")
        if not self._is_allowed_by_robots(pdf_url):
            raise ScrapingError(f"robots.txt PDF erisim izni vermiyor: {pdf_url}")

        response = self._request_with_retry(pdf_url, "PDF indirilemedi")

        page_texts, extraction_method = self.extract_text_from_pdf(response.content, pdf_url)

        docs: List[Document] = []
        for page_idx, text in enumerate(page_texts):
            cleaned_text = (text or "").strip()
            if not cleaned_text:
                continue
            
            content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
            
            metadata = {
                "source": pdf_url,
                "source_type": "web_pdf",
                "page": page_idx + 1,
                "title": pdf_url.split("/")[-1],
                "extraction_method": extraction_method,
                "content_hash": content_hash,
            }
            docs.append(Document(page_content=cleaned_text, metadata=metadata))

        if not docs:
            raise ScrapingError(f"PDF'den metin cikartilamadi: {pdf_url}")

        return docs

    def _build_page_document_from_html(
        self,
        source_url: str,
        html: str,
        css_selector: str | None = None,
    ) -> Document:
        if css_selector:
            # CSS selector modu: mevcut davranis korunur
            soup = BeautifulSoup(html, "lxml")
            nodes = soup.select(css_selector)
            if not nodes:
                raise ScrapingError(f"CSS selector eslesmedi: {source_url} ({css_selector})")
            selected_html = "\n".join(str(node) for node in nodes)
            content = ContentCleaner.clean_page_text(selected_html)
        else:
            # Content-First: trafilatura ile icerik cikar, fallback BS4
            try:
                from content_processor import ContentExtractor
                content = ContentExtractor.extract_main_content(html, url=source_url)
            except ImportError:
                content = None

            if not content:
                content = ContentCleaner.clean_page_text(html)

        min_chars = min(self.config.min_content_chars, 120)
        if not ContentCleaner.validate_content_quality(content, min_chars):
            raise ScrapingError(
                f"Icerik cok kisa veya bos: {source_url} ({len(content)} karakter)"
            )

        title = self._extract_title(html)
        heading = self._extract_primary_heading(html)
        prefix_parts = [part for part in (title, heading) if part and part not in content[:500]]
        if prefix_parts:
            content = "\n".join(prefix_parts + [content])

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        metadata = {
            "source": source_url,
            "source_type": "web_page",
            "title": title,
            "content_hash": content_hash,
        }
        if css_selector:
            metadata["selector"] = css_selector
        return Document(page_content=content, metadata=metadata)

    def extract_text_from_pdf(self, pdf_bytes: bytes, pdf_url: str) -> Tuple[List[str], str]:
        # 1) Hizli yol: PyPDF ile dogrudan metin cikar.
        pypdf_page_texts: List[str] = []
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            pypdf_page_texts = [(page.extract_text() or "") for page in reader.pages]
        except Exception as exc:
            logger.warning("PyPDF okuma hatasi, OCR fallback deneniyor (%s): %s", pdf_url, exc)

        merged_pypdf = "\n".join(t.strip() for t in pypdf_page_texts if t and t.strip())
        if len(merged_pypdf) >= 100:
            return pypdf_page_texts, "pypdf"

        # 2) Son care: OCR fallback (turkce).
        logger.info("PDF metni yetersiz, OCR fallback tetiklendi: %s", pdf_url)
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
        except Exception as exc:
            raise ScrapingError(f"OCR kutuphaneleri yuklenemedi: {pdf_url} ({exc})") from exc

        try:
            images = convert_from_bytes(pdf_bytes)
        except Exception as exc:
            raise ScrapingError(f"OCR icin PDF goruntuye cevrilemedi: {pdf_url} ({exc})") from exc

        ocr_page_texts: List[str] = []
        try:
            for image in images:
                ocr_page_texts.append(pytesseract.image_to_string(image, lang="tur"))
        except Exception as exc:
            raise ScrapingError(f"OCR metin cikartma hatasi: {pdf_url} ({exc})") from exc

        merged_ocr = "\n".join(t.strip() for t in ocr_page_texts if t and t.strip())
        if len(merged_ocr) < 100:
            raise ScrapingError(f"PDF'den metin cikartilamadi: {pdf_url}")

        return ocr_page_texts, "ocr"

    def _request_with_retry(self, url: str, error_prefix: str):
        last_error = None
        max_attempts = max(1, self.config.max_retries)
        verify_ssl = self.config.verify_ssl

        if not verify_ssl:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

        for attempt in range(1, max_attempts + 1):
            # UA rotation: her istekte farklı UA seç
            ua = self.config.user_agent
            if isinstance(ua, tuple) and len(ua) > 1:
                self.session.headers["User-Agent"] = random.choice(ua)

            try:
                response = self.session.get(
                    url,
                    timeout=self.config.timeout_sec,
                    verify=verify_ssl,
                )
                response.raise_for_status()
                return response
            except SSLError as exc:
                last_error = exc

                # SSL zinciri problemi yasaniyorsa tek seferlik kontrollu fallback.
                if verify_ssl and self.config.allow_insecure_ssl_fallback:
                    verify_ssl = False
                    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
                    logger.warning(
                        "%s: SSL dogrulama hatasi alindi, verify=False fallback deneniyor: %s",
                        error_prefix,
                        url,
                    )
                    continue

                if attempt >= max_attempts:
                    break
                wait_sec = self.config.backoff_sec * (2 ** (attempt - 1))
                logger.warning(
                    "%s (deneme %d/%d): %s | tekrar denenecek",
                    error_prefix,
                    attempt,
                    max_attempts,
                    url,
                )
                time.sleep(wait_sec)
            except Timeout as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                wait_sec = self.config.backoff_sec * (2 ** (attempt - 1))
                logger.warning(
                    "%s (timeout deneme %d/%d): %s | tekrar denenecek",
                    error_prefix,
                    attempt,
                    max_attempts,
                    url,
                )
                time.sleep(wait_sec)
            except requests.RequestException as exc:
                raise ScrapingError(f"{error_prefix}: {url} ({exc})") from exc

        raise ScrapingError(f"{error_prefix}: {url} ({last_error})") from last_error

    def _is_allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        cache_key = f"{parsed.scheme}://{parsed.netloc}"
        if cache_key not in self._robots_cache:
            self._robots_cache[cache_key] = URLValidator.is_allowed_by_robots(
                url,
                self.config.user_agent,
            )
        return self._robots_cache[cache_key]


def parse_urls_from_text(text: str) -> List[str]:
    seen = set()
    urls: List[str] = []
    for line in (text or "").splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls
