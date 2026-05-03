import sqlite3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawler_state.db")

def get_connection():
    return sqlite3.connect(DB_PATH, isolation_level=None)

def init_db():
    """Veritabani tablolarini olusturur."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawled_urls (
                url TEXT PRIMARY KEY,
                status TEXT,
                crawled_at TEXT,
                depth INTEGER,
                content_type TEXT,
                links_found INTEGER,
                content_hash TEXT
            )
        """)
        logger.debug("SQLite crawler_state.db hazir.")

def get_url_record(url: str) -> Optional[Dict]:
    """Belirtilen URL'nin kaydini getirir."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM crawled_urls WHERE url = ?", (url,))
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            "url": row[0],
            "status": row[1],
            "crawled_at": row[2],
            "depth": row[3],
            "content_type": row[4],
            "links_found": row[5],
            "content_hash": row[6]
        }

def upsert_url_record(
    url: str,
    status: str,
    depth: int,
    content_type: str,
    links_found: int,
    content_hash: str = None
):
    """Bir URL kaydini ekler veya gunceller."""
    crawled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Once var mi kontrol et, varsa mevcut hash'i koru eger yeni hash verilmediyse
        cursor.execute("SELECT content_hash FROM crawled_urls WHERE url = ?", (url,))
        row = cursor.fetchone()
        
        if content_hash is None and row is not None:
            content_hash = row[0]
            
        cursor.execute("""
            INSERT INTO crawled_urls (url, status, crawled_at, depth, content_type, links_found, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                status = excluded.status,
                crawled_at = excluded.crawled_at,
                depth = excluded.depth,
                content_type = excluded.content_type,
                links_found = excluded.links_found,
                content_hash = excluded.content_hash
        """, (url, status, crawled_at, depth, content_type, links_found, content_hash))

def delete_url_record(url: str):
    """Bir URL kaydini siler."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crawled_urls WHERE url = ?", (url,))

def get_all_records() -> List[Dict]:
    """Tum kayitlari getirir."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM crawled_urls")
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "url": row[0],
                "status": row[1],
                "crawled_at": row[2],
                "depth": row[3],
                "content_type": row[4],
                "links_found": row[5],
                "content_hash": row[6]
            })
        return results

def get_record_count() -> int:
    """Toplam kayit sayisini dondurur."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM crawled_urls")
        return cursor.fetchone()[0]

# Ilk yuklemede tabloyu hazirla
init_db()
