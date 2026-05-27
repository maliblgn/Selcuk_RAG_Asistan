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

## Source Inventory Alias Audit

Metadata title mismatch veya golden expectation degisikligi yapilmadan once source inventory alias audit calistirilir:

```bash
python evaluation/audit_source_inventory_aliases.py --golden evaluation/golden_questions.json --out source_inventory_alias_audit.local.json --markdown-out source_inventory_alias_audit.local.md
```

`source_inventory_alias_audit.local.json` ve `source_inventory_alias_audit.local.md` local artifact'tir; commit edilmez. Alias degisiklikleri soru ID'sine gore degil, belge ve terim ailesi duzeyinde yapilir.

## Golden Expectation Review

Golden expectation degisikligi yapilmadan once source inventory alias audit ve article metadata audit birlikte calistirilir. Golden duzeltmeleri runtime patch yerine yalnizca degerlendirme beklentisini gercek kaynak metadata'siyla hizalamak icin yapilir.

`expected_terms` veya `expected_behavior` keyfi olarak zayiflatilmaz. Belge/madde beklentisi degisecekse audit ciktisi, mevcut source metadata ve not alani birlikte guncellenir.

## Answer Quality Evaluation

Sinirli LLM cevap kalitesi kontrolu icin once CI-safe dry-run calistirilir:

```bash
python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json --out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md
```

Yerel ve manuel live LLM denemesi icin:

```bash
python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json --out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md --live-llm --limit 10
```

Live LLM icin `GROQ_API_KEY` gerekir. CI'da gercek LLM cagrisi yapilmaz. `answer_quality_report.local.json` ve `answer_quality_summary.local.md` local artifact'tir; commit edilmez.

## Answer Quality Leak Triage

Answer quality live run sonucunda raw model cevabi ve production final cevabi ayri degerlendirilir. `source_block_leak_count` ve `url_leak_count` final kullanici cevabini temsil eder.

Raw model ciktisinda kaynak/URL blogu olmasi tek basina production hatasi sayilmaz; post-processing sonrasi final cevapta leak kalirsa guardrail fix gerekir. Inline citation bicimindeki `[1]`, `[2]` atiflari leak sayilmaz.

## Provider / Model Comparison

Provider/model adaylarini answer quality soru seti uzerinden karsilastirmak icin dry-run:

```bash
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md
```

Yerel live Groq karsilastirmasi:

```bash
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md --live-llm --provider-id groq_llama_3_1_8b_instant --limit 10
```

CI'da gercek LLM cagrisi yapilmaz. API key/secret rapora veya dosyaya yazilmaz. Bu degerlendirme production provider'i degistirmez.

## Quality Dashboard

Streamlit yonetici alaninda local evaluation artifact ozetleri goruntulenebilir. Panel read-only calisir; shell command calistirmaz.

Komutlar terminalde calistirilir, panel local artifact varsa okur:

- `retrieval_evaluation_report.local.json`
- `general_smoke_report.local.json`
- `answer_quality_report.local.json`
- `provider_comparison_report.local.json`

Local artifact dosyalari commit edilmez. API key/secret UI'da gosterilmez.

## Release / Demo Documentation

Release summary, demo script ve architecture overview dokumanlari major fazlardan sonra guncel tutulur.

Demo sorulari kaynakli cevap, guvenli fallback, kaynak paneli ve post-processing guardrail davranisini temsil etmelidir. Release dokumanlarinda yalniz mevcut dogrulanmis durum yazilir; abartili veya kanitsiz iddia eklenmez.

## Source Discovery Mode

`X ile ilgili kaynaklar nelerdir?` gibi kaynak listeleme sorulari normal answer generation'dan ayrilir. Source discovery modu ChromaDB/source inventory uzerinden ilgili kaynaklari listeler ve belirgin kaynak kesfi niyeti yoksa devreye girmez.

Bu mod LLM cevabi uretmek yerine kaynak kesfi yapar; normal tanim, hesaplama veya mevzuat cevabi sorulari mevcut RAG akisinda kalir.

## Web Source Expansion Audit

Yeni web kaynak adaylari ingestion oncesinde manifest olarak denetlenir:

```bash
python evaluation/audit_web_source_candidates.py --candidates evaluation/web_source_candidates.json --out web_source_candidates_audit.local.json --markdown-out web_source_candidates_audit.local.md
```

Bu komut yeni kaynak adaylarini dogrular, ingestion yapmaz. Dynamic kaynaklar statik ChromaDB snapshot'tan ayri degerlendirilir. `web_source_candidates_audit.local.json` ve `web_source_candidates_audit.local.md` local artifact'tir; commit edilmez.

## Technology Faculty Source Plan

Teknoloji Fakultesi kaynaklari snapshot update oncesinde ayrik manifest olarak dogrulanir:

```bash
python evaluation/audit_technology_faculty_sources.py --sources evaluation/technology_faculty_sources.json --out technology_faculty_sources_audit.local.json --markdown-out technology_faculty_sources_audit.local.md
```

Bu faz ingestion yapmaz. Teknoloji Fakultesi kaynaklari once manifest, kapsam ve priority olarak denetlenir. Snapshot update ayri gorevdir ve `docs/CHROMADB_SNAPSHOT_PROCEDURE.md` takip edilir. `technology_faculty_sources_audit.local.json` ve `technology_faculty_sources_audit.local.md` local artifact'tir; commit edilmez.

## Technology Faculty Snapshot Update

Teknoloji Fakultesi kaynaklari snapshot'a alinmadan once preflight, sonra ingestion, sonra source discovery ve tam kalite zinciri calistirilir:

```bash
python tools/preflight_technology_faculty_sources.py --sources evaluation/technology_faculty_sources.json --out technology_faculty_preflight.local.json --markdown-out technology_faculty_preflight.local.md
python tools/ingest_technology_faculty_sources.py --sources evaluation/technology_faculty_sources.json --chroma-dir chroma_db --report technology_faculty_ingestion.local.json --markdown-out technology_faculty_ingestion.local.md
python evaluation/evaluate_source_discovery.py --questions evaluation/source_discovery_smoke_questions.json --out source_discovery_report.local.json --markdown-out source_discovery_summary.local.md
```

Bu islem ChromaDB snapshot degistirir. Local artifactler ve `data/*.pdf` commit edilmez. Snapshot update sonrasi retrieval evaluation, general smoke, answer quality dry-run, provider comparison dry-run ve pytest birlikte calistirilir. HF deploy ayrica dogrulanir.

## Snapshot Update Triage

ChromaDB snapshot update sonrasi article hit veya critical failure degisirse, main'e almadan once retrieval triage, article metadata audit ve source inventory alias audit calistirilir. Bu triage runtime patch yerine once etki alanini ayirir: yeni kaynak gurultusu, mevcut rerank davranisi, metadata sorunu veya golden expectation ihtiyaci.

## Dynamic Dining Menu Reader

Yemekhane menusu statik ChromaDB snapshot'a eklenmez. Menu guncel/dinamik kaynak olarak okunur; endpoint erisilemezse menu uydurulmaz. Dynamic reader testleri ve smoke evaluation calistirilir. ChromaDB snapshot bu fazda degistirilmez.

```bash
python evaluation/evaluate_dynamic_menu.py --questions evaluation/dynamic_menu_smoke_questions.json --out dynamic_menu_report.local.json --markdown-out dynamic_menu_summary.local.md
```

## Dynamic Menu Parser Debug

```bash
python tools/debug_dynamic_menu_source.py --out dynamic_menu_debug.local.json --markdown-out dynamic_menu_debug.local.md
```

Bu komut endpoint health ve parser ipuclarini local artifact olarak uretir. Ham HTML, cache ve local debug ciktilari commit edilmez.

## Architecture Audit / Refactor Planning

Buyuk refactor oncesi architecture audit raporu cikarilir. Bu rapor runtime davranisi degistirmez; once sorumluluklar, routing, ChromaDB local dev akisi ve evaluation komutlari analiz edilir.

Refactor kucuk fazlara bolunur. Calisan RAG, source discovery, dynamic source ve deploy akislari tek seferde yeniden yazilmaz.

## Query Router

Yeni cevap modu eklenecekse once `query_router.py` routing sirasi kontrol edilir. Source discovery, dynamic source ve RAG modlari route descriptor ile ayrilir.

Routing degisikliklerinden sonra query router testleri, source discovery evaluation, dynamic menu evaluation ve retrieval evaluation calistirilir.

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
