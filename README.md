# Selcuk RAG Asistan

Selcuk RAG Asistan, Selcuk Universitesi yonetmelik, yonerge ve resmi dokumanlarini sorgulamak icin gelistirilmis bir RAG uygulamasidir. Sistem Streamlit arayuzu, ChromaDB snapshot'i, metadata-aware rerank katmani, kaynak paneli ve cevap guvenligi guardrail'leri ile calisir.

Ana deploy hedefi Hugging Face Spaces Docker ortamidir. Streamlit Community Cloud artik ana deploy ortami olarak onerilmez; bellek limitleri nedeniyle kalici ve daha rahat calisan hedef HF Spaces olarak belirlenmistir.

## Mevcut Durum

- 149 kaynak ve 2985 chunk iceren ChromaDB snapshot repoda korunur.
- ChromaDB runtime icin gereklidir; yeni ingestion calistirmadan uygulama acilabilir.
- Metadata-aware rerank aktif.
- Source binding ve inline citation eslesmesi uygulanir.
- General RAG guardrails aktif:
  - alakasiz kaynak filtreleme
  - used-source-only kaynak paneli
  - model tarafindan uretilen kaynak/URL bloklarini temizleme
  - dusuk kaliteli cevap tespiti
  - operasyonel/guncel bilgi sorularinda safe fallback
- Groq LLM entegrasyonu kullanilir.
- OpenAI entegrasyonu bu surumde yoktur.

## Mimari

| Katman | Dosya / Teknoloji | Gorev |
| --- | --- | --- |
| UI | `app.py`, Streamlit | Sohbet arayuzu, kaynak paneli, session state |
| RAG motoru | `rag_engine.py` | Retrieval, prompt, streaming cevap, guardrails |
| Rerank | `retrieval_rerank.py` | Metadata-aware legal/source rerank |
| Vector DB | `chroma_db/`, ChromaDB | Tracked runtime snapshot |
| Embedding | `intfloat/multilingual-e5-small` | Local sentence-transformers embedding |
| LLM | Groq API | Cevap uretimi |
| Kaynak kontrolu | `source_manifest.json`, `source_access_policy.py` | Resmi kaynak ve erisim politikasi |
| Test | `tests/` | Unit ve regression testleri |

## Klasor Yapisi

```text
.
|-- app.py
|-- rag_engine.py
|-- retrieval_rerank.py
|-- source_manifest.json
|-- source_inventory.py
|-- source_access_policy.py
|-- chroma_db/
|-- tests/
|-- scripts/
|-- evaluation/
|-- docs/
|-- .streamlit/config.toml
|-- Dockerfile
|-- requirements.txt
|-- README.md
```

Ayrintili aciklama icin bkz. `docs/PROJECT_STRUCTURE.md`.

## Kurulum

Python 3.11+ onerilir.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ortam Degiskenleri

`.env.example` dosyasini kopyalayip yerelde `.env` olusturun:

```bash
cp .env.example .env
```

Temel degiskenler:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
ADMIN_PASSWORD=...
```

`.env` ve secret/API key dosyalari repoya commit edilmez.

## Local Calistirma

Mevcut ChromaDB snapshot ile:

```bash
streamlit run app.py
```

Index durumunu kontrol etmek icin:

```bash
python check_chroma_health.py --db-path chroma_db --json
```

Yeni ingestion bu normal calisma akisi icin gerekli degildir.

## Hugging Face Deploy

HF Spaces Docker deploy hedefi:

```text
https://huggingface.co/spaces/maliblgn/selcuk-rag-asistan
```

Deploy dosyalari:

- `Dockerfile`
- `.dockerignore`
- `.streamlit/config.toml`
- `requirements.txt`
- runtime kodu
- tracked `chroma_db/` snapshot

`main` branch guncellendiginde GitHub Actions otomatik olarak Hugging Face Space deploy'u yapar. Bunun icin GitHub repo ayarlarinda `HF_TOKEN` secret tanimli olmalidir. HF Space Docker SDK ile calisir ve uygulama portu `7860` olarak ayarlanir. Deploy workflow'u README frontmatter'ini otomatik uretir ve ChromaDB snapshot dosyalarini Git LFS ile HF Space reposuna gonderir.

Detaylar icin bkz. `docs/HF_SPACES_DEPLOY_RAPORU.md`.

## Testler

```bash
python -m pytest tests/ -v
```

CI ve lokal testler RAG davranisinin, source binding'in, retrieval rerank'in ve guardrail mantiginin bozulmamasini hedefler.

## Bilinen Sinirlamalar

- Saat, ucret, yemekhane, kutuphane calisma saatleri gibi guncel operasyonel bilgiler corpus icinde acikca yoksa cevaplanmaz; safe fallback doner.
- Sistem resmi kaynak yerine gecmez; onemli kararlar icin ilgili resmi belge kontrol edilmelidir.
- OCR veya PDF metin kalitesi nedeniyle bazi dokumanlarda eksik chunk olasidir.
- ChromaDB snapshot sabittir; yeni kaynak eklemek ayrica planlanan ingestion islemi gerektirir.

## Gelistirme Akisi

- `main` kararlı surumdur.
- `dev` aktif gelistirme dalidir.
- Yeni isler varsayilan olarak `dev` uzerinde yapilir.
- Testler gecmeden `main`e alinmaz.
- Buyuk davranis degisiklikleri icin once kapsam netlestirilir.

Detaylar icin bkz. `docs/DEVELOPMENT_WORKFLOW.md`.

## Guvenlik

Repoya commit edilmemesi gerekenler:

- `.env`
- API key ve secret degerleri
- `data/*.pdf`
- `chroma_db_legal_test/`
- lokal healthcheck ve preview ciktilari

`chroma_db/` bu projede istisnadir: runtime snapshot olarak tracked kalir.

## Ornek Sorular

- `AKTS nedir?`
- `Tez izleme komitesi kac ogretim uyesinden olusur?`
- `Doktora yeterlik sinavlari ile ilgili esaslar nelerdir?`
- `Selcuk Universitesi'nde ders kredisi nasil hesaplanir?`
