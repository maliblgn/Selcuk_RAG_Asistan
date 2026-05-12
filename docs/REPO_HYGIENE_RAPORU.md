# Repo Hygiene Raporu

## Neden temizlik yapildi?

Repo calisan RAG uygulamasi, ChromaDB snapshot'i, testler ve deploy dosyalari ile kararlı hale geldikten sonra kok dizinde cok sayida ara rapor, preview JSON'u, baseline ciktisi ve eski faz dokumani birikmisti. Bu dosyalar runtime icin gerekli degildi ve hangi dosyanin uygulama icin zorunlu oldugunu belirsizlestiriyordu.

Bu temizlik ile hedeflenen:

- `main` kararlı, `dev` aktif gelistirme dali olacak sekilde duzen kurmak.
- Runtime dosyalarini artifact ciktisindan ayirmak.
- README'yi mevcut HF Spaces Docker ve guardrail mimarisine gore guncellemek.
- Generated rapor/preview dosyalarinin tekrar repoya girmesini engellemek.

## Repo envanteri siniflandirmasi

### A) Runtime icin gerekli dosyalar

- `app.py`
- `rag_engine.py`
- `retrieval_rerank.py`
- `source_inventory.py`
- `source_access_policy.py`
- `check_chroma_health.py`
- `content_processor.py`
- `web_scraper.py`
- `web_crawler.py`
- `crawler_config.py`
- `crawler_db.py`
- `data_ingestion.py`
- `legal_chunker.py`
- `legal_ingestion.py`
- `flash_channel.py`
- `source_manifest.json`
- `curated_web_sources.txt`
- `chroma_db/`
- `requirements.txt`
- `.streamlit/config.toml`

### B) Deployment dosyalari

- `Dockerfile`
- `.dockerignore`
- `.streamlit/config.toml`
- `requirements.txt`
- `README.md`
- `.env.example`
- `docs/HF_SPACES_DEPLOY_RAPORU.md`

### C) Test dosyalari

- `tests/`
- `evaluation/golden_questions.json`
- `evaluation/*.py`

### D) Gelistirme/analiz scriptleri

- `analysis_*.py`
- `legal_chunk_preview.py`
- `index_report.py`
- `discovery_report.py`
- `db_maintenance.py`
- `scripts/`

### E) Uretilmis artifact / rapor / preview dosyalari

Asagidaki kok dizin JSON/TXT/CSV rapor ve preview dosyalari runtime icin gerekli olmadigi icin kaldirildi:

- `baseline_discovery_report.json`
- `baseline_index_report.json`
- `central_pdf_listing_sources.txt`
- `chroma_article_analysis.json`
- `chroma_article_analysis_full_authorized.json`
- `chroma_health_report.json`
- `chroma_health_report_full_authorized.json`
- `critical_access_preflight.json`
- `critical_pdf_inventory.json`
- `evaluation_questions.json`
- `full_ingestion_failures_authorized.json`
- `full_pdf_inventory_authorized.json`
- `full_pdf_urls_authorized.txt`
- `index_report_full_authorized.json`
- `legal_chunk_preview.json`
- `legal_chunk_preview_after_quality.json`
- `legal_chunker_demo.json`
- `legal_test_index_report.json`
- `manual_download_todo.csv`
- `rag_preview_*.json`
- `retrieval_*_report.json`

### F) Eski faz raporlari

Asagidaki eski ara raporlar kaldirildi:

- `docs/AKTS_SOURCE_BINDING_HOTFIX_RAPORU.md`
- `docs/BASELINE_DURUM_RAPORU.md`
- `docs/FAZ*.md`
- `docs/FULL_AUTHORIZED_CHROMA_MADDE_ANALIZ_RAPORU.md`
- `docs/FULL_AUTHORIZED_INGESTION_RAPORU.md`
- `docs/GENERAL_RAG_GUARDRAILS_RAPORU.md`
- `docs/GROQ_TOKEN_BUDGET_HOTFIX_RAPORU.md`
- `docs/HF_SPACE_README_TEMPLATE.md`
- `docs/LIVE_CHROMA_HATA_TESHIS_RAPORU.md`
- `PROJE_BAGLAM_DOSYASI.md`
- `PROJE_INCELEME_RAPORU.md`
- `algoritma_ozet.md`
- `tasarim_raporu.md`

## Data dosyalari karari

`data/*.pdf` dosyalari runtime icin gerekli degil; mevcut uygulama tracked `chroma_db/` snapshot ile calisir. Bu nedenle repodan kaldirildi ve `data/` `.gitignore` kapsaminda tutuldu. Yeni ingestion istenirse veri kaynaklari yeniden lokal olarak indirilebilir, fakat PDF'ler commit edilmez.

## Korunan dosyalar

- `chroma_db/`: 149 kaynak / 2985 chunk runtime snapshot.
- `source_manifest.json`: Resmi kaynak manifesti.
- `curated_web_sources.txt`: Kontrollu gelistirme/ingestion yardimci listesi.
- `evaluation/golden_questions.json`: Retrieval regression seti.
- `docs/HF_SPACES_DEPLOY_RAPORU.md`: HF Spaces deploy notlari.
- `CRAWLING_POLICY.md`: Crawler guvenlik politikasi.

## ChromaDB neden korundu?

HF Spaces runtime mevcut ChromaDB snapshot ile ayaga kalkar. Yeni ingestion bu gorevin kapsami disindadir. Bu nedenle `chroma_db/` silinmedi, yeniden uretilmedi ve commit kapsaminda degistirilmedi.

## README guncelleme ozeti

`README.md` bastan sade ve guncel olarak yazildi:

- HF Spaces Docker ana deploy ortami olarak belirtildi.
- Streamlit Community Cloud'un memory limitleri nedeniyle ana hedef olmadigi aciklandi.
- 149 kaynak / 2985 chunk snapshot durumu eklendi.
- Metadata-aware rerank, source binding ve general guardrails ozetlendi.
- Kurulum, local calistirma, test ve guvenlik kurallari guncellendi.
- `main` / `dev` gelistirme modeli belgelendi.

## Yeni gelistirme akisi

- `main`: Kararli surum.
- `dev`: Aktif gelistirme dali.
- Yeni isler `dev` uzerinde yapilir.
- Testler gecmeden `main`e alinmaz.
- HF deploy guncellemesi ayrica yapilir.

Detaylar `docs/DEVELOPMENT_WORKFLOW.md` dosyasinda.

## Eklenen dokumanlar

- `docs/PROJECT_STRUCTURE.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/REPO_HYGIENE_RAPORU.md`

## Test sonucu

Komut:

```bash
python -m pytest tests/ -v
```

Sonuc:

```text
188 passed, 2 skipped
```

## Healthcheck sonucu

Komut:

```bash
python check_chroma_health.py --db-path chroma_db --json --out chroma_health_cleanup_check.local.json
```

Sonuc ozeti:

- `ok`: true
- `status`: ok
- `document_count`: 2985
- `unique_source_count`: 149
- `collection_readable`: true

`chroma_health_cleanup_check.local.json` lokal cikti olarak birakildi ve commit edilmedi.

## Degistirilmeyenler

- `chroma_db/` icerigi bilincli olarak degistirilmedi.
- Yeni ingestion calistirilmadi.
- HF orphan branch veya deploy islemi yapilmadi.
- RAG davranisini degistiren kod refactor'u yapilmadi.
- `.env`, secret veya API key commit edilmedi.
- `chroma_db_legal_test/` commit edilmedi.
