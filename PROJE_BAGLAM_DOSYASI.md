# Selcuk RAG Cloud - ChatGPT Proje Baglam Dosyasi

Bu dosya, projeyi ChatGPT'ye veya baska bir yapay zeka aracina tek seferde tanitmak icin hazirlanmistir. Projenin amaci, teknolojileri, mimarisi, dosya yapisi, veri akisi, calistirma komutlari ve dikkat edilmesi gereken noktalar burada ozetlenir.

## 1. Proje Ozeti

Selcuk RAG Cloud, Selcuk Universitesi'nin resmi web sayfalari ve PDF dokumanlari uzerinden cevap verebilen RAG tabanli bir chatbot uygulamasidir. Kullanici Streamlit arayuzunden soru sorar; sistem soruya uygun dokuman parcalarini ChromaDB vektor veritabanindan getirir, Groq uzerindeki Llama modeliyle Turkce ve kaynak numarali cevap uretir.

Temel hedef:

- Selcuk Universitesi yonetmelikleri, yonergeleri, akademik takvimleri, burs/staj/diploma gibi ogrenci belgeleri ve kampus yasami kaynaklari hakkinda resmi kaynaklara dayali cevap vermek.
- Bilgi tabanini mumkun oldugunca web uzerindeki resmi kaynaklardan, robots.txt ve domain politikalarina saygili sekilde uretmek.
- Cevaplarda uydurma yapmamak; bilgi dokumanlarda yoksa bunu acikca belirtmek.

## 2. Ana Kullanim Senaryolari

- Ogrenci "Staj muafiyet sartlari nelerdir?" diye sorar.
- Sistem bu soruyu gerekirse yeniden yazar ve alternatif arama sorgulari uretir.
- ChromaDB icindeki ilgili PDF/web sayfasi parcalarini BM25 + vektor arama ile bulur.
- FlashRank reranker ile en alakali parcalari secer.
- LLM, yalnizca gelen baglama dayanarak Turkce cevap uretir.
- Cevap icinde kaynak numaralari `[1]`, `[2]` seklinde gosterilir.
- Arayuzde kullanici kaynaklari acabilir, sohbeti temizleyebilir, cevabi indirebilir ve takip sorulari gorebilir.

## 3. Teknoloji Yigini

| Katman | Teknoloji / Kutuphane | Gorev |
|---|---|---|
| Arayuz | Streamlit | Chat arayuzu, sidebar, admin paneli, kaynak gosterimi |
| LLM | Groq API, varsayilan `llama-3.1-8b-instant` | Soru yeniden yazma, multi-query, cevap uretme, takip sorusu |
| Embedding | HuggingFace `intfloat/multilingual-e5-small` | Turkce/metin embedding uretimi |
| Vektor DB | ChromaDB | Dokuman chunk'larini kalici vektor veritabaninda saklama |
| RAG framework | LangChain | Prompt, retriever, document, chain ve parser altyapisi |
| Keyword retrieval | `rank_bm25` / LangChain BM25Retriever | Terim bazli arama |
| Hybrid retrieval | EnsembleRetriever | BM25 ve vektor aramayi 0.5/0.5 agirlikla birlestirme |
| Reranking | FlashRank | Aday dokumanlari yeniden siralama |
| Web scraping | requests, BeautifulSoup, lxml, trafilatura | HTML indirme, temizleme, ana icerik cikarma |
| PDF okuma | pypdf | PDF metin cikarma |
| OCR fallback | pdf2image, pytesseract | Metni cikmayan PDF'lerde OCR denemesi |
| Test | pytest | Birim testleri |
| CI | GitHub Actions | Otomatik test calistirma |
| Ortam | python-dotenv, `.env` | API anahtari ve crawler/scraper ayarlari |

## 4. Ana Dosya ve Moduller

| Dosya / Klasor | Rol |
|---|---|
| `app.py` | Streamlit uygulamasi. Chat UI, mod secimi, admin paneli, kaynak expander'i, hata yonetimi ve cevap akisini yonetir. |
| `rag_engine.py` | RAG motoru. Embedding, ChromaDB, BM25/vector hibrit retriever, FlashRank reranker, promptlar, cevap streaming ve kaynak envanteri mantigi burada. |
| `data_ingestion.py` | Web/PDF kaynaklarini okuyup chunk'lara bolerek ChromaDB'ye yazan ana ingestion scripti. CLI argumanlarini da yonetir. |
| `web_scraper.py` | URL dogrulama, domain whitelist, robots.txt kontrolu, HTTP retry, HTML temizleme, PDF indirme, PDF/OCR metin cikarma ve Document uretimi. |
| `web_crawler.py` | BFS tabanli otonom link kesfi. Metin sayfalari ve dokuman linklerini bulur. |
| `crawler_config.py` | Crawler icin user-agent, exclude pattern, priority pattern, dokuman uzantilari ve timeout ayarlari. |
| `crawler_db.py` | Crawler state bilgisini SQLite uzerinde tutar. URL hash, durum ve metadata bilgileriyle incremental islemeye yardim eder. |
| `content_processor.py` | trafilatura tabanli ana icerik cikarma, header-aware/semantic chunking ve metadata zenginlestirme yardimcilari. |
| `flash_channel.py` | Oncelikli URL'leri belirli araliklarla kontrol edip degisiklik varsa vektor DB'yi guncellemek icin tasarlanmis izleme dongusu. |
| `index_report.py` | ChromaDB kapsam raporu uretir. Toplam chunk, kaynak sayisi ve kaynak tipleri gibi bilgiler verir. |
| `discovery_report.py` | Web kesif raporu uretir; ChromaDB'yi degistirmeden kaynak kesif kapasitesini analiz eder. |
| `source_inventory.py` | Kaynak envanteri uretimi icin yardimci script. |
| `source_manifest.json` | Resmi kaynak stratejisi. Crawl seed'leri, dogrudan bilinen kaynaklar ve beklenen dokumanlari tutar. |
| `CRAWLING_POLICY.md` | Web tarama, robots.txt, yetkili kaynak modu ve demo veri stratejisini aciklar. |
| `tests/` | RAG, scraper, crawler, ingestion ve content processor testleri. |
| `chroma_db/` | ChromaDB kalici veritabani dosyalari. |
| `.streamlit/config.toml` | Streamlit tema ayarlari. |
| `.github/workflows/ci.yml` | GitHub Actions CI tanimi. |
| `.env.example` | Ortam degiskenleri sablonu. |

## 5. Mimari Genel Bakis

Sistem iki ana hatta ayrilir:

1. Bilgi tabani uretim hatti
2. Soru cevaplama hatti

### 5.1 Bilgi Tabani Uretim Hatti

```text
source_manifest.json / urls.txt / crawler seed
        |
        v
web_crawler.py veya data_ingestion.py
        |
        v
web_scraper.py
  - URL normalize eder
  - Domain whitelist uygular
  - robots.txt kontrol eder
  - HTML/PDF indirir
  - PDF metni cikarir
  - Gerekirse OCR fallback dener
        |
        v
LangChain Document listesi
        |
        v
chunking
  - RecursiveCharacterTextSplitter
  - content_processor.py icinde semantik/header-aware alternatifler
        |
        v
HuggingFace multilingual embedding
        |
        v
ChromaDB (`chroma_db/`)
```

### 5.2 Soru Cevaplama Hatti

```text
Kullanici sorusu (Streamlit)
        |
        v
rag_engine.py
  - Gecmis sohbet varsa soruyu bagimsiz hale getirir
  - Multi-query ile 3 alternatif sorgu uretir
        |
        v
Hybrid retrieval
  - BM25 keyword search
  - Chroma vector search (MMR)
  - EnsembleRetriever ile birlestirme
        |
        v
Deduplication + FlashRank reranking
        |
        v
Baglam formatlama
  - [1] [Kaynak: ...]
  - MAX_CONTEXT_CHARS ile token tasmasini sinirlama
        |
        v
Groq Llama modeli
        |
        v
Turkce, kaynak numarali cevap + takip soru onerileri
```

## 6. RAG Motoru Detaylari

`SelcukRAGEngine` sinifi `rag_engine.py` icindedir.

Baslatilirken:

- `intfloat/multilingual-e5-small` embedding modeli yuklenir.
- `chroma_db/` kalici Chroma veritabanina baglanilir.
- Chroma retriever `search_type="mmr"` ile kurulur.
- DB'deki dokumanlardan BM25 retriever olusturulur.
- BM25 ve vector retriever `EnsembleRetriever` ile 0.5/0.5 agirlikla birlestirilir.
- Groq modeli `GROQ_MODEL` ortam degiskeninden okunur; yoksa `llama-3.1-8b-instant` kullanilir.
- FlashRank yuklenebilirse reranking aktif olur.

Sistem promptunda kritik kurallar:

- Baglamda bilgi yoksa uydurma yapma.
- Rakamlara sadik kal.
- Sadece Turkce cevap ver.
- Cevap icinde inline citation kullan: `[1]`, `[2]`.
- Cevabin sonunda ayrica "Kaynak:" listesi yazma.

Desteklenen cevap modlari:

- `Akademik Rehber`: resmi, ciddi, net dil.
- `Kampus Yasami`: daha samimi ve yardimsever dil.
- `Hizli Arama`: kisa, madde madde cevap.

Ek ozel davranis:

- Kullanici "veritabaninda hangi kaynaklar var?" gibi kaynak envanteri sorarsa LLM'e gitmeden ChromaDB kaynak listesi okunur ve cevap uretilir.

## 7. Streamlit Arayuzu

`app.py`, son kullanici deneyimini yonetir.

Ana arayuz ozellikleri:

- Sayfa basligi: Selcuk RAG Asistani.
- Sidebar'da asistan modu secimi.
- Bilgi tabani/kaynak istatistikleri ve admin paneli.
- Ilk acilista ornek soru butonlari.
- `st.chat_message` tabanli sohbet akisi.
- Cevap beklerken spinner durumlari.
- Cevap sonunda kaynak expander'i.
- Cevabi Markdown olarak indirme.
- Olumlu/olumsuz feedback butonlari.
- LLM tarafindan uretilen takip sorulari.
- Hata durumunda kullaniciya anlasilir mesaj, teknik detay icin expander.

Admin paneli:

- `ADMIN_PASSWORD` ortam degiskeni bos ise admin paneli devre disi kalir.
- Tanimliysa giris alani ile acilir.
- ChromaDB istatistikleri, kaynak turleri ve log gosterimi gibi bakim/izleme islevleri sunar.

## 8. Veri Kaynaklari ve Crawler Politikasi

Proje "web-only discovery" stratejisini hedefler. Yani bilgi tabani normalde yerel PDF klasorunden degil, resmi web kaynaklarindan uretilir.

Kaynak yonetimi:

- `source_manifest.json` aktif/pasif kaynaklari tutar.
- `crawl_seeds`: crawler'in baslayabilecegi sayfalar.
- `known_direct_sources`: dogrudan bilinen web/PDF kaynaklari.
- `expected_documents`: projede kapsanmasi beklenen belge tipleri.

Guvenlik ve etik politika:

- Domain whitelist varsayilan olarak `.env.example` icinde aciktir.
- robots.txt izin vermiyorsa URL otomatik islenmez.
- robots.txt okunamiyorsa sistem guvenli tarafta kalip URL'yi bloklar.
- Kurumsal/yazili izinli kaynaklar icin iki ayar vardir:
  - `AUTHORIZED_SOURCE_MODE=true`
  - `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=true`
- Bu yetkili modlar varsayilan olarak kapali tutulmalidir.

## 9. Kurulum ve Calistirma

Python surumu:

```bash
python 3.11+
```

Sanal ortam:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Ortam degiskenleri:

```bash
copy .env.example .env
```

`.env` icinde en az:

```env
GROQ_API_KEY=...
WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST=true
WEB_SCRAPER_ALLOWED_DOMAINS=selcuk.edu.tr,webadmin.selcuk.edu.tr
ADMIN_PASSWORD=
```

Uygulamayi baslatma:

```bash
streamlit run app.py
```

Bilgi tabanini manifest ile kurma:

```bash
python data_ingestion.py --manifest source_manifest.json --clear
```

Manifest seed'leri ile crawler calistirma:

```bash
python data_ingestion.py --manifest source_manifest.json --crawl --crawl-depth 2 --crawl-max-pages 80 --clear
```

Kontrollu URL listesiyle demo DB kurma:

```bash
python data_ingestion.py --urls curated_web_sources.txt --clear
```

Otonom crawler:

```bash
python data_ingestion.py --crawl --clear
```

Kapsam raporu:

```bash
python index_report.py
python index_report.py --json --out index_report.json
```

Kesif raporu:

```bash
python discovery_report.py --max-depth 1 --max-pages 20
python discovery_report.py --json --out discovery_report.json
```

Testler:

```bash
pytest tests/ -v
```

## 10. Onemli Ortam Degiskenleri

| Degisken | Anlam |
|---|---|
| `GROQ_API_KEY` | Groq API anahtari. |
| `GROQ_MODEL` | Kullanilacak Groq modeli. Yoksa `llama-3.1-8b-instant`. |
| `WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST` | Whitelist aktif mi? Teslim/demo icin `true` onerilir. |
| `WEB_SCRAPER_ALLOWED_DOMAINS` | Izinli domain listesi. |
| `WEB_SCRAPER_VERIFY_SSL` | SSL dogrulamasi. Varsayilan `true`. |
| `WEB_SCRAPER_ALLOW_INSECURE_FALLBACK` | SSL hatasinda guvensiz fallback denensin mi? |
| `WEB_SCRAPER_TIMEOUT_SEC` | Scraper request timeout. |
| `WEB_SCRAPER_MAX_RETRIES` | HTTP retry sayisi. |
| `WEB_SCRAPER_MIN_CONTENT_CHARS` | Sayfa metni icin minimum anlamli karakter esigi. |
| `AUTHORIZED_SOURCE_MODE` | Manifestte izin gerektiren pasif kaynaklari kapsama alir. |
| `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE` | Yazili izin varsa robots engelini loglayarak gecer. |
| `CRAWL_SEED_URL` | Otonom crawler baslangic URL'si. |
| `CRAWL_MAX_DEPTH` | Crawler maksimum derinligi. |
| `CRAWL_MAX_PAGES` | Crawler maksimum sayfa sayisi. |
| `CRAWL_DELAY` | Istekler arasi bekleme. |
| `CRAWL_EXCLUDE_PATTERNS` | URL dislama desenleri. |
| `CRAWL_PRIORITY_PATTERNS` | Crawler kuyrugunda one alinacak desenler. |
| `PRIORITY_URLS` | Flash channel ile izlenecek oncelikli sayfalar. |
| `ADMIN_PASSWORD` | Admin paneli sifresi. Bos ise panel kapali. |

## 11. Veri ve Metadata Mantigi

Scraper ve ingestion surecinde her kaynak LangChain `Document` nesnesine donusturulur.

Beklenen metadata alanlari:

- `source`: URL veya dosya yolu.
- `title`: Kaynak basligi.
- `source_type`: `web_page`, `web_pdf` veya `unknown`.
- `page`: PDF sayfa numarasi gibi sayfa bilgisi.
- `content_hash`: Icerik degisikliklerini yakalamak icin hash.

Bu metadata:

- Eski vektorleri silmek,
- Incremental guncelleme yapmak,
- Kaynak envanteri uretmek,
- UI'da kaynak linki ve baslik gostermek,
- LLM baglaminda kaynak etiketi vermek

icin kullanilir.

## 12. Test ve Kalite Durumu

Projede pytest tabanli testler vardir:

- `test_rag_engine.py`: baglam formatlama, kaynak envanteri, takip sorulari, rewrite mantigi.
- `test_web_scraper.py`: URL dogrulama, robots, scraping, PDF linkleri ve hata senaryolari.
- `test_web_crawler.py`: crawler BFS, state, domain/dislama mantigi.
- `test_data_ingestion_crawl.py`: crawler sonucunun ingestion tarafinda dogru islenmesi.
- `test_content_processor.py`: icerik cikarma, chunking ve metadata mantigi.

Mevcut `PROJE_INCELEME_RAPORU.md` dosyasi projedeki kalite/risk analizini ayrica tutar. O rapor, bu baglam dosyasindan farkli olarak daha cok eksik, risk ve iyilestirme onceliklerine odaklanir.

## 13. Bilinen Riskler ve Dikkat Noktalari

- ChromaDB kapsam raporu duzenli kontrol edilmelidir; cevap kalitesi dogrudan indekslenen kaynak kalitesine baglidir.
- PDF ve HTML kaynaklari ayri extractor akislariyla islenmelidir.
- Domain whitelist ve robots politikasi teslimde acik ve savunulabilir olmalidir.
- `ADMIN_PASSWORD` bos birakilirsa panel kapali kalir; varsayilan kolay sifre kullanilmamalidir.
- `requirements.txt` su an paketleri versiyonsuz listeler; tekrarlanabilir teslim icin versiyon pinleme dusunulmelidir.
- LLM cevap kalitesi icin golden question set ve kaynak isabeti olcumu eklemek faydali olur.
- `.env`, loglar, crawler state ve ChromaDB artefaktlari icin commit stratejisi net tutulmalidir.

## 14. ChatGPT'ye Verilebilecek Kisa Prompt

Asagidaki prompt, bu dosyayla birlikte ChatGPT'ye verilebilir:

```text
Bu dosya Selcuk RAG Cloud projesinin baglam dosyasidir. Proje, Selcuk Universitesi resmi web/PDF kaynaklari uzerinden RAG tabanli cevap veren bir Streamlit chatbot uygulamasidir. Bu baglami oku ve bundan sonraki cevaplarinda projenin mimarisine, dosya yapisina, mevcut teknoloji yigini ve veri akisina uygun oneriler ver. Yeni ozellik veya hata duzeltmesi onerirken mevcut dosyalari ve sorumluluklarini dikkate al.
```

## 15. En Kisa Teknik Ozet

Selcuk RAG Cloud; Streamlit arayuzlu, Groq/Llama destekli, ChromaDB + multilingual-e5-small embedding kullanan bir Turkce RAG asistanidir. `data_ingestion.py`, `web_crawler.py` ve `web_scraper.py` resmi web/PDF kaynaklarini toplayip chunk'lara boler ve ChromaDB'ye yazar. `rag_engine.py`, BM25 + vector hybrid retrieval, multi-query, FlashRank reranking ve kaynak numarali promptlarla cevap uretir. `app.py`, son kullanici sohbet deneyimini ve admin/kaynak gorunumlerini sunar.
