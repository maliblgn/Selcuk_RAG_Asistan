# Faz 2A Legal Chunker Raporu

Rapor tarihi: 2026-05-04T08:45:55+00:00

## 1. Amaç

Türkçe mevzuat metinlerinde cevapların madde düzeyinde daha doğru bağlanabilmesi için MADDE bazlı chunklama yapan bağımsız ve test edilebilir bir modül eklendi. Bu fazda ChromaDB, ingestion pipeline, web fetch veya PDF okuma akışına entegrasyon yapılmadı.

## 2. Desteklenen Madde Formatları

- `MADDE 1 -`
- `MADDE 1 –`
- `MADDE 43-`
- `Madde 4 -`
- `madde 5 -`
- `MADDE 7`
- `MADDE 8-(1)`
- `MADDE 8 - (1)`

## 3. Modül Fonksiyonları

- `ArticleChunk`: madde numarası, başlık, içerik, karakter aralığı ve yaklaşık sayfa aralığını taşır.
- `find_article_starts(text)`: satır/paragraf başındaki MADDE başlangıçlarını bulur.
- `split_text_by_articles(text, source_metadata=None)`: tek metni ArticleChunk listesine böler.
- `split_pages_by_articles(page_texts, source_metadata=None)`: sayfa metinlerinden ArticleChunk listesi ve yaklaşık page_start/page_end üretir.
- `article_chunks_to_documents(chunks, source_metadata=None)`: ArticleChunk listesini LangChain Document listesine çevirir.
- `extract_article_title(article_text, article_no)`: ilk MADDE satırından başlık benzeri kısa metni çıkarır.
- `looks_like_legal_text(text)`: en az iki farklı MADDE başlangıcı varsa mevzuat benzeri metin kabul eder.

## 4. Test Sonuçları

`pytest tests/ -v` komutu çalıştırıldı; sonuç final yanıtta özetlenmiştir.

## 5. Demo Çıktısı

Sabit örnek metinden 4 madde çıkarıldı.

| madde | başlık |
|---|---|
| 1 | Amaç |
| 2 | Tanımlar |
| 43 | Doktora yeterlik sınavları ile ilgili esaslar şunlardır |
| 44 | Yürürlük |

## 6. Sonraki Adım

Bir sonraki fazda `legal_chunker.py` mevcut ingestion pipeline'a opsiyonel olarak entegre edilebilir. Entegrasyon öncesinde gerçek yönetmelik metinlerinden örnekler seçilip madde bölünmesi, sayfa aralığı ve metadata kalitesi ayrıca doğrulanmalıdır.
