# Final Release Checklist

Bu checklist, Selçuk RAG Asistan demo/release öncesinde repository, test, deploy ve güvenlik durumunu hızlıca doğrulamak için kullanılır.

## Repository Status

- [ ] `dev` ve `main` branch sync durumu kontrol edildi.
- [ ] `git status --short` incelendi.
- [ ] `chroma_db/chroma.sqlite3` yerelde modified görünse bile stage edilmedi.
- [ ] `release_notes_v0.1.0-demo.local.md` stage edilmedi.
- [ ] Local artifact dosyaları stage edilmedi.
- [ ] Runtime davranışı değiştiren beklenmeyen dosya yok.

## Test / Evaluation

- [ ] Syntax check passed.
- [ ] Full tests passed.
- [ ] Full regression runner passed.
- [ ] Answer grounding passed.
- [ ] Retrieval metrikleri önceki seviyeyi koruyor.
- [ ] `fallback_accuracy` 1.0.
- [ ] `critical_failure_count` 0.

Önerilen komutlar:

```bash
python -m py_compile app.py query_router.py app_chat_handlers.py source_discovery.py rag_engine.py retrieval_rerank.py retrieval_normalization.py evaluation/run_regression_suite.py evaluation/evaluate_answer_grounding.py
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md
python -m pytest tests/ -v
```

## Deployment

- [ ] GitHub Actions CI success.
- [ ] Deploy Hugging Face Space success.
- [ ] HF runtime `RUNNING`.
- [ ] HTTP status `200`.
- [ ] Traceback/Streamlit exception yok.
- [ ] ChromaDB health verified.
- [ ] Canlı snapshot 157 source / 3092 document/chunk.

## Manual Demo Smoke

- [ ] RAG smoke passed: `AKTS nedir?`, `ALES nedir?`
- [ ] Mevzuat smoke passed: `Çift anadal şartları nelerdir?`
- [ ] Source discovery smoke passed: `Staj yönergesi var mı?`
- [ ] Teknoloji Fakültesi source discovery smoke passed.
- [ ] Dynamic menu safe fallback passed.
- [ ] Out-of-scope fallback passed: `Galatasaray maçı ne zaman?`
- [ ] AGNO/GANO terminoloji belirsizliği temkinli cevaplandı.

## Security / Commit Scope

- [ ] No secrets committed.
- [ ] `.env` commit edilmedi.
- [ ] API key/token/secret içeren dosya commit edilmedi.
- [ ] `data/*.pdf` commit edilmedi.
- [ ] `data/manual_pdfs/` commit edilmedi.
- [ ] Local artifacts (`*.local.json`, `*.local.md`) commit edilmedi.
- [ ] ChromaDB snapshot accidental stage edilmedi.
- [ ] Dependency/provider/model unchanged.
- [ ] Yeni ingestion çalıştırılmadı.
- [ ] Release/tag/version bump oluşturulmadı.

## Known Limitations

- ChromaDB snapshot mevcut kaynaklarla sınırlıdır.
- Snapshot update manuel/prosedürlü yapılır.
- Dynamic dining menu endpoint'e bağlıdır.
- Live LLM QA API key gerektirir.
- Sistem resmi belge yerine geçmez.
