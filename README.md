# Selcuk RAG Asistan

Selcuk RAG Asistan, Selcuk Universitesi resmi yonetmelik, yonerge ve PDF dokumanlari uzerinde calisan kaynakli bir RAG uygulamasidir. Sistem, uygun kaynak buldugunda cevabi inline citation ile verir; corpus disi veya guncel operasyonel bilgi isteyen sorularda guvenli fallback davranisini hedefler.

Ana deploy hedefi Hugging Face Spaces Docker ortamidir. Streamlit arayuzu, ChromaDB runtime snapshot'i, metadata-aware retrieval/rerank, post-processing guardrail'leri ve read-only kalite paneli birlikte calisir.

## Canli Durum

- Runtime bilgi tabani: tracked `chroma_db/` snapshot
- Kaynak sayisi: 149 unique source
- Chunk/document sayisi: 2985
- UI: Streamlit
- Vector DB: ChromaDB
- LLM provider: Groq
- Deploy: GitHub Actions ile Hugging Face Space
- Kalite gorunurlugu: retrieval evaluation, general smoke, answer quality, provider comparison ve read-only quality dashboard

Release ozeti icin bkz. [docs/RELEASE_SUMMARY.md](docs/RELEASE_SUMMARY.md).

## Mimari

Kisa akis:

```text
Kullanici sorusu
  -> query normalization / intent guards
  -> ChromaDB retrieval
  -> metadata-aware rerank
  -> relevance filtering
  -> Groq LLM answer
  -> post-processing guardrails
  -> final cevap + kaynak paneli
```

Detayli mimari icin bkz. [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md).

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

Yerel ortam degiskenleri icin `.env.example` dosyasini kopyalayin:

```bash
cp .env.example .env
```

Ornek degerler:

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
ADMIN_PASSWORD=change_me_locally
```

`.env`, API key ve secret dosyalari repoya commit edilmez.

## Local Calistirma

Mevcut ChromaDB snapshot ile uygulama acilir; normal calisma icin yeni ingestion gerekmez.

```bash
streamlit run app.py
```

ChromaDB healthcheck:

```bash
python check_chroma_health.py --db-path chroma_db --json
```

Beklenen snapshot degerleri:

- `status: ok`
- `document_count: 2985`
- `unique_source_count: 149`
- `collection_readable: true`

Snapshot proseduru icin bkz. [docs/CHROMADB_SNAPSHOT_PROCEDURE.md](docs/CHROMADB_SNAPSHOT_PROCEDURE.md).

## Evaluation Komutlari

Retrieval evaluation:

```bash
python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json --out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md
```

General smoke:

```bash
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
```

Answer quality dry-run:

```bash
python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json --out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md
```

Provider comparison dry-run:

```bash
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md
```

Testler:

```bash
python -m pytest tests/ -v
```

`*.local.json` ve `*.local.md` evaluation artifact dosyalari commit edilmez.

## Quality Dashboard

Streamlit arayuzunde read-only kalite paneli bulunur. Panel local evaluation artifact ozetlerini okur, shell command calistirmaz, API key/secret gostermez ve raw answer preview yayinlamaz.

Detay icin bkz. [docs/QUALITY_DASHBOARD_RAPORU.md](docs/QUALITY_DASHBOARD_RAPORU.md).

## Hugging Face Deploy

`main` branch'e push/merge sonrasi GitHub Actions workflow'u Hugging Face Space deploy'unu tetikler.

Deploy zinciri:

- `.github/workflows/deploy-hf-space.yml`
- `Dockerfile`
- `requirements.txt`
- tracked `chroma_db/` snapshot
- GitHub Actions secret: `HF_TOKEN`

Workflow, ChromaDB snapshot dosyalarini Hugging Face tarafina Git LFS ile tasir. `HF_TOKEN` veya baska secret degerleri dosyaya yazilmaz.

## Demo

Demo akisi ve temsilci sorular icin bkz. [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

Ornek demo sorulari:

- `AKTS nedir?`
- `Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?`
- `Selcuk Universitesi'nde doktora yeterlik sinavlari ile ilgili esaslar nelerdir?`
- `Selcuk Universitesi kutuphanesinde hangi saatlerde hizmet sunulur?`
- `Selcuk Universitesi yemekhane hizmetleri hangi saatlerde sunulur?`
- `Selcuk Universitesi'nde ders kredisi nasil hesaplanir?`
- `Selcuk Universitesi ogrencilere ucretsiz laptop veriyor mu?`

## Onemli Dokumanlar

- [Release Summary](docs/RELEASE_SUMMARY.md)
- [Demo Script](docs/DEMO_SCRIPT.md)
- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [ChromaDB Snapshot Procedure](docs/CHROMADB_SNAPSHOT_PROCEDURE.md)
- [Quality Dashboard Report](docs/QUALITY_DASHBOARD_RAPORU.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)

## Gelistirme Kurallari

- Aktif gelistirme `dev` branch uzerinde yapilir.
- `main` kararli release/deploy branch'idir.
- Runtime davranisi degisen islerden once retrieval evaluation, general smoke, answer quality ve test zinciri calistirilir.
- ChromaDB snapshot guncellemesi ayri prosedurle ele alinir.
- `data/*.pdf`, `.env`, API key/secret ve local evaluation artifact dosyalari commit edilmez.
