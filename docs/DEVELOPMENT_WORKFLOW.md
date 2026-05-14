# Development Workflow

## Branch modeli

- `main`: Kararli surum dalidir. Calisan, testlerden gecmis ve deploy edilebilir durumdaki kod burada tutulur.
- `dev`: Aktif gelistirme dalidir. Yeni isler varsayilan olarak burada yapilir.

Bu duzende yeni feature branch acmak varsayilan akisa dahil degildir. Buyuk ve riskli degisiklikler icin once kapsam netlestirilir.

## Calisma akisi

1. `dev` dalini guncelle.
2. Degisikligi `dev` uzerinde yap.
3. Testleri calistir.
4. Yasakli dosyalarin stage edilmedigini kontrol et.
5. `origin/dev` dalina pushla.
6. `main`e alma karari ayrica verilir.

## Test komutu

```bash
python -m pytest tests/ -v
```

Testler gecmeden `main`e alinmaz.

## Dependency degisikligi

`requirements.txt` icindeki kritik runtime paketleri pinlenmistir. Paket surumu degistirilecekse en az su kontroller calistirilir:

```bash
USE_TF=0 TRANSFORMERS_NO_TF=1 python -c "import streamlit, chromadb, sentence_transformers, groq; print('runtime imports ok')"
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
python -m pytest tests/ -v
```

Dependency degisikligi `main`e alindiktan sonra HF deploy workflow sonucu da kontrol edilir. Local smoke artifact'leri commit edilmez.

## General Smoke Evaluation

Genel RAG kapsamini LLM cagrisi yapmadan kontrol etmek icin:

```bash
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
```

`general_smoke_report.local.json` ve `general_smoke_summary.local.md` local artifact'tir; commit edilmez.

## Retrieval Evaluation

Golden question setiyle retrieval, relevance filtering ve source mapping metriklerini LLM cagrisi yapmadan kontrol etmek icin:

```bash
python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json --out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md
```

`retrieval_evaluation_report.local.json` ve `retrieval_evaluation_summary.local.md` local artifact'tir; commit edilmez. Runtime davranisi degistiren islerden once general smoke, retrieval evaluation ve pytest birlikte calistirilir.

## Retrieval Triage

Retrieval evaluation raporundan failure analizi cikarmak icin:

```bash
python evaluation/triage_retrieval_failures.py --report retrieval_evaluation_report.local.json --golden evaluation/golden_questions.json --out retrieval_triage_report.local.json --markdown-out retrieval_triage_summary.local.md
```

`retrieval_triage_report.local.json` ve `retrieval_triage_summary.local.md` local artifact'tir; commit edilmez. Runtime duzeltmesi yapilmadan once triage raporu incelenir ve hard-coded soru patch'i yerine genel iyilestirme alani belirlenir.

## Retrieval Normalization / Alias

Query vocabulary veya metadata alias degisikliklerinden sonra su kontroller birlikte calistirilir:

```bash
python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json --out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md
python evaluation/triage_retrieval_failures.py --report retrieval_evaluation_report.local.json --golden evaluation/golden_questions.json --out retrieval_triage_report.local.json --markdown-out retrieval_triage_summary.local.md
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
python -m pytest tests/ -v
```

Aliaslar soru ID'sine gore degil, genel terim ve belge ailesi duzeyinde tutulur. Fallback accuracy dususu gorulurse degisiklik geri alinir veya daha dar ve guvenli hale getirilir.

## Article Metadata Evaluation

Madde no/baslik eslesmesi degisikliklerinden sonra article metadata audit de calistirilir:

```bash
python evaluation/audit_article_metadata.py --golden evaluation/golden_questions.json --out article_metadata_audit.local.json --markdown-out article_metadata_audit.local.md
```

`article_metadata_audit.local.json` ve `article_metadata_audit.local.md` local artifact'tir; commit edilmez. Article matching degisikliklerinden sonra retrieval evaluation, triage, article audit, general smoke ve pytest birlikte calistirilir.

## Yasakli dosyalar

Asagidaki dosyalar commit edilmez:

- `.env`
- API key, token veya secret iceren herhangi bir dosya
- `data/*.pdf`
- `data/manual_pdfs/`
- `chroma_db_legal_test/`
- `custom_urls.txt`
- `selcuk_links.txt`
- lokal healthcheck, preview ve generated report dosyalari

## ChromaDB kurali

`chroma_db/` bu projede runtime snapshot olarak tracked kalir. Silinmez, yeniden uretilmez ve bu tip dokumantasyon/temizlik islerinde degistirilmez.

Snapshot guncelleme ayri bir gorev olarak ele alinir. Guncelleme yapilmadan once `docs/CHROMADB_SNAPSHOT_PROCEDURE.md` dokumani takip edilir.

## Otomatik Hugging Face Deploy

- Gelistirme `dev` branch uzerinde yapilir.
- Degisiklikler test edildikten sonra `dev` -> `main` alinir.
- `main` branch'e push/merge oldugunda `.github/workflows/deploy-hf-space.yml` otomatik calisir.
- Workflow Hugging Face Space reposuna temiz deploy commit'i gonderir.
- Buyuk ChromaDB dosyalari workflow icinde Git LFS ile gonderilir.
- `.gitignore` ChromaDB snapshot'ini normal `git add -A` akisinda dislayabildigi icin deploy workflow'u yalniz `chroma_db/` klasorunu bilincli olarak `git add -f chroma_db` ile ekler.
- Workflow `chroma_db/chroma.sqlite3` dosyasinin deploy klasorunde bulundugunu, git index'e eklendigini ve Git LFS tarafindan izlendigini commit oncesi dogrular.
- Gerekli GitHub Actions secret:
  - `HF_TOKEN`
- `HF_TOKEN` Hugging Face write token olmalidir.
- Token repoya veya dosyaya yazilmaz.
- Workflow `workflow_dispatch` ile manuel de calistirilabilir.

## Ingestion kurali

Yeni ingestion sadece acik gorev olarak istenirse calistirilir. Normal uygulama mevcut ChromaDB snapshot ile calisir.
