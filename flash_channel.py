import os
import time
import logging
from dotenv import load_dotenv

# dotenv'i baslangicta yukle
load_dotenv()

from web_scraper import WebScraper, ScraperConfig, ScrapingError
from data_ingestion import _delete_old_vectors, _split_documents, _persist_documents
from crawler_db import get_url_record, upsert_url_record

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] FLASH_CHANNEL: %(message)s")
logger = logging.getLogger(__name__)

def process_priority_url(url: str, scraper: WebScraper):
    """Tek bir oncelikli sayfayi kontrol eder, degismisse sisteme kaydeder."""
    logger.info("Kontrol ediliyor: %s", url)
    try:
        page_docs, page_errors = scraper.scrape_page_linked_pdfs(url)
        
        if page_errors:
            for err in page_errors:
                logger.warning("Scraping hatasi (%s): %s", url, err)
                
        if not page_docs:
            return

        main_doc = page_docs[0]
        new_hash = main_doc.metadata.get("content_hash")
        
        record = get_url_record(url)
        old_hash = record.get("content_hash") if record else None
        
        if new_hash and old_hash and new_hash == old_hash:
            logger.info("Degisiklik yok: %s", url)
            return
            
        logger.info("Guncelleme tespit edildi! Vektorler yenileniyor: %s", url)
        
        # 1. Eski vektorleri sil
        if old_hash:
            _delete_old_vectors(url)
            
        # 2. Yeni parcalari vektor uzerine yaz
        parcalar = _split_documents(page_docs)
        _persist_documents(parcalar, clear_existing=False)
        
        # 3. SQLite veritabanini guncelle
        upsert_url_record(
            url=url,
            status="success",
            depth=record.get("depth", 0) if record else 0,
            content_type="document" if ".pdf" in url.lower() else "text_page",
            links_found=record.get("links_found", 0) if record else 0,
            content_hash=new_hash
        )
        logger.info("Basariyla guncellendi: %s", url)
        
    except ScrapingError as exc:
        logger.warning("URL isleme hatasi (%s): %s", url, exc)
    except Exception as exc:
        logger.warning("Beklenmeyen hata (%s): %s", url, exc)

def main():
    urls_env = os.getenv("PRIORITY_URLS", "")
    priority_urls = [u.strip() for u in urls_env.split(",") if u.strip()]
    
    if not priority_urls:
        logger.error("PRIORITY_URLS bulunamadi. Lutfen .env dosyasini kontrol edin.")
        return
        
    logger.info("Flash Channel baslatildi. %d adet oncelikli URL izleniyor.", len(priority_urls))
    
    scraper = WebScraper(ScraperConfig.from_env())
    check_interval = 900 # 15 dakika (saniye)
    
    while True:
        logger.info("=== Flash Channel Dongusu Basliyor ===")
        for url in priority_urls:
            process_priority_url(url, scraper)
            
        logger.info("=== Dongu Tamamlandi. %d dakika bekleniyor. ===", check_interval // 60)
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
