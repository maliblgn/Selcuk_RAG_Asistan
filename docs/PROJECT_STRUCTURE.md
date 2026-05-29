# Project Structure

Bu dosya repodaki ana dosya ve klasorlerin ne icin tutuldugunu ozetler.

## Runtime dosyalari

- `app.py`: Streamlit UI, sohbet akisi, kaynak paneli, fallback gosterimi.
- `app_chat_handlers.py`: Chat cevap akisi icin source discovery, dynamic menu ve assistant message helperlari.
- `query_router.py`: Source discovery, dynamic dining menu ve RAG modlari arasinda routing karari.
- `rag_engine.py`: RAG motoru, retrieval, promptlar, cevap post-processing ve guardrails.
- `retrieval_rerank.py`: Metadata-aware rerank ve legal query sinyalleri.
- `retrieval_normalization.py`: Turkce/ASCII-lite normalization, alias ve madde eslesmesi yardimcilari.
- `source_discovery.py`: Kaynak listeleme niyeti ve indekslenmis kaynak kesfi.
- `dynamic_menu_reader.py`: Yemekhane menusu dynamic reader ve parser/diagnostic yardimcilari.
- `dynamic_sources/`: Dynamic source interface, registry, health ve dining menu wrapper katmani.
- `chroma_runtime.py`: Local ChromaDB runtime copy stratejisi.
- `source_inventory.py`: ChromaDB icindeki kaynak envanteri yardimcilari.
- `source_access_policy.py`: Kaynak erisim politikasi ve izin sinyalleri.
- `check_chroma_health.py`: ChromaDB snapshot saglik kontrolu.
- `flash_channel.py`: Opsiyonel FlashRank entegrasyon kanali.
- `content_processor.py`, `web_scraper.py`, `web_crawler.py`: Ingestion ve crawler is akisi icin yardimci moduller.

## Veri ve kaynaklar

- `chroma_db/`: Runtime icin gerekli tracked ChromaDB snapshot. Silinmez ve yeniden uretilmez. Guncelleme proseduru icin `docs/CHROMADB_SNAPSHOT_PROCEDURE.md` takip edilir.
- `source_manifest.json`: Resmi kaynak seedleri ve beklenen dokumanlar.
- `curated_web_sources.txt`: Kontrollu/manual ingestion denemeleri icin kucuk kaynak listesi. Normal runtime icin gerekli degildir, fakat gelistirme yardimcisi olarak tutulur.

## Deployment

- `Dockerfile`: Hugging Face Spaces Docker build tanimi.
- `.dockerignore`: Deploy build disinda kalacak lokal dosyalar.
- `.streamlit/config.toml`: Streamlit runtime ayarlari.
- `requirements.txt`: Python bagimliliklari.
- `.env.example`: Ortam degiskeni sablonu. Gercek `.env` commit edilmez.

## Test ve degerlendirme

- `tests/`: Unit ve regression testleri.
- `evaluation/`: Retrieval, answer grounding, dynamic source, source discovery ve regression suite scriptleri.
- `evaluation/run_regression_suite.py`: `fast`, `full`, `dynamic-source`, `snapshot-update` profilleri.
- `evaluation/evaluate_answer_grounding.py`: Evidence-only ve opsiyonel live LLM grounding kontrolu.
- `analysis_*.py`, `legal_chunk_preview.py`, `index_report.py`, `discovery_report.py`: Gelistirme/analiz scriptleri. Urettikleri JSON raporlar repo disinda tutulur.

## Dokumantasyon

- `README.md`: Guncel proje ozeti, kurulum, deploy ve gelistirme akisi.
- `docs/HF_SPACES_DEPLOY_RAPORU.md`: HF Spaces Docker deploy notlari.
- `docs/CHROMADB_SNAPSHOT_PROCEDURE.md`: ChromaDB snapshot uretim, dogrulama, guncelleme ve rollback proseduru.
- `docs/DEVELOPMENT_WORKFLOW.md`: Branch ve test calisma duzeni.
- `docs/SYSTEM_ARCHITECTURE_AUDIT_RAPORU.md`: Faz 9 mimari/refactor ve kalite audit notlari.
- `docs/DEMO_SCRIPT.md`: Canli demo soru akisi ve beklenen davranislar.
- `docs/RELEASE_SUMMARY.md`: Demo/release-readiness ozeti.
- `docs/REPO_HYGIENE_RAPORU.md`: Bu temizlik fazinin raporu.

## Scripts

- `scripts/`: Tek seferlik veya destekleyici gelistirme scriptleri.

## Commit edilmemesi gerekenler

- `.env`
- `data/`
- `data/manual_pdfs/`
- `chroma_db_legal_test/`
- `rag_preview_*.json`
- `*_report*.json`
- lokal healthcheck ciktisi
