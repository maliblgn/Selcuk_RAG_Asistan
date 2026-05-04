# Baseline Durum Raporu

Rapor tarihi: 2026-05-04  
Çalışma dizini: `C:\Users\User\Desktop\Selcuk_RAG_Cloud`

Bu rapor geliştirme öncesi mevcut durumu ölçmek için hazırlanmıştır. Uygulama mantığına, RAG/crawler/scraper/ingestion kodlarına veya `.env`/secret dosyalarına müdahale edilmemiştir. Yalnızca rapor dosyası ve istenen baseline JSON çıktıları üretilmiştir.

## 1. İncelenen Dosyalar

| Dosya / Klasör | Mevcut mu? | Kısa rol açıklaması |
|---|---:|---|
| `app.py` | Evet | Streamlit chat arayüzü, asistan modu, kaynak gösterimi, admin paneli ve hata yönetimi. |
| `rag_engine.py` | Evet | ChromaDB, embedding, BM25/vector hibrit retriever, FlashRank reranking, Groq LLM promptları ve cevap üretim mantığı. |
| `data_ingestion.py` | Evet | URL/manifest/crawler kaynaklarını okuyup dokümanları chunk'lara bölerek ChromaDB'ye yazan ingestion CLI. |
| `web_scraper.py` | Evet | URL doğrulama, domain whitelist, robots.txt kontrolü, HTML/PDF çekme, PDF metin çıkarma ve OCR fallback akışı. |
| `web_crawler.py` | Evet | BFS tabanlı küçük/otonom web keşfi; metin sayfaları ve doküman linklerini ayırır. |
| `content_processor.py` | Evet | trafilatura tabanlı içerik çıkarma, semantik/header-aware chunking ve metadata zenginleştirme yardımcıları. |
| `crawler_config.py` | Evet | User-Agent havuzu, exclude/priority pattern'ları, doküman uzantıları ve timeout ayarları. |
| `crawler_db.py` | Evet | SQLite tabanlı crawler state ve URL kayıt yönetimi. |
| `source_manifest.json` | Evet | Web-only kaynak stratejisi; seed, doğrudan kaynak ve beklenen doküman listeleri. |
| `curated_web_sources.txt` | Evet | Kontrollü demo bilgi tabanı için küçük web/PDF kaynak listesi. |
| `index_report.py` | Evet | ChromaDB kapsam ve manifest uyum raporu üretir. |
| `discovery_report.py` | Evet | Küçük limitli web keşif raporu üretir; ChromaDB'yi değiştirmez. |
| `tests/` | Evet | pytest tabanlı birim testleri. |

## 2. Test Sonuçları

İstenen komut:

```powershell
pytest tests/ -v
```

Sonuç: Bu komut doğrudan çalışmadı. `pytest` PATH üzerinde bulunamadığı için PowerShell `CommandNotFoundException` verdi. Bu durum gerçek kod hatası değil; yerel PATH/sanal ortam kullanımıyla ilgili çalıştırma ortamı problemidir.

Ölçümü alabilmek için mevcut sanal ortamla eşdeğer test çalıştırıldı:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Sonuç:

| Metrik | Değer |
|---|---:|
| Toplanan test | 77 |
| Geçen test | 75 |
| Kalan / skipped test | 2 |
| Başarısız test | 0 |
| Süre | 70.62 sn |

Hata sınıflandırması:

| Tür | Durum | Not |
|---|---|---|
| API key hatası | Yok | Testler gerçek Groq çağrısı gerektirmeden geçti. |
| Network hatası | Yok | Test paketi network yüzünden kırılmadı. |
| Dependency hatası | Kısmi | `pytest` komutu PATH'te yok; sanal ortam üzerinden testler çalışıyor. |
| Gerçek kod hatası | Yok | Sanal ortamla çalıştırılan testlerde failure/error yok. |
| Skipped test | Var | `test_content_processor.py` içinde 2 test skipped. |

## 3. ChromaDB / Index Raporu

Çalıştırılan komut:

```powershell
.\venv\Scripts\python.exe index_report.py --json --out baseline_index_report.json
```

Sonuç: `baseline_index_report.json` başarıyla üretildi.

Özet metrikler:

| Metrik | Değer |
|---|---:|
| ChromaDB mevcut mu? | Evet |
| Embedding / chunk sayısı | 659 |
| Benzersiz kaynak sayısı | 45 |
| DB yolu | `C:\Users\User\Desktop\Selcuk_RAG_Cloud\chroma_db\chroma.sqlite3` |
| Manifest aktif kaynak sayısı | 2 |
| Indexte eksik görünen aktif manifest kaynakları | `cafeteria_menu`, `free_meal_scholarship_directive_2021` |

Kaynak tipi dağılımı:

| Kaynak tipi | Sayı |
|---|---:|
| `web_pdf` | 657 |
| `web_page` | 2 |

Doküman tipi dağılımı:

| Doküman tipi | Sayı |
|---|---:|
| `genel` | 394 |
| `karar` | 78 |
| `yönetmelik` | 69 |
| `sınav` | 40 |
| `akademik_takvim` | 35 |
| `duyuru` | 22 |
| `mezuniyet` | 14 |
| `staj` | 4 |
| `yönerge` | 2 |
| `burs` | 1 |

Önemli gözlem: Index içinde `https://selcuk.edu.tr/anasayfa/detay/39873` ve `https://selcuk.edu.tr/anasayfa/detay/39874` kaynakları 1'er chunk olarak görünüyor. Buna karşın manifestin aktif iki kaynağı olan yemekhane menüsü ve ücretsiz yemek bursu PDF'i index raporunda eksik görünüyor. Bu, mevcut ChromaDB snapshot'ı ile manifest aktif kaynak stratejisinin birebir senkron olmadığını gösterir.

## 4. Discovery Raporu

Çalıştırılan komut:

```powershell
.\venv\Scripts\python.exe discovery_report.py --max-depth 0 --max-pages 3 --json --out baseline_discovery_report.json
```

Sonuç: `baseline_discovery_report.json` başarıyla üretildi. Canlı keşif çok küçük limitlerle çalıştırıldı.

Özet metrikler:

| Metrik | Değer |
|---|---:|
| Aktif seed sayısı | 1 |
| Keşfedilen benzersiz metin sayfası | 1 |
| Keşfedilen doküman linki | 0 |
| Failed URL | 0 |
| Crawler max depth | 0 |
| Crawler max pages | 3 |

Seed sonucu:

| Seed | URL | Sonuç |
|---|---|---|
| `cafeteria_menu` | `https://yemek.selcuk.edu.tr/Menu/MenuGetir` | 1 sayfa işlendi, 0 doküman bulundu, 0 hata. |

Beklenen doküman eşleşmeleri:

| Beklenen doküman | Discovery eşleşmesi |
|---|---|
| `internship_directive` | Hayır |
| `scholarship_directive` | Evet, `free_meal_scholarship_directive_2021` doğrudan kaynak listesinde var. |
| `double_major_directive` | Hayır |
| `diploma_supplement_directive` | Hayır |
| `excuse_directive` | Hayır |

Network/robots hatası bu küçük çalıştırmada görülmedi. Rapor yalnızca aktif seed ve aktif doğrudan kaynakları dikkate aldığı için kapsam doğal olarak dar kaldı.

## 5. Manifest Durumu

Manifest stratejisi: `web_only_discovery`.

Aktif kaynaklar:

| Bölüm | ID | Başlık | URL | Permission gerekli mi? |
|---|---|---|---|---:|
| `crawl_seeds` | `cafeteria_menu` | Yemekhane Menü Servisi | `https://yemek.selcuk.edu.tr/Menu/MenuGetir` | Hayır |
| `known_direct_sources` | `free_meal_scholarship_directive_2021` | Ücretsiz Yemek Bursu Yönergesi 2021 | `https://eski.selcuk.edu.tr/contents/076/icerik/%C3%9Ccretsiz%20Yemek%20Bursu%20Y%C3%B6nergesi2021_637926976061139192.pdf` | Hayır |

Pasif kaynaklar:

| Bölüm | ID | Başlık | Kritik mi? | Permission gerekli mi? |
|---|---|---|---|---:|
| `crawl_seeds` | `selcuk_home` | Selçuk Üniversitesi Anasayfa | Orta | Evet |
| `crawl_seeds` | `student_portal` | Öğrenci Sayfası | Yüksek | Evet |
| `crawl_seeds` | `academic_portal` | Akademik Sayfa | Yüksek | Evet |
| `crawl_seeds` | `central_regulations` | Merkezi Mevzuat Sayfası | Yüksek | Evet |
| `crawl_seeds` | `technology_faculty` | Teknoloji Fakültesi Sayfası | Orta | Evet |
| `crawl_seeds` | `technology_regulations` | Teknoloji Fakültesi Yönerge ve Yönetmelikler | Yüksek | Evet |
| `known_direct_sources` | `central_regulations_listing` | Selçuk Üniversitesi Yönetmelikler Listesi | Kritik | Evet |
| `known_direct_sources` | `central_directives_listing` | Selçuk Üniversitesi Yönergeler Listesi | Kritik | Evet |
| `known_direct_sources` | `academic_calendar_2025_2026` | 2025-2026 Genel Akademik Takvimi | Yüksek | Evet |
| `known_direct_sources` | `technology_internship_directive_2023` | Teknoloji Fakültesi Staj Yönergesi 2023 | Yüksek | Evet |

Özellikle istenen iki kritik kaynak:

| Kaynak | Manifestte var mı? | Bölüm | Aktif mi? | Permission gerekli mi? | Indexte var mı? |
|---|---:|---|---:|---:|---:|
| `https://selcuk.edu.tr/anasayfa/detay/39873` | Evet | `known_direct_sources` / `central_regulations_listing` | Hayır | Evet | Evet, 1 chunk |
| `https://selcuk.edu.tr/anasayfa/detay/39874` | Evet | `known_direct_sources` / `central_directives_listing` | Hayır | Evet | Evet, 1 chunk |

Yorum: Yönetmelikler ve yönergeler listesi manifestte doğru şekilde tanımlanmış, fakat varsayılan modda pasif tutuluyor. Bu durum güvenlik/robots/izin politikası açısından bilinçli görünüyor; ancak geliştirme ve demo kapsamı için bu iki kaynağın pasif olması merkezi mevzuat keşfini sınırlıyor.

## 6. Demo Kaynak Durumu

`curated_web_sources.txt` içeriği:

| Kaynak | Tür | Kapsam |
|---|---|---|
| `https://yemek.selcuk.edu.tr/Menu/MenuGetir` | Web sayfası / servis | Kampüs yaşamı, yemekhane menüsü |
| `https://eski.selcuk.edu.tr/contents/076/icerik/%C3%9Ccretsiz%20Yemek%20Bursu%20Y%C3%B6nergesi2021_637926976061139192.pdf` | PDF | Ücretsiz yemek bursu yönergesi |

Kapsam değerlendirmesi: Bu liste kontrollü ve güvenli demo için uygun, fakat gerçek yönetmelik/yönerge kapsamı için yeterli değil. Staj, çift ana dal, diploma/diploma eki, mazeret, genel eğitim-öğretim yönetmelikleri ve merkezi yönerge/yönetmelik listeleri bu demo listesinde yer almıyor. Bu nedenle kullanıcı arayüzündeki örnek akademik soruların tamamını güvenilir şekilde cevaplamak için daha geniş ve izin/robots açısından netleştirilmiş bir kaynak seti gerekir.

## 7. Riskler

- `pytest tests/ -v` doğrudan çalışmıyor; `pytest` PATH'te yok. Sanal ortamla testler geçiyor, bu yüzden dokümantasyonda komut `.\venv\Scripts\python.exe -m pytest tests/ -v` veya sanal ortam aktivasyonu açık yazılmalı.
- Manifestin aktif kaynakları ile mevcut ChromaDB snapshot'ı senkron değil: aktif iki kaynak index raporunda eksik görünüyor.
- Merkezi yönetmelikler ve yönergeler listesi manifestte var ama pasif ve `requires_permission=true`. Varsayılan demo/keşif akışı bu kritik kaynakları kapsamıyor.
- ChromaDB'de çok sayıda `webadmin.selcuk.edu.tr` PDF'i var. Bu kaynakların robots/izin durumu ve commit/teslim stratejisi net belgelenmeli.
- Discovery düşük limitte başarılı olsa da yalnızca yemekhane seed'ini taradı; mevzuat keşfi hakkında güçlü kanıt üretmedi.
- PDF erişimi, robots.txt, SSL ve kurumsal izin riskleri devam ediyor. Özellikle `webadmin.selcuk.edu.tr` PDF'leri için otomatik işleme politikası dikkatli yönetilmeli.
- Mevcut rapor çıktılarında bazı Türkçe karakterler terminal/JSON görüntülemede bozuk görünebiliyor; bu, kodlama/console görüntüleme kaynaklı olabilir.
- `.env` dosyası mevcut ama bu raporda içeriği kullanılmadı ve değiştirilmedi. API key/secret üretimi veya commit işlemi yapılmadı.

## 8. Bir Sonraki Adım Önerisi

Kod değişikliği yapmadan bir sonraki geliştirme için önce kaynak stratejisi netleştirilmeli. En yüksek öncelik, `source_manifest.json` ile mevcut ChromaDB snapshot'ını uyumlu hale getirecek kontrollü bir kaynak planı çıkarmaktır:

1. Yönetmelikler listesi (`39873`) ve yönergeler listesi (`39874`) için izin/robots durumu netleştirilmeli.
2. Demo kaynak listesi akademik örnek soruları karşılayacak şekilde genişletilmeli veya arayüzdeki örnek sorular mevcut demo kapsamına göre daraltılmalı.
3. `baseline_index_report.json` ve `baseline_discovery_report.json` referans alınarak hangi beklenen dokümanların eksik olduğu işaretlenmeli.
4. Sonraki kod geliştirmesi olarak ingestion/crawler davranışına geçmeden önce "hangi kaynaklar aktif, hangileri izinli modda, hangileri kesinlikle pasif" kararı verilmelidir.
