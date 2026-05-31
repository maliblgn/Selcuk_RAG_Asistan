# Selçuk RAG Asistan

Selçuk RAG Asistan, Selçuk Üniversitesi kaynakları, yönetmelikler, yönergeler, web kaynakları ve dinamik kaynaklar üzerinden güvenilir cevap ve kaynak keşfi sağlamayı hedefleyen RAG tabanlı bir asistandır.

Sistem uygun kaynak bulduğunda cevabı inline citation ve kaynak paneliyle sunar. Kaynakta açık bilgi yoksa, güncel operasyonel bilgi gerekiyorsa veya terim eşdeğerliği kaynakta kanıtlanmıyorsa bilgi uydurmamak için güvenli fallback davranışı uygular.

Canlı demo: [Hugging Face Space](https://maliblgn-selcuk-rag-asistan.hf.space)

## Ana Özellikler

- Static ChromaDB RAG snapshot
- Source Discovery Mode
- Dynamic Dining Menu Reader
- Session-only PDF, PDF URL, manual URL & pasted text RAG
- Query Router
- Dynamic Source Registry
- Metadata-aware retrieval/rerank
- Answer grounding evaluation
- Regression suite runner
- ChromaDB local runtime copy
- Safe fallback / no hallucination yaklaşımı

Session-only PDF, PDF URL, manual URL & pasted text RAG, yüklenen PDF, PDF linki, manuel link veya yapıştırılan metin sorularında ham metin/chunk dökmek yerine soru odaklı cevap üretir. E-posta, telefon, dil seviyesi, proje listesi ve başvuru şartları gibi hedef bilgiler kaynak içinden ayıklanır; kaynakta yoksa bilgi uydurulmaz. Hugging Face ortamında dosya yükleme engellenirse PDF URL veya metin yapıştırma fallback yolu kullanılabilir.
- Hugging Face Spaces deploy workflow

## Canlı Durum

- Runtime bilgi tabanı: tracked `chroma_db/` snapshot
- Kaynak sayısı: 157 unique source
- Chunk/document sayısı: 3092
- UI: Streamlit
- Vector DB: ChromaDB
- LLM provider: Groq
- Deploy: GitHub Actions ile Hugging Face Space
- Son doğrulama: answer grounding 42/42, full regression 12/12, tests 342 passed / 2 skipped

Release readiness özeti için bkz. [docs/RELEASE_SUMMARY.md](docs/RELEASE_SUMMARY.md).

## Mimari

Kısa akış:

```text
Kullanıcı sorusu
  -> query_router.py
  -> source_discovery / dynamic_sources registry / RAG
  -> ChromaDB retrieval + metadata-aware rerank
  -> answer generation
  -> post-processing guardrails
  -> final cevap + kaynak paneli
  -> evaluation / regression suite
```

Detaylı mimari için bkz. [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md).

## Kurulum

Python 3.11+ önerilir.

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

Yerel ortam değişkenleri için `.env.example` dosyasını kopyalayın:

```bash
cp .env.example .env
```

Örnek değerler:

```env
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
ADMIN_PASSWORD=change_me_locally
```

`.env`, API key ve secret dosyaları repoya commit edilmez.

## Local Çalıştırma

Mevcut ChromaDB snapshot ile uygulama açılır; normal çalışma için yeni ingestion gerekmez.

```bash
streamlit run app.py
```

ChromaDB healthcheck:

```bash
python check_chroma_health.py --db-path chroma_db --json
```

Beklenen snapshot değerleri:

- `status: ok`
- `document_count: 3092`
- `unique_source_count: 157`
- `collection_readable: true`

Snapshot prosedürü için bkz. [docs/CHROMADB_SNAPSHOT_PROCEDURE.md](docs/CHROMADB_SNAPSHOT_PROCEDURE.md).

## Test ve Evaluation

Tüm testler:

```bash
python -m pytest tests/ -v
```

Tek komutlu full regression:

```bash
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
```

Answer grounding evidence-only:

```bash
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md
```

Local report dosyaları (`*.local.json`, `*.local.md`) commit edilmez.

## Dynamic Sources

Yemekhane menüsü gibi güncel/dinamik bilgiler statik ChromaDB snapshot içine gömülmez. Dining menu reader dar kapsamlı dinamik kaynak olarak çalışır. Endpoint erişilemezse veya bugüne ait güvenilir satır bulunamazsa menü uydurulmaz.

Dynamic source altyapısı `dynamic_sources/` registry altında yönetilir. Şu an kayıtlı reader: `dining_menu`.

## Quality Dashboard

Streamlit arayüzünde read-only kalite paneli bulunur. Panel local evaluation artifact özetlerini okur, shell command çalıştırmaz, API key/secret göstermez ve raw answer preview yayınlamaz.

Detay için bkz. [docs/QUALITY_DASHBOARD_RAPORU.md](docs/QUALITY_DASHBOARD_RAPORU.md).

## Hugging Face Deploy

`main` branch'e push/merge sonrası GitHub Actions workflow'u Hugging Face Space deploy'unu tetikler.

Deploy zinciri:

- `.github/workflows/deploy-hf-space.yml`
- `Dockerfile`
- `requirements.txt`
- tracked `chroma_db/` snapshot
- GitHub Actions secret: `HF_TOKEN`

Workflow, ChromaDB snapshot dosyalarını Hugging Face tarafına Git LFS ile taşır. `HF_TOKEN` veya başka secret değerleri dosyaya yazılmaz.

## Demo

Demo akışı ve temsilci sorular için bkz. [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

Örnek demo soruları:

- `AKTS nedir?`
- `ALES nedir?`
- `Ön lisans ve lisans AGNO şartı nedir?`
- `GANO ile AGNO aynı şey mi?`
- `Staj yönergesi var mı?`
- `Teknoloji Fakültesi staj kaynakları nelerdir?`
- `Bugün yemekte ne var?`
- `Galatasaray maçı ne zaman?`

## Bilinen Sınırlılıklar

- ChromaDB snapshot mevcut indekslenmiş kaynaklarla sınırlıdır.
- Yeni kaynaklar ingestion yapılmadan cevap kapsamına girmez.
- Dinamik yemekhane menüsü endpoint yapısına ve erişilebilirliğine bağlıdır.
- Live LLM QA varsayılan kapalıdır ve provider API key gerektirir.
- Tam on-prem/local LLM mimarisi bu demo kapsamında değildir.
- Sistem resmi belge yerine geçmez; kritik kararlar için resmi kaynak kontrol edilmelidir.

## Önemli Dokümanlar

- [Release Summary](docs/RELEASE_SUMMARY.md)
- [Demo Script](docs/DEMO_SCRIPT.md)
- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [ChromaDB Snapshot Procedure](docs/CHROMADB_SNAPSHOT_PROCEDURE.md)
- [System Architecture Audit](docs/SYSTEM_ARCHITECTURE_AUDIT_RAPORU.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)

## Geliştirme Kuralları

- Aktif geliştirme `dev` branch üzerinde yapılır.
- `main` kararlı deploy branch'idir.
- Runtime davranışı değişen işlerden önce regression suite, answer grounding ve full tests çalıştırılır.
- ChromaDB snapshot güncellemesi ayrı prosedürle ele alınır.
- `data/*.pdf`, `.env`, API key/secret ve local evaluation artifact dosyaları commit edilmez.
