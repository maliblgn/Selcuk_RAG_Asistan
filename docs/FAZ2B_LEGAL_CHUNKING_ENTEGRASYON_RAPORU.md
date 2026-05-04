# Faz 2B Legal Chunking Entegrasyon Raporu

## 1. Amaç

Bu fazda Faz 2A'da eklenen `legal_chunker.py` modülü ingestion pipeline'a opsiyonel olarak bağlandı. Amaç, mevzuat benzeri metinlerde MADDE bazlı chunk üretimini hazır hale getirmek; mevcut varsayılan chunklama davranışını ve mevcut ChromaDB snapshot'ını değiştirmemektir.

## 2. Varsayılan Davranış

`LEGAL_CHUNKING_ENABLED=false` varsayılan değerdir. Bu durumda `data_ingestion.py` içindeki mevcut `SmartChunker` / `RecursiveCharacterTextSplitter` akışı aynen çalışır.

CLI'da `--legal-chunking` verilmediğinde ve env flag true değilken legal chunker çağrısı yapılmaz; dokümanlar mevcut fallback splitter'a gönderilir.

## 3. Aktif Davranış

Legal chunking şu iki yoldan biriyle aktif olur:

```powershell
.\venv\Scripts\python.exe data_ingestion.py --legal-chunking
```

veya:

```env
LEGAL_CHUNKING_ENABLED=true
```

Aktif olduğunda pipeline önce metnin `looks_like_legal_text()` kontrolünden geçip geçmediğine bakar. Mevzuat formatı tespit edilirse madde bazlı `Document` üretir. Mevzuat formatı yoksa veya legal chunker hata verirse mevcut chunker fallback olarak çalışır.

`source_type=web_pdf` olan ve aynı `source` metadata'sını taşıyan sayfa dokümanları gruplanır, `page` metadata'sına göre sıralanır ve `split_pages_by_articles()` ile işlenir. Böylece `page_start` ve `page_end` yaklaşık olarak korunur.

## 4. Metadata

Article chunk çıktılarında kaynak metadata'sı korunur. Eklenen alanlar:

| Alan | Açıklama |
| --- | --- |
| `article_no` | MADDE numarası |
| `article_title` | MADDE satırından çıkarılan başlık veya kısa giriş |
| `page_start` | Maddenin başladığı yaklaşık PDF sayfası |
| `page_end` | Maddenin bittiği yaklaşık PDF sayfası |
| `chunk_type` | `article` |
| `legal_chunker` | `true` |

Korunması beklenen kaynak alanları: `source`, `title`, `source_type`, `doc_type`, `extraction_method`.

## 5. Test Sonuçları

Çalıştırılan komut:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Testler synthetic `Document` verileriyle çalıştırıldı. Bu fazda gerçek ingestion, web fetch, PDF indirme veya ChromaDB yazma komutu çalıştırılmadı.

Sonuç:

```text
106 passed, 2 skipped
```

## 6. Sonraki Adım

Bir sonraki fazda küçük ve kontrollü bir örnek belgeyle dry-run ingestion/preview akışı hazırlanabilir. Bu önizleme, ChromaDB'yi yeniden üretmeden legal chunking çıktılarının gerçek PDF metinlerinde nasıl göründüğünü doğrulamak için kullanılmalıdır.
