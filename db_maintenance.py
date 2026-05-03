import os
import logging
from datetime import datetime, timezone
import hashlib

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] DB_MAINTENANCE: %(message)s")
logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

def perform_maintenance(stale_days=30):
    if not os.path.exists(DB_DIR):
        logger.info("ChromaDB bulunamadi.")
        return

    logger.info("Veritabani bakimi baslatiliyor...")
    
    embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    db = Chroma(persist_directory=DB_DIR, embedding_function=embedding_model)
    collection = db._collection
    
    result = collection.get(include=["metadatas", "documents"])
    ids = result.get("ids", [])
    metadatas = result.get("metadatas", [])
    documents = result.get("documents", [])
    
    if not ids:
        logger.info("Veritabani bos.")
        return
        
    logger.info("Toplam %d vektor inceleniyor...", len(ids))
    
    # 1. Duplicate Remover (Hash Cakismasi)
    seen_hashes = set()
    duplicate_ids = []
    
    # 2. Stale Data Expiry
    stale_ids = []
    now = datetime.now(timezone.utc)
    
    for i, meta in enumerate(metadatas):
        # --- Duplicate Check ---
        chunk_text = documents[i] or ""
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        
        # Ayni hash'e sahip baska bir chunk varsa kopyadir
        if chunk_hash in seen_hashes:
            duplicate_ids.append(ids[i])
        else:
            seen_hashes.add(chunk_hash)
            
        # --- Stale Data Check ---
        # Sadece guncel degerini cabuk yitiren icerikler eskir
        doc_type = meta.get("doc_type", "")
        if doc_type in ["duyuru", "etkinlik", "haber"]:
            crawled_at_str = meta.get("crawled_at")
            if crawled_at_str:
                try:
                    if crawled_at_str.endswith("Z"):
                        crawled_at_str = crawled_at_str[:-1] + "+00:00"
                    
                    crawled_at_dt = datetime.fromisoformat(crawled_at_str)
                    
                    if crawled_at_dt.tzinfo is None:
                        crawled_at_dt = crawled_at_dt.replace(tzinfo=timezone.utc)
                        
                    age_days = (now - crawled_at_dt).days
                    if age_days > stale_days:
                        stale_ids.append(ids[i])
                except ValueError:
                    pass

    # Silme Islemleri
    total_to_delete = set(duplicate_ids + stale_ids)
    
    if total_to_delete:
        logger.info("Silinecek kopyalar: %d, Eskimis veriler: %d (Toplam unique silinecek: %d)", 
                    len(duplicate_ids), len(stale_ids), len(total_to_delete))
        collection.delete(ids=list(total_to_delete))
        logger.info("Silme islemi basariyla tamamlandi. Vektor compaction ChromaDB tarafindan otomatik yapildi.")
    else:
        logger.info("Silinecek kopya veya eskimis veri bulunamadi.")
        
    logger.info("Veritabani bakimi tamamlandi.")

if __name__ == "__main__":
    perform_maintenance(stale_days=30)
