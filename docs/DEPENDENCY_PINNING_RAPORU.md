# Dependency Pinning Raporu

## Neden Pinleme Yapildi?

Proje Hugging Face Spaces Docker ortaminda calisiyor ve runtime zinciri Streamlit, ChromaDB, local embedding modeli, LangChain adapterleri ve Groq istemcisine bagli. Bu paketlerin unpinned kalmasi, yeni upstream surumleri geldikce ayni commit'in farkli gunlerde farkli dependency kombinasyonlariyla build edilmesine yol acabilir.

Bu calismada amac bugun test ve smoke kontrollerinden gecen dependency kombinasyonunu sabitlemek, HF build'lerini daha deterministik hale getirmek ve ileride paket degisikligi yapildiginda hangi kontrollerin calistirilmasi gerektigini netlestirmektir.

## Pinlenen Kritik Paketler

`requirements.txt` icindeki kritik runtime paketleri local calisan ortamla uyumlu olarak pinlendi:

- `streamlit==1.57.0`
- `chromadb==1.5.9`
- `sentence-transformers==5.4.1`
- `transformers==4.57.3`
- `torch==2.9.1`
- `groq==0.37.1`
- `langchain==1.2.18`
- `langchain-core==1.4.0`
- `langchain-community==0.4.1`
- `langchain-huggingface==1.2.2`
- `langchain-chroma==1.1.0`
- `langchain-groq==1.1.2`
- `rank-bm25==0.2.2`
- `flashrank==0.2.10`
- `python-dotenv==1.2.1`
- `requests==2.32.5`
- `httpx==0.28.1`
- `pytest==9.0.3`

## Runtime Bagimliliklari

Ana runtime yolu su paketlere dayanir:

- Streamlit UI: `streamlit`
- ChromaDB snapshot okuma: `chromadb`, `langchain-chroma`
- Embedding: `sentence-transformers`, `transformers`, `torch`, `langchain-huggingface`
- LLM provider: `groq`, `langchain-groq`
- Retrieval/rerank: `langchain`, `langchain-community`, `rank-bm25`

FlashRank paketi pinli kaldi, ancak Dockerfile'da `FLASHRANK_ENABLED=false` oldugu icin runtime'da varsayilan olarak kapali.

## Ingestion / OCR Bagimliliklari

Su paketler runtime cevap yolundan cok ingestion, crawling veya PDF/OCR yardimci islerinde kullanilir:

- `pypdf`
- `beautifulsoup4`
- `lxml`
- `trafilatura`
- `pytesseract`
- `pdf2image`
- `tqdm`

Bu fazda buyuk dependency refactor yapilmadi ve bu paketler silinmedi. Ayrica yeni ingestion calistirilmadi.

## Agir Paket Riski

`torch`, `sentence-transformers`, `chromadb` ve `flashrank` build boyutu acisindan en dikkatli izlenmesi gereken paketlerdir. Yeni agir paket, `torchvision`, CUDA veya nvidia paketi eklenmedi. `torch` surumu mevcut calisan ortamla ayni olacak sekilde pinlendi.

## Docker / HF Uyumluluk Notu

Dockerfile `python:3.11-slim` uzerinde `requirements.txt` kurar. Bu degisiklik Dockerfile'a OS paketi eklemez. HF CPU ortaminda runtime yolunu korumak icin FlashRank default kapali kalir ve ChromaDB snapshot deploy workflow'u tarafindan Git LFS ile gonderilmeye devam eder.

## Dogrulama

Import smoke:

```bash
USE_TF=0 TRANSFORMERS_NO_TF=1 python -c "import streamlit, chromadb, sentence_transformers, groq; print('runtime imports ok')"
```

Sonuc:

```text
runtime imports ok
```

Not: Lokal Windows ortaminda TensorFlow/Keras paketleri global olarak kurulu oldugundan, `sentence_transformers` dogrudan import edildiginde Transformers'in TF entegrasyon yoluna sapabildigi goruldu. Proje runtime'i TensorFlow kullanmaz; bu nedenle import smoke `USE_TF=0` ile calistirildi. HF Docker requirements icine `tensorflow` veya `tf-keras` eklenmedi.

General smoke:

```bash
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
```

Sonuc:

- Toplam soru: 34
- Beklenen answer: 23
- Beklenen fallback: 11
- `triage_status_counts`: `ok`, `inspect_top_document`, `answer_expected_without_source`, `fallback_expected_with_source`

Test:

```bash
python -m pytest tests/ -v
```

Sonuc:

```text
197 passed, 2 skipped
```

## Degistirilmeyenler

- Runtime RAG davranisi degistirilmedi.
- `app.py`, `rag_engine.py`, `retrieval_rerank.py` dosyalarina dokunulmadi.
- ChromaDB icerigi degistirilmedi.
- Yeni ingestion calistirilmadi.
- `.env`, secret ve `data/*.pdf` dosyalari commit kapsaminda degildir.
