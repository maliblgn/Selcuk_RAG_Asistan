# Project Structure

Bu dosya repodaki ana dosya ve klasorlerin ne icin tutuldugunu ozetler.

## Runtime dosyalari

- `app.py`: Streamlit UI, sohbet akisi, kaynak paneli, fallback gosterimi.
- `rag_engine.py`: RAG motoru, retrieval, promptlar, cevap post-processing ve guardrails.
- `retrieval_rerank.py`: Metadata-aware rerank ve legal query sinyalleri.
- `source_inventory.py`: ChromaDB icindeki kaynak envanteri yardimcilari.
- `source_access_policy.py`: Kaynak erisim politikasi ve izin sinyalleri.
- `check_chroma_health.py`: ChromaDB snapshot saglik kontrolu.
- `flash_channel.py`: Opsiyonel FlashRank entegrasyon kanali.
- `content_processor.py`, `web_scraper.py`, `web_crawler.py`: Ingestion ve crawler is akisi icin yardimci moduller.

## Veri ve kaynaklar

- `chroma_db/`: Runtime icin gerekli tracked ChromaDB snapshot. Silinmez ve yeniden uretilmez.
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
- `evaluation/`: Retrieval degerlendirme scriptleri ve `golden_questions.json`.
- `analysis_*.py`, `legal_chunk_preview.py`, `index_report.py`, `discovery_report.py`: Gelistirme/analiz scriptleri. Urettikleri JSON raporlar repo disinda tutulur.

## Dokumantasyon

- `README.md`: Guncel proje ozeti, kurulum, deploy ve gelistirme akisi.
- `docs/HF_SPACES_DEPLOY_RAPORU.md`: HF Spaces Docker deploy notlari.
- `docs/DEVELOPMENT_WORKFLOW.md`: Branch ve test calisma duzeni.
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
