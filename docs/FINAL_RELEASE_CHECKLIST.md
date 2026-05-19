# Final Release Checklist

Bu checklist, Selcuk RAG Asistan release veya demo oncesinde repository, test, deploy ve guvenlik durumunu hizlica dogrulamak icin kullanilir.

## Repository Status

- `dev` ve `main` branch sync durumu kontrol edilir.
- `git status` ile working tree incelenir.
- `chroma_db/chroma.sqlite3` yerelde modified gorunurse stage edilmez; once sebebi ayrica incelenir.
- Forbidden files kontrol edilir:
  - `.env`
  - API key, token veya secret iceren dosyalar
  - `data/*.pdf`
  - `data/manual_pdfs/`
  - `chroma_db_legal_test/`
  - local evaluation artifact dosyalari

## Tests

Release oncesi asagidaki komutlar calistirilir:

```bash
python -m py_compile app.py quality_dashboard.py evaluation/compare_llm_providers.py
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md
python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json --out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md
python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json --out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
python -m pytest tests/ -v
```

Local report dosyalari commit edilmez.

## Deployment

- GitHub Actions CI sonucu kontrol edilir.
- Hugging Face deploy workflow sonucu kontrol edilir.
- HF Space runtime durumu `RUNNING` olmalidir.
- HTTP status `200` olmalidir.
- ChromaDB health kontrolu `status: ok`, `document_count: 2985`, `unique_source_count: 149` degerleriyle uyumlu olmalidir.
- Canli UI acilir ve ChromaDB/traceback hatasi olmadigi dogrulanir.

## Security

- `.env` tracked olmamalidir.
- API key veya secret degeri repoda bulunmamalidir.
- `.env.example` gercek anahtar formatina benzeyen deger icermemelidir.
- Local artifact dosyalari ignore edilmelidir.
- `data/*.pdf` ve `data/manual_pdfs/` commit edilmemelidir.
- `chroma_db_legal_test/` commit edilmemelidir.
- ChromaDB snapshot deploy workflow tarafinda Git LFS ile HF Space reposuna gonderilir ve workflow bunu kontrol eder.

## Demo

- `docs/DEMO_SCRIPT.md` hazir ve guncel olmalidir.
- `docs/RELEASE_SUMMARY.md` mevcut dogrulanmis durumu yansitmalidir.
- `docs/ARCHITECTURE_OVERVIEW.md` runtime, evaluation ve deploy katmanlarini aciklamalidir.
- Demo sorulari hem kaynakli cevap hem safe fallback davranisini temsil etmelidir.

## Known Limitations

- Quality dashboard ilk surumde read-only calisir.
- Snapshot guncellemesi manuel ve prosedurlu yapilir.
- Live LLM evaluation API key gerektirir.
- Provider comparison production provider degistirmez.
- Article hit metrigi halen gelistirmeye aciktir.
