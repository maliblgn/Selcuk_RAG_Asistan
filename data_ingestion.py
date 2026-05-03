import argparse
import json
import os
import re
import shutil
import logging
from datetime import datetime
from typing import List, Set, Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from web_scraper import WebScraper, ScraperConfig, ScrapingError, parse_urls_from_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Klasör Yolları (her zaman bu dosyanın bulunduğu dizine göre)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_BASE_DIR, "chroma_db")
FAILED_DOCS_PATH = os.path.join(_BASE_DIR, "failed_docs.json")


def filter_already_ingested(urls: List[str], existing_sources: Set[str]) -> List[str]:
    """Mevcut kaynaklarda bulunan URL'leri yeni islenecek listeden cikar."""
    return [url for url in urls if url not in existing_sources]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def authorized_source_mode_enabled() -> bool:
    """Kurumsal izinli kaynaklari dahil etme modu."""
    return _env_bool("AUTHORIZED_SOURCE_MODE", False)


def _manifest_item_enabled(item: dict) -> bool:
    """Manifest kaynaginin bu calistirmada islenip islenmeyecegini belirle."""
    if item.get("active", True):
        return True
    if item.get("requires_permission") and authorized_source_mode_enabled():
        logger.warning(
            "Izinli kaynak modu ile pasif kaynak islenecek: %s (%s)",
            item.get("id", "unknown"),
            item.get("url", ""),
        )
        return True
    return False


def _clear_db():
    logger.info("Eski veritabani temizleniyor...")
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)


def _scrape_url_entries(urls: List[str], label: str):
    if not urls:
        logger.warning("%s icinde islenecek URL bulunamadi.", label)
        return []

    scraper = WebScraper(ScraperConfig.from_env())
    web_docs, errors = scraper.scrape_urls_with_linked_pdfs(urls)
    logger.info(
        "Web scraping tamamlandi (bagli PDF'ler dahil): %d basarili, %d hatali",
        len(web_docs),
        len(errors),
    )
    for err in errors:
        logger.warning("Scraping hatasi: %s", err)

    _write_failed_docs(errors)
    return web_docs


def _load_web_documents(urls_file):
    logger.info("URL listesi okunuyor: %s", urls_file)
    if not os.path.exists(urls_file):
        # Mevcut .txt dosyalarını listele
        available = [f for f in os.listdir(_BASE_DIR) if f.endswith(".txt")]
        hint = ""
        if available:
            hint = f" Mevcut .txt dosyalari: {', '.join(available)}"
        raise FileNotFoundError(f"URL dosyasi bulunamadi: {urls_file}.{hint}")

    with open(urls_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    urls = parse_urls_from_text(raw_text)
    if not urls:
        logger.warning("URL dosyasinda islenecek satir bulunamadi.")
        return []

    return _scrape_url_entries(urls, urls_file)


def load_manifest_urls(manifest_file: str) -> List[str]:
    """JSON kaynak manifestinden aktif URL'leri sirali ve tekrarsiz oku."""
    logger.info("Kaynak manifesti okunuyor: %s", manifest_file)
    if not os.path.exists(manifest_file):
        raise FileNotFoundError(f"Manifest dosyasi bulunamadi: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    urls: List[str] = []
    seen = set()
    sections = ("crawl_seeds", "known_direct_sources", "sources")
    for section in sections:
        for item in payload.get(section, []):
            if not _manifest_item_enabled(item):
                continue
            url = (item.get("url") or "").strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _load_manifest_documents(manifest_file: str):
    urls = load_manifest_urls(manifest_file)
    return _scrape_url_entries(urls, manifest_file)


def _extract_url_from_error(error_message):
    match = re.search(r"https?://[^\s)]+", error_message or "")
    return match.group(0) if match else None


def _write_failed_docs(errors):
    unique_entries = []
    seen = set()

    for err in errors:
        url = _extract_url_from_error(err)
        key = (url or "", err)
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append({
            "url": url,
            "reason": err,
        })

    payload = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "failed_count": len(unique_entries),
        "failed_documents": unique_entries,
    }

    with open(FAILED_DOCS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Basarisiz dokuman logu yazildi: %s (%d kayit)", FAILED_DOCS_PATH, len(unique_entries))


def _split_documents(docs):
    logger.info("Metinler anlam butunlugune gore parcalaniyor...")
    try:
        from content_processor import SmartChunker, MetadataEnricher
        chunker = SmartChunker()
        parcalar = chunker.chunk_documents(docs)
        logger.info("Toplam %d parca olusturuldu. Metadata zenginlestiriliyor...", len(parcalar))
        zengin_parcalar = MetadataEnricher.enrich_documents(parcalar)
        return zengin_parcalar
    except ImportError:
        logger.warning("content_processor bulunamadi, varsayilan chunker kullaniliyor.")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        parcalar = text_splitter.split_documents(docs)
        logger.info("Toplam %d parca olusturuldu.", len(parcalar))
        return parcalar


def _persist_documents(parcalar, clear_existing=False):
    if not parcalar:
        raise ValueError("Kaydedilecek dokuman parcasi yok.")

    logger.info("Vektorler olusturulup Chroma'ya kaydediliyor...")
    embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")

    if clear_existing:
        _clear_db()

    if os.path.exists(DB_DIR) and not clear_existing:
        db = Chroma(persist_directory=DB_DIR, embedding_function=embedding_model)
        db.add_documents(parcalar)
    else:
        Chroma.from_documents(
            documents=parcalar,
            embedding=embedding_model,
            persist_directory=DB_DIR,
        )

    logger.info("Islem tamamlandi.")


# ═══════════════════════════════════════════════════════════
#  Crawler Integration & Incremental Storage
# ═══════════════════════════════════════════════════════════

def get_existing_sources() -> Set[str]:
    """ChromaDB'den mevcut kaynak (source) metadata'larini cek."""
    if not os.path.exists(DB_DIR):
        return set()
    try:
        embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        db = Chroma(persist_directory=DB_DIR, embedding_function=embedding_model)
        collection = db._collection
        result = collection.get(include=["metadatas"])
        sources = set()
        for meta in (result.get("metadatas") or []):
            if meta and "source" in meta:
                sources.add(meta["source"])
        logger.info("ChromaDB'de %d benzersiz kaynak bulundu.", len(sources))
        return sources
    except Exception as exc:
        logger.warning("ChromaDB kaynak listesi alinamadi: %s", exc)
        return set()


def _delete_old_vectors(url: str):
    """Belirtilen URL'ye ait eski vektörleri ChromaDB'den siler."""
    if not os.path.exists(DB_DIR):
        return
    try:
        embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
        db = Chroma(persist_directory=DB_DIR, embedding_function=embedding_model)
        
        # ChromaDB collection'dan source = url olanlari sil
        collection = db._collection
        result = collection.get(where={"source": url}, include=["metadatas"])
        if result and result["ids"]:
            collection.delete(ids=result["ids"])
            logger.info("'%s' icin %d eski vektor silindi.", url, len(result["ids"]))
    except Exception as e:
        logger.warning("Eski vektorler silinirken hata: %s", e)


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _scrape_crawled_url(scraper: WebScraper, url: str) -> Tuple[List[Document], List[str]]:
    """Crawler sonucundaki URL'yi uygun extractor ile isle."""
    if _is_pdf_url(url):
        try:
            return scraper._pdf_url_to_documents(url), []
        except ScrapingError as exc:
            return [], [str(exc)]
    return scraper.scrape_page_linked_pdfs(url)


def _load_crawled_documents(
    crawl_depth: int | None = None,
    crawl_max_pages: int | None = None,
    seed_url: str | None = None,
) -> List[Document]:
    """Crawler'i calistir, bulunan URL'leri tara ve Document listesi dondur."""
    from web_crawler import SelcukCrawler, CrawlerConfig
    from crawler_db import get_url_record, upsert_url_record

    try:
        from tqdm import tqdm
        HAS_TQDM = True
    except ImportError:
        HAS_TQDM = False

    # 1. Crawler'i calistir
    config = CrawlerConfig.from_env()
    if seed_url is not None:
        config.seed_url = seed_url
    if crawl_depth is not None:
        config.max_depth = crawl_depth
    if crawl_max_pages is not None:
        config.max_pages = crawl_max_pages

    logger.info("Otonom crawler baslatiliyor...")
    crawler = SelcukCrawler(config=config)
    result = crawler.crawl()

    logger.info(
        "Crawler sonucu: %d metin sayfasi, %d dokuman linki",
        len(result.text_pages),
        len(result.document_links),
    )

    all_urls = result.text_pages + result.document_links
    if not all_urls:
        logger.info("Islenecek URL bulunamadi.")
        return []

    logger.info("Toplam %d URL web scraper ile taranacak...", len(all_urls))

    # 3. URL'leri WebScraper ile tara ve Hash kontrolü yap
    scraper = WebScraper(ScraperConfig.from_env())
    docs: List[Document] = []
    errors: List[str] = []

    iterable = tqdm(all_urls, desc="Web tarama", unit="url") if HAS_TQDM else all_urls

    for url in iterable:
        try:
            page_docs, page_errors = _scrape_crawled_url(scraper, url)
            
            # Hash kontrolu: Dokumanlarda bir degisiklik var mi?
            # Eger birden fazla dokuman donuyorsa (or: pdf sayfalari) tek bir birlesik hash kullanabiliriz.
            # Burada page_docs icerisindeki ana dokumanin hash'ine bakacagiz.
            if page_docs:
                main_doc = page_docs[0]
                new_hash = main_doc.metadata.get("content_hash")
                
                # DB'deki kaydi al
                record = get_url_record(url)
                old_hash = record.get("content_hash") if record else None
                
                if new_hash and old_hash and new_hash == old_hash:
                    # Icerik ayni, islemeye gerek yok
                    continue
                
                # Degismis veya yeni, eski vektorleri sil
                if old_hash:
                    _delete_old_vectors(url)
                
                # DB'yi guncelle
                upsert_url_record(
                    url=url,
                    status="success",
                    depth=record.get("depth", 0) if record else 0,
                    content_type="document" if ".pdf" in url.lower() else "text_page",
                    links_found=record.get("links_found", 0) if record else 0,
                    content_hash=new_hash
                )
                
                docs.extend(page_docs)
            
            errors.extend(page_errors)
        except ScrapingError as exc:
            errors.append(str(exc))
            logger.warning("URL isleme hatasi: %s", exc)
        except Exception as exc:
            errors.append(f"Beklenmeyen hata ({url}): {exc}")
            logger.warning("Beklenmeyen hata: %s - %s", url, exc)

    # 4. 404 vs gibi hatalarda (artik ulasilamayan), eski vektorleri sil (Soft-delete/Purge)
    existing = get_existing_sources()
    for err_url in result.failed_urls:
        if err_url in existing:
            logger.info("URL artik 404 veriyor, vektorler siliniyor: %s", err_url)
            _delete_old_vectors(err_url)
            # DB'den de durumu guncelle
            upsert_url_record(err_url, "error", 0, "text_page", 0, None)

    logger.info(
        "Crawl sonrasi web tarama tamamlandi: %d yeni/guncellenmis dokuman parcalanmak uzere eklendi, %d hata",
        len(docs),
        len(errors),
    )

    if errors:
        _write_failed_docs(errors)

    return docs


def _load_manifest_crawled_documents(
    manifest_file: str,
    crawl_depth: int | None = None,
    crawl_max_pages: int | None = None,
) -> List[Document]:
    """Manifestteki aktif seed'leri crawler ile kesfedip dokumanlari yukle."""
    logger.info("Manifest seed'leri crawler ile isleniyor: %s", manifest_file)
    if not os.path.exists(manifest_file):
        raise FileNotFoundError(f"Manifest dosyasi bulunamadi: {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    docs: List[Document] = []
    seen_sources = set()
    for seed in payload.get("crawl_seeds", []):
        if not _manifest_item_enabled(seed):
            continue
        url = (seed.get("url") or "").strip()
        if not url:
            continue
        logger.info("Manifest seed crawl: %s (%s)", seed.get("id", "seed"), url)
        seed_docs = _load_crawled_documents(
            crawl_depth=crawl_depth,
            crawl_max_pages=crawl_max_pages,
            seed_url=url,
        )
        for doc in seed_docs:
            key = (doc.metadata.get("source"), doc.metadata.get("page"), doc.page_content[:120])
            if key in seen_sources:
                continue
            seen_sources.add(key)
            docs.append(doc)

    direct_docs = _load_manifest_documents(manifest_file)
    for doc in direct_docs:
        key = (doc.metadata.get("source"), doc.metadata.get("page"), doc.page_content[:120])
        if key not in seen_sources:
            seen_sources.add(key)
            docs.append(doc)

    return docs


# ═══════════════════════════════════════════════════════════
#  Ana Build Fonksiyonu
# ═══════════════════════════════════════════════════════════

def build_ingestion(
    urls_file=None,
    manifest_file=None,
    crawl=False,
    crawl_depth=None,
    crawl_max_pages=None,
    clear_existing=False,
):
    """Ana veri aktarım fonksiyonu.

    Args:
        urls_file: URL listesi dosya yolu.
        manifest_file: JSON kaynak manifesti dosya yolu.
        crawl: Otonom crawler'ı çalıştır.
        crawl_depth: Crawler tarama derinliği.
        crawl_max_pages: Crawler maks sayfa sayısı.
        clear_existing: Mevcut DB'yi temizle.
    """
    docs = []
    if urls_file:
        docs.extend(_load_web_documents(urls_file))
    if manifest_file:
        if crawl:
            docs.extend(_load_manifest_crawled_documents(
                manifest_file,
                crawl_depth=crawl_depth,
                crawl_max_pages=crawl_max_pages,
            ))
            crawl = False
        else:
            docs.extend(_load_manifest_documents(manifest_file))
    if crawl:
        docs.extend(_load_crawled_documents(
            crawl_depth=crawl_depth,
            crawl_max_pages=crawl_max_pages,
        ))

    if not docs:
        raise ValueError("Islenecek dokuman bulunamadi.")

    parcalar = _split_documents(docs)
    _persist_documents(parcalar, clear_existing=clear_existing)


def _parse_args():
    parser = argparse.ArgumentParser(description="Web kaynaklarini taranip ChromaDB'ye aktarir.")
    parser.add_argument("--urls", type=str, help="URL listesini tutan .txt dosya yolu")
    parser.add_argument("--manifest", type=str, help="JSON kaynak manifesti dosya yolu")
    parser.add_argument("--crawl", action="store_true",
                        help="Otonom crawler'i calistirip bulunan URL'leri isle")
    parser.add_argument("--crawl-depth", type=int, default=None,
                        help="Crawler tarama derinligi (varsayilan: .env'den)")
    parser.add_argument("--crawl-max-pages", type=int, default=None,
                        help="Maksimum taranacak sayfa sayisi")
    parser.add_argument("--clear", action="store_true", help="Mevcut veritabanini temizleyip yeniden olusturur")
    return parser.parse_args()


def main():
    args = _parse_args()

    # Eger hicbir arguman verilmediyse crawler'i calistir
    crawl = args.crawl
    if not args.urls and not args.manifest and not args.crawl:
        logger.info("Hicbir arguman verilmedi, varsayilan olarak crawler calistirilacak.")
        crawl = True

    build_ingestion(
        urls_file=args.urls,
        manifest_file=args.manifest,
        crawl=crawl,
        crawl_depth=args.crawl_depth,
        crawl_max_pages=args.crawl_max_pages,
        clear_existing=args.clear,
    )

if __name__ == "__main__":
    main()
