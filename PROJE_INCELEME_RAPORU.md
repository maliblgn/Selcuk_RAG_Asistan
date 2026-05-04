# Selcuk RAG Cloud - Kapsamli Proje Inceleme Raporu

Inceleme tarihi: 2026-05-03  
Inceleme kapsami: kod mimarisi, RAG kalitesi, crawler/scraper akis, test/CI, guvenlik, veri tabani, dokumantasyon ve teslim hazirligi.

Guncelleme notu: Bu rapordaki ilk P0 bulgularindan test/CI uyumu, PDF ingestion ayrimi, kaynak etiketi ve admin sifre fallback'i ayni gun icinde ilk saglamlastirma turunda ele alindi. Son dogrulama: `66 passed, 2 skipped`.

## 1. Genel Degerlendirme

Proje fikri bitirme projesi icin guclu: Selcuk Universitesi web sayfalari ve PDF dokumanlari uzerinden RAG tabanli bir asistan, gercek bir kullanici ihtiyacina denk geliyor. Teknik olarak Streamlit arayuzu, Groq LLM, multilingual embedding, ChromaDB, crawler, robots.txt kontrolu, OCR fallback, semantic chunking, BM25 + vector hybrid retrieval ve reranking gibi iyi secilmis parcalar var.

Ancak su anki durumda proje "calisir prototip" seviyesinden "guvenilir muhendislik teslimi" seviyesine gecmek icin bazi kritik duzeltmelere ihtiyac duyuyor. En onemli problemler testlerin kirik olmasi, crawler ile bulunan PDF linklerinin ingestion yolunda yanlis islenmesi, mevcut Chroma veritabaninin kapsam olarak cok dar kalmasi, admin panelinde varsayilan sifre kullanimi ve CI'in gercek bagimliliklari kurmamasidir.

## 2. Onceliklendirilmis Kritik Bulgular

### P0 - Test paketi ve CI su anda kirik

Komut:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Sonuc: Koleksiyon asamasinda hata alindi. `tests/test_data_ingestion_crawl.py`, `data_ingestion.filter_already_ingested` fonksiyonunu import etmeye calisiyor, fakat `data_ingestion.py` icinde bu fonksiyon yok.

Sorunlu dosya:

- `tests/test_data_ingestion_crawl.py:5`
- `data_ingestion.py`

Sorunlu test disarida birakilip kalan testler calistirildiginda:

```text
13 failed, 50 passed, 2 skipped
```

Basarisizliklarin ana sebepleri:

- `rag_engine.format_context` testleri, kaynak adinin normalize edilmesini bekliyor; kod ise tam source stringini kullaniyor (`rag_engine.py:232-234`).
- `web_crawler` testleri eski JSON `state_file` tasarimina gore yazilmis; kod artik sabit SQLite `crawler_state.db` kullaniyor (`crawler_db.py:9`, `web_crawler.py:432-439`).
- `web_scraper` testleri HTML basliginin page content icinde kalmasini bekliyor; trafilatura/temizleme akisi basligi atabiliyor.

Etki: Bitirme projesi sunumunda veya GitHub Actions uzerinde "testler geciyor" denilemez. Bu, juri karsisinda teknik guvenilirligi en cok zedeleyen konu olur.

Onerilen cozum:

1. Once hangi davranisin dogru olduguna karar ver: testler mi eski, kod mu yanlis?
2. `filter_already_ingested` ya geri eklenmeli ya da test kaldirilmali/guncellenmeli.
3. `crawler_db.DB_PATH` testlerde override edilebilir hale getirilmeli.
4. CI, `pip install -r requirements.txt` kullanmali.
5. Testleri geciren minimum PR hazirlanmali.

### P0 - Crawler ile bulunan PDF dokumanlari ingestion tarafinda yanlis akistan geciyor

`data_ingestion._load_crawled_documents` icinde crawler sonucundaki text sayfalari ve document linkleri tek listeye birlestiriliyor:

- `data_ingestion.py:210`

Sonra listedeki her URL icin ayni metod cagriliyor:

- `data_ingestion.py:226`: `scraper.scrape_page_linked_pdfs(url)`

Bu metod PDF URL'leri icin dogru giris noktasi degil. PDF'ler icin `WebScraper._pdf_url_to_documents` veya public bir `scrape_document_url` benzeri yol kullanilmasi gerekiyor. Mevcut akista crawler tarafindan "document" diye siniflanan bir PDF linki HTML sayfasi gibi indirilmeye ve parse edilmeye calisabilir.

Etki: Bilgi tabanina girmesi gereken yonetmelik PDF'leri eksik veya hatali girer. Bu da RAG'in en kritik vaadini, yani resmi belgelerden cevap vermesini zayiflatir.

Onerilen cozum:

- `result.text_pages` ve `result.document_links` ayri islenmeli.
- PDF/DOCX gibi dokumanlar icin ayri extractor pipeline kurulmalidir.
- PDF URL'leri icin her sayfa metadata'sinda `source`, `page`, `title`, `content_hash` korunmalidir.
- Crawler ingestion icin birim test eklenmeli: "PDF linki geldi -> `_pdf_url_to_documents` cagrildi".

### P0 - Mevcut ChromaDB kapsami cok dar

Yerel ChromaDB incelendi:

```text
toplam vektor: 38
benzersiz kaynak: 3
```

Kaynak dagilimi:

```text
20 chunk: 2025-2026 Genel Akademik Takvimi PDF
15 chunk: https://www.selcuk.edu.tr
3 chunk : https://yemek.selcuk.edu.tr/Menu/MenuGetir
```

Etki: Uygulama arayuzunde staj, burs, cift ana dal, diploma eki gibi ornek sorular var; fakat mevcut bilgi tabani bu belgeleri kapsamiyor gibi gorunuyor. Kullanici bu sorulari sordugunda sistem ya cevap veremeyecek ya da alakasiz kaynaklardan cevap uretmeye zorlanacak.

Onerilen cozum:

- Teslim icin kontrollu, tekrar uretilebilir bir seed listesi hazirlanmali.
- En az su belge gruplari kesin indexlenmeli: egitim-ogretim yonetmeligi, staj yonergeleri, burs yonergesi, cift ana dal/yandal, diploma/diploma eki, mazeret, akademik takvim, yemek/duyuru gibi dinamik kaynaklar.
- Index build sonrasi otomatik rapor uretilmeli: toplam chunk, benzersiz kaynak, kaynak tipi, basarisiz URL'ler, OCR kullanilan PDF sayisi.

### P0 - Admin paneli varsayilan sifre ile acilabiliyor

`app.py:716`:

```python
if pw == os.getenv("ADMIN_PASSWORD", "admin123"):
```

`.env.example:39`:

```env
ADMIN_PASSWORD=admin123
```

Etki: Canli uygulamada `ADMIN_PASSWORD` tanimli degilse admin paneli herkesin tahmin edebilecegi `admin123` ile acilir. Panel su anda sadece istatistik/log gosteriyor gibi gorunse de bu davranis guvenlik acisindan kabul edilemez.

Onerilen cozum:

- Varsayilan sifre kaldirilmali.
- `ADMIN_PASSWORD` yoksa admin paneli kapali olmali.
- Sifre hash'li saklanmali veya Streamlit secrets kullanilmali.
- Giris denemeleri rate limitlenmeli.

### P1 - CI gercek bagimliliklari kurmuyor

`.github/workflows/ci.yml:26-27`:

```yaml
run: pip install pytest langchain-core langchain-groq langchain-huggingface langchain-chroma
```

Fakat proje `requirements.txt` icinde `requests`, `beautifulsoup4`, `lxml`, `pypdf`, `trafilatura`, `rank_bm25`, `flashrank`, `pdf2image`, `pytesseract` gibi baska bagimliliklar da kullaniyor.

Etki: CI yerel ortami temsil etmiyor. Testler bugun gecse bile GitHub Actions farkli sekilde kirilabilir.

Onerilen cozum:

```yaml
- name: Bagimliliklari yukle
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
```

Ek olarak OCR testleri icin sistem paketleri gerekiyorsa CI'de `apt-get install tesseract-ocr poppler-utils` eklenmeli veya OCR testleri mocklanmali.

### P1 - Bagimliliklar versiyonsuz

`requirements.txt` tamamen versiyonsuz paketlerden olusuyor.

Etki:

- LangChain ekosistemi hizli degistigi icin bugun calisan kod yarin kirilabilir.
- Bitirme projesi tesliminden once "benim makinemde calisiyor" riski artar.

Onerilen cozum:

- `requirements.in` + `pip-tools` veya dogrudan pinlenmis `requirements.txt`.
- En azindan major-risk paketleri pinlenmeli: `langchain-*`, `chromadb`, `streamlit`, `sentence-transformers`, `flashrank`.

### P1 - Git durumunda veri artefaktlari karisik

`git status` sonucunda:

- Eski Chroma index dosyalari silinmis gorunuyor.
- Yeni Chroma index klasorleri izlenmemis.
- `data/` altindaki PDF'ler silinmis gorunuyor.
- `crawler_state.db` izlenmemis.
- `chroma_db/chroma.sqlite3` degismis.

Etki: Repo klonlandiginda bilgi tabani hangi durumda gelecek belirsiz. Teslimde demo bozulabilir.

Onerilen cozum:

Iki stratejiden biri secilmeli:

1. Reproducible build: `chroma_db/`, `crawler_state.db`, `failed_docs.json` repo disinda tutulur; `python data_ingestion.py --crawl --clear` veya seed manifest ile yeniden uretilir.
2. Frozen demo DB: teslim icin temiz bir `chroma_db/` snapshot'i commitlenir; hangi kaynaklardan uretildigi raporlanir.

Bitirme projesi icin en temiz yol: seed manifest + yeniden uretilebilir build + opsiyonel frozen demo DB.

## 3. RAG Kalitesi ve Dogruluk

### Guclu taraflar

- `intfloat/multilingual-e5-small` Turkce icin makul bir embedding secimi.
- BM25 + vector ensemble arama, yonetmelik gibi terim hassasiyeti yuksek belgelerde iyi fikir.
- FlashRank reranking eklenmis.
- Promptta "context yoksa uydurma" ve inline citation kurallari var.
- Sohbet gecmisi icin query rewrite dusunulmus.

### Gelistirilmesi gerekenler

1. `format_context` kaynaklari ham URL/path olarak veriyor (`rag_engine.py:232-234`). Kullanici arayuzunde kaynak listesi ayrica var, fakat LLM context'inde kaynaklar daha okunur olursa citation kalitesi artar.
2. Reranker threshold, `metadata["relevance_score"]` yoksa `1.0` kabul ediyor. Bu durumda esik pratikte devre disi kalabilir.
3. Her kullanici sorusunda potansiyel olarak 4 LLM cagrisi var: rewrite, multi-query, final answer, followup. Bu Groq rate limit ve gecikme riskini artirir.
4. Degerlendirme seti yok. RAG projesi icin en kritik eksiklerden biri bu.

Onerilen RAG degerlendirme seti:

- 30-50 soru.
- Her soru icin beklenen kaynak URL/PDF ve ideal kisa cevap.
- Metrikler: kaynak isabeti, answer groundedness, citation precision, "cevap yok" dogrulugu, latency.
- Sunumda tablo olarak gosterilmeli.

## 4. Crawler / Scraper / Ingestion Tasarimi

### Guclu taraflar

- robots.txt kontrolu var.
- Domain whitelist opsiyonu var.
- Timeout, retry, backoff var.
- OCR fallback var.
- CSS selector ile spesifik bolum cekme dusunulmus.
- SQLite crawler state ile incremental mantik denenmis.

### Riskler

1. Varsayilan domain whitelist kapali (`.env.example:6`). Bu, URL dosyasina yanlis veya kotu niyetli bir domain girerse dis kaynaklarin indexlenmesine yol acabilir.
2. `.env.example:12` SSL dogrulamayi varsayilan olarak `false` gosteriyor. README'deki ornek ise `true`. Bu tutarsizlik guvenlik ve teslim kalitesi acisindan duzeltilmeli.
3. `WebScraper._request_with_retry` SSL hatasinda `verify=False` fallback yapabiliyor (`web_scraper.py:518-526`). Bu kurumsal aglarda pratik olabilir, ama raporda "kontrollu fallback" olarak aciklanmali ve varsayilan kapali dusunulmeli.
4. State skip mantigi yeni link kesfini sinirlayabilir. `web_crawler.py:191-200` basarili gorulen sayfayi tekrar fetch etmeden sonuca ekliyor; bu sayfadaki yeni linkler kesfedilmez.
5. `_delete_old_vectors(url)` sadece `source == url` olan vektorleri siliyor (`data_ingestion.py:161-174`). Bir sayfadan linkli PDF'ler geldiyse veya kaynak URL degistiyse eski chunk'lar kalabilir.

## 5. Frontend / UX

### Guclu taraflar

- Streamlit ile hizli demo yapisi uygun.
- Chat gecmisi, kaynak expander'i, feedback, markdown indirme, takip sorulari var.
- Hata mesajlari rate limit, API key ve baglanti hatalarini ayiriyor.
- Sidebar ve mod secimi sunumda anlatilabilir.

### Gelistirme onerileri

1. `app.py` cok buyuk tek dosya. UI, auth, chat orchestration ve styling ayrilmali.
2. Admin paneli su anda ingestion/yeniden indexleme icin gercek kontrol sunmuyor; sadece sayac/log gosteriyor. Ya sade tutulmali ya da gercek admin islevleri eklenmeli.
3. CSS cok uzun ve Streamlit internal selector'lerine bagimli. Streamlit guncellemesiyle tasarim kirilabilir.
4. `st.session_state.yeni_dokumanlar` var ama UI'da dosya yukleme akisi gorunmuyor. Ya ozellik tamamlanmali ya da koddan kaldirilmali.
5. Kaynak expander'inda kaynak preview'i var, bu iyi. Ancak PDF sayfa numarasi ve dokuman tipi de gosterilmeli.

## 6. Guvenlik ve Operasyon

Kritik maddeler:

- Varsayilan admin sifresi kaldirilmali.
- Domain whitelist teslimde varsayilan acik olmali.
- SSL verify varsayilan true olmali.
- `.env` repo disinda kalmali; bu dogru sekilde `.gitignore` icinde var.
- `failed_docs.json`, `crawler_state.db`, `chroma_db/` icin commit stratejisi netlestirilmeli.
- Loglara kullanici sorusu ve cevap yaziliyor; bu KVKK/acik veri bakimindan not edilmeli.

## 7. Dokumantasyon ve Sunum Hazirligi

README iyi bir baslangic, fakat teslim icin su belgeler eklenmeli:

1. Mimari diyagram.
2. Veri akisi diyagrami: crawler -> scraper/OCR -> chunker -> metadata -> Chroma -> retriever -> LLM.
3. RAG degerlendirme raporu.
4. Kurulum ve demo senaryosu.
5. Basarisiz URL ve veri kapsami raporu.
6. Guvenlik/etik notu: resmi kaynak, hata yapabilir uyarisi, robots.txt saygisi.

## 8. Onerilen Yol Haritasi

### Asama 1 - Temel saglamlastirma

- Testleri guncelle ve gecir.
- CI'i `requirements.txt` ile calistir.
- Admin sifre fallback'ini kaldir.
- PDF ingestion bug'ini duzelt.
- Chroma/index stratejisini netlestir.

### Asama 2 - Bilgi tabani kalitesi

- Kontrollu seed manifest hazirla.
- Tum kritik yonetmelikleri indexle.
- Build sonunda kaynak/chunk raporu uret.
- `failed_docs.json` raporunu teslim ekine koy.

### Asama 3 - RAG kalite olcumu

- Golden question set hazirla.
- Kaynak isabeti ve cevap dogrulugu olc.
- Threshold ve reranker ayarlarini bu sete gore kalibre et.

### Asama 4 - Sunum parlatma

- README ve tasarim raporunu guncelle.
- Mimari diyagram ekle.
- Demo icin 5 guclu senaryo hazirla:
  - Akademik takvim tarihi
  - Yemekhane bilgisi
  - Staj yonergesi
  - Cift ana dal basvuru kosullari
  - Belgede olmayan bilgi sorusu

## 9. Kisa Sonuc

Bu proje fikir ve teknik kapsam olarak bitirme projesi icin iyi bir seviyede. En buyuk eksik "ozellik ekleme" degil, guvenilirlik ve tekrar uretilebilirlik. Testler gecmeli, bilgi tabani kapsami kanitlanmali, PDF ingestion duzeltilmeli ve admin guvenligi toparlanmali. Bunlar yapildiginda proje hem sunumda daha ikna edici olur hem de gercek kullanima daha yakin bir muhendislik urunune donusur.
