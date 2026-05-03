# 🎓 Selçuk Üniversitesi RAG Asistanı

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://selcuk-rag-asistan.streamlit.app/)
[![CI](https://github.com/maliblgn/Selcuk_RAG_Asistan/actions/workflows/ci.yml/badge.svg)](https://github.com/maliblgn/Selcuk_RAG_Asistan/actions/workflows/ci.yml)

🔗 **Canlı Demo:** [https://selcuk-rag-asistan.streamlit.app](https://selcuk-rag-asistan.streamlit.app/)

Selçuk Üniversitesi yönetmeliklerini sorgulayan, yapay zeka destekli bir chatbot uygulamasıdır. `selcuk.edu.tr` adresini otonom olarak tarayarak (web sayfaları ve PDF'ler) bilgi çıkarır ve soruları yanıtlar.

## 🛠️ Teknoloji Yığını

| Bileşen | Teknoloji |
|---|---|
| **UI** | Streamlit |
| **LLM** | Groq API (Llama 3.1 8B Instant) |
| **Embedding** | HuggingFace `intfloat/multilingual-e5-small` |
| **Vektör DB** | ChromaDB |
| **Framework** | LangChain |

## 📋 Gereksinimler

- Python 3.11+
- Groq API anahtarı ([console.groq.com](https://console.groq.com) üzerinden alınır)

## 🚀 Kurulum

```bash
# 1. Sanal ortam oluştur
python -m venv venv

# 2. Sanal ortamı aktifleştir
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. API anahtarını ayarla
cp .env.example .env
# .env dosyasına GROQ_API_KEY değerini girin

# 5. Veritabanını oluştur (otonom web taraması ile)
python data_ingestion.py --crawl

# 6. Uygulamayı başlat
streamlit run app.py
```

## 🌐 Otonom Web Tarama & Scraping (V2)

Sistem tamamen otonom olarak üniversite web sitesini tarayacak ve içeriği bilgi tabanına ekleyecek şekilde tasarlanmıştır.

- Otonom tarama (`crawl=True`) ile belirtilen derinliğe (depth) kadar alt sayfalar otomatik keşfedilir.
- Hem HTML içerikleri hem de web sitesine yüklenmiş `.pdf` uzantılı dokümanlar otomatik olarak indirilip okunur.
- robots.txt: izin yoksa sayfa otomatik atlanir
- Kullanım: Yalnızca CLI üzerinden veya (eklenirse) Admin paneli üzerinden yönetilir. Streamlit arayüzü son kullanıcı için sadece sohbete odaklanmıştır.
- Spesifik bolum cekimi: URL satirina `|css=.hedef` ekleyerek sadece ilgili HTML bolumu alinabilir
- PDF metni 100 karakterin altindaysa OCR fallback otomatik devreye girer (`pdf2image` + `pytesseract`, `lang="tur"`)
- Hem normal okuma hem OCR basarisiz olursa kayitlar `failed_docs.json` dosyasina yazilir

### Ortam ayarlari (.env)

Web scraping davranisini `.env` ile yonetebilirsiniz:

```env
WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST=false
WEB_SCRAPER_ALLOWED_DOMAINS=selcuk.edu.tr,webadmin.selcuk.edu.tr
WEB_SCRAPER_VERIFY_SSL=true
WEB_SCRAPER_ALLOW_INSECURE_FALLBACK=true
WEB_SCRAPER_TIMEOUT_SEC=10
WEB_SCRAPER_MAX_RETRIES=3
WEB_SCRAPER_BACKOFF_SEC=1.0
WEB_SCRAPER_MIN_CONTENT_CHARS=300
```

Domain kisitlamasi acmak icin `WEB_SCRAPER_ENABLE_DOMAIN_WHITELIST=true` yapin.
`WEB_SCRAPER_ALLOWED_DOMAINS` yalnizca whitelist aktifken uygulanir.

Kurumsal aglarda SSL sertifika zinciri sorunu varsa once otomatik fallback devreye girer.
Gerekirse gecici olarak `WEB_SCRAPER_VERIFY_SSL=false` kullanabilirsiniz.

OCR fallback icin sistemde asagidaki araclarin kurulu olmasi gerekir:

- Tesseract OCR (`tesseract`)
- Poppler (`pdftoppm`)

### CLI ile kullanım

```bash
# Otonom web taramasını başlat
python data_ingestion.py --crawl

# Kontrollü kaynak manifestini işle
python data_ingestion.py --manifest source_manifest.json --clear

# Manifest seed'lerini crawler ile keşfedip bilgi tabanını yeniden üret
python data_ingestion.py --manifest source_manifest.json --crawl --crawl-depth 2 --crawl-max-pages 80 --clear

# URL listesini işle
python data_ingestion.py --urls urls.txt

# Veritabanını sıfırlayıp otonom olarak yeniden oluştur
python data_ingestion.py --crawl --clear
```

### Bilgi tabanı kapsam raporu

```bash
python index_report.py
python index_report.py --json --out index_report.json
```

`source_manifest.json`, yerel PDF listesi değil; resmi web tarama başlangıç noktalarını (`crawl_seeds`), web üzerinden doğrudan bilinen resmi kaynakları (`known_direct_sources`) ve taramada bulunması beklenen doküman başlıklarını (`expected_documents`) izler.

### Web keşif raporu

```bash
python discovery_report.py --max-depth 1 --max-pages 20
python discovery_report.py --json --out discovery_report.json
```

Bu rapor ChromaDB'yi değiştirmez; sadece resmi web sayfalarından kaç sayfa ve kaç doküman linki keşfedildiğini, beklenen yönerge/yönetmelik başlıklarının taramada yakalanıp yakalanmadığını gösterir.

## 🧪 Testler

```bash
pytest tests/ -v
```

## 📂 Proje Yapısı

```
Selcuk_RAG_Asistan/
├── app.py                # Streamlit arayüzü ve sohbet mantığı
├── rag_engine.py         # RAG zinciri, retriever ve LLM motoru
├── data_ingestion.py     # Web Crawler → ChromaDB veri aktarım scripti
├── web_scraper.py        # URL doğrulama, robots ve HTML metin ayıklama
├── requirements.txt      # Bağımlılıklar
├── .env.example          # Ortam değişkenleri şablonu
├── chroma_db/            # Vektör veritabanı
├── tests/                # Pytest birim testleri
│   ├── test_rag_engine.py
│   └── test_web_scraper.py
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions CI pipeline
└── .devcontainer/        # GitHub Codespaces yapılandırması
```

## 💡 Kullanım

- **Soru sorun**: Metin kutusuna yönetmeliklerle ilgili sorularınızı yazın.
- **Kaynak alıntısı**: Her yanıtın sonunda bilgiyi hangi URL'den veya kaynaktan aldığını belirten alıntı (`Kaynak: https://...`) bilgisi görünür.

## ☁️ Codespaces ile Kullanım

Proje, GitHub Codespaces ile tek tıkla çalışmaya hazırdır. `.devcontainer` yapılandırması otomatik olarak tüm bağımlılıkları kurar ve Streamlit'i başlatır.

> **Not**: `GROQ_API_KEY` ortam değişkenini Codespaces Secrets'a eklemeyi unutmayın.

## Crawler Guvenlik Politikasi

Proje web-only veri stratejisi kullanir, ancak otomatik tarama `robots.txt` ve kurumsal erisim politikasina uygun olmak zorundadir. Kimlik dogrulama otomatik crawler izni yerine gecmez; robots tarafindan engellenen veya robots dosyasi okunamayan URL'ler bilgi tabanina alinmaz.

Kontrollu demo bilgi tabani icin:

```bash
python data_ingestion.py --urls curated_web_sources.txt --clear
```

Kesif raporu almak icin:

```bash
python discovery_report.py --max-depth 0 --max-pages 3
```

Ayrintili kurallar `CRAWLING_POLICY.md` dosyasindadir. `source_manifest.json` icinde `active: false` veya `requires_permission: true` olan kaynaklar belgelenir, fakat otomatik islenmez.
