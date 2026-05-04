# Full Authorized Ingestion Raporu

## 1. Amaç

Bu çalışma, Selçuk Üniversitesi merkezi yönetmelikler ve yönergeler liste sayfalarındaki erişilebilir PDF corpus'unu local ve kontrollü bir tek seferlik ingestion ile ChromaDB'ye almak için yapıldı.

Bu işlem canlı runtime scraping değildir. Faz 4A yapılmadı; metadata-aware rerank production `rag_engine.py` akışına taşınmadı.

## 2. Kullanılan Mod

Bu çalıştırmada terminal session içinde yetkili mod açık kullanıldı:

| Ayar | Değer |
|---|---:|
| `AUTHORIZED_SOURCE_MODE` | `true` |
| `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE` | `true` |
| `WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST` | `true` |
| `WEB_SCRAPER_ALLOWED_DOMAINS` | `selcuk.edu.tr,webadmin.selcuk.edu.tr,eski.selcuk.edu.tr,yemek.selcuk.edu.tr` |
| `WEB_SCRAPER_TIMEOUT_SEC` | `20` |
| `WEB_SCRAPER_MAX_RETRIES` | `5` |
| `WEB_SCRAPER_BACKOFF_SEC` | `2.0` |

Robots override varsayılan davranış değildir; bu rapordaki kullanım bilinçli/yetkili local corpus oluşturma modu içindir.

## 3. Inventory Sonucu

Çalıştırılan komut:

```bash
python discovery_report.py --manifest source_manifest.json --source-id central_regulations_listing --source-id central_directives_listing --pdf-inventory-only --include-inactive --json --out full_pdf_inventory_authorized.json
```

Not: Komut JSON dosyasını üretti; Windows konsolunda Türkçe karakter çıktısı yazdırılırken `cp1254` kaynaklı console encoding hatası oluştu. Dosya çıktısı başarılıdır.

| Kaynak | URL | Fetch | PDF sayısı |
|---|---|---:|---:|
| `central_regulations_listing` | `https://selcuk.edu.tr/anasayfa/detay/39873` | başarılı | 72 |
| `central_directives_listing` | `https://selcuk.edu.tr/anasayfa/detay/39874` | başarılı | 84 |

Toplam PDF adayı: 156  
Benzersiz PDF adayı: 154

Inventory'den URL listesi üretildi:

```bash
python scripts/inventory_to_url_list.py --inventory full_pdf_inventory_authorized.json --out full_pdf_urls_authorized.txt
```

## 4. Ingestion Sonucu

Ana ingestion komutu legal chunking açık şekilde çalıştırıldı:

```bash
python data_ingestion.py --urls full_pdf_urls_authorized.txt --batch-size 10 --clear --legal-chunking
```

Uzun süren PDF/OCR işlemleri nedeniyle ingestion birkaç kontrollü parça halinde tamamlandı. Kalan URL listeleri ChromaDB'de zaten bulunan kaynaklarla karşılaştırılarak üretildi ve `--clear` olmadan devam ettirildi.

| Metrik | Değer |
|---|---:|
| Benzersiz PDF adayı | 154 |
| Başarıyla ChromaDB'ye giren PDF | 149 |
| Başarısız PDF | 5 |
| Retry yapılacak PDF | 0 |
| Manuel fallback gereken PDF | 5 |
| Üretilen chunk/document | 2985 |

Başarısız PDF'ler `full_ingestion_failures_authorized.json` ve `manual_download_todo.csv` dosyalarına yazıldı. Tüm hatalar `ocr_failed` sınıfındadır.

## 5. ChromaDB Health

Çalıştırılan komut:

```bash
python check_chroma_health.py --db-path chroma_db --json --out chroma_health_report_full_authorized.json
```

| Alan | Değer |
|---|---:|
| Status | `ok` |
| Collection okunabilir | true |
| Document/chunk sayısı | 2985 |
| Benzersiz kaynak sayısı | 149 |
| `web_pdf` chunk sayısı | 2985 |

Index raporu:

```bash
python index_report.py --json --out index_report_full_authorized.json
```

`doc_type` dağılımı:

| doc_type | chunk |
|---|---:|
| akademik_takvim | 40 |
| yönetmelik | 2 |
| yönerge | 122 |
| genel | 67 |
| karar | 9 |
| duyuru | 1 |
| mezuniyet | 4 |

## 6. Madde Analizi

Çalıştırılan komut:

```bash
python analysis_chroma_articles.py --json --out chroma_article_analysis_full_authorized.json --markdown-out docs/FULL_AUTHORIZED_CHROMA_MADDE_ANALIZ_RAPORU.md
```

| Metrik | Değer |
|---|---:|
| Toplam chunk | 2985 |
| Benzersiz kaynak | 149 |
| MADDE yapısı olan kaynak | 122 |
| Tahmini toplam madde | 2427 |

Lisansüstü Eğitim ve Öğretim Yönetmeliği kaynaklarında:

| Kontrol | Sonuç |
|---|---:|
| MADDE yapısı | true |
| Tahmini madde sayısı | 58 |
| Tanımlar | true |
| AKTS | true |
| Yeterlik | true |

## 7. Başarısız Kaynaklar

Başarısız 5 PDF'nin tamamı OCR aşamasında kaldı. Ortak neden:

```text
Tesseract Turkish language data missing: tur.traineddata bulunamadı.
```

Bu hatalar geçici HTTP/network hatası değildir; `retryable=false` olarak sınıflandırıldı. Retry URL listesi boş üretildi.

Kalıcı çözüm seçenekleri:

- Tesseract `tur.traineddata` dosyasını kurup `TESSDATA_PREFIX` değerini doğrulamak.
- Bu 5 PDF'yi manuel indirip OCR/metin çıkarımı tamamlandıktan sonra `data/manual_pdfs/` benzeri commit edilmeyen bir klasörden ingestion'a eklemek.
- PDF'lerin metin tabanlı yeni sürümü varsa doğrudan onu kaynak göstermek.

Manuel indirilen PDF'leri eklemek için güvenli local PDF desteği hazırlandı:

```bash
python data_ingestion.py --local-pdf-dir data/manual_pdfs --legal-chunking
```

Bu komut `--clear` kullanılmadan çalıştırıldığında mevcut ChromaDB'ye ekleme yapar. `data/manual_pdfs/` içeriği Git'e commit edilmemelidir.

## 8. Retrieval Smoke Test

LLM/Groq çağrısı yapılmadan mevcut golden question set ile retrieval değerlendirmesi çalıştırıldı:

```bash
python evaluation/evaluate_retrieval.py --questions evaluation/golden_questions.json --out retrieval_full_authorized_report.json --top-k 5
```

| Metrik | Değer |
|---|---:|
| `document_hit_at_1` | 0.933 |
| `document_hit_at_3` | 1.000 |
| `document_hit_at_5` | 1.000 |
| `article_hit_at_1` | 0.733 |
| `article_hit_at_3` | 0.800 |
| `article_hit_at_5` | 0.800 |
| `expected_terms_hit_at_5` | 0.800 |

Bu ölçüm production metadata-aware rerank kullanmaz; Faz 4A kapsamında production entegrasyona geçilmedi.

## 9. Canlıya Taşıma Kararı

Bu `chroma_db/` snapshot'ı canlıya hızlı corpus düzeltmesi için genel olarak uygundur:

- Healthcheck `ok`.
- 149 benzersiz PDF kaynak var.
- 2985 chunk üretildi.
- Yönetmelik/yönerge corpus'unun büyük çoğunluğu alındı.
- Lisansüstü yönetmeliklerde AKTS, Tanımlar ve Yeterlik sinyalleri mevcut.

Bilinen eksik: 5 PDF OCR/Tesseract Türkçe dil verisi eksikliği nedeniyle işlenemedi. Bu eksik canlıya alma için bloklayıcı değilse snapshot kullanılabilir; tamlık isteniyorsa önce OCR dil verisi kurulup bu 5 PDF yeniden işlenmelidir.

Bu rapor aşamasında `chroma_db/` stage edilmedi, commit edilmedi ve push yapılmadı.
