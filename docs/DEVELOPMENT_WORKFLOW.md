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

## One-shot Development and Deploy Flow

Dusuk/orta riskli gelistirmelerde tek prompt icinde su akis uygulanabilir: dev'de gelistirme, test/evaluation, `origin/dev` push, main merge, `origin/main` push, CI ve HF deploy dogrulama.

Bu akis testleri atlamaz. ChromaDB snapshot update, yeni ingestion, dependency/provider degisikligi gibi yuksek riskli islerde ek guvenlik kontrolleri uygulanir.

## App Orchestration Cleanup

`app.py` UI dosyasi olarak kalir. Chat cevap uretim bloklari kucuk helperlara ayrilabilir; helperlar Streamlit layout cizmemeli ve cevap/source/session mesaji hazirlama gibi dar sorumluluklar tasimalidir.

Bu tur refactorlarda query router testleri, source discovery evaluation, dynamic menu evaluation, retrieval evaluation ve full pytest calistirilir. UI davranisi ve runtime cevap modlari korunmadan main'e alinmaz.

## Regression Suite Runner

Sik kullanilan test/evaluation zinciri tek komutla calistirilabilir:

```bash
python evaluation/run_regression_suite.py --profile fast
python evaluation/run_regression_suite.py --profile full
python evaluation/run_regression_suite.py --profile dynamic-source
python evaluation/run_regression_suite.py --profile snapshot-update
```

Profil ozeti:

- `fast`: syntax, query router/dynamic menu/app chat handler testleri, dynamic menu dry-run, source discovery evaluation ve full pytest.
- `full`: `fast` kapsamindaki kritik kontroller ile retrieval evaluation, general smoke, answer quality dry-run ve provider comparison dry-run.
- `dynamic-source`: dynamic dining menu ve source discovery odakli smoke kontrolleri; live fetch varsayilan olarak kapali kalir.
- `snapshot-update`: snapshot update sonrasi kalite zinciri; ingestion calistirmaz ve ChromaDB snapshot'i degistirmez.

Local runner raporlari (`regression_suite_*.local.json`, `regression_suite_*.local.md`) commit edilmez.

## Dynamic Source Interface

Dynamic kaynaklar `dynamic_sources/` altindaki ortak interface ve registry ile yonetilir. Ilk kayitli kaynak dining menu reader'dir; mevcut `dynamic_menu_reader.py` fonksiyonlari geriye uyumlu olarak calismaya devam eder.

Yeni dynamic source eklenmeden once `query_router.py` oncelik sirasi kontrol edilir. Source discovery, dynamic source'lardan once calismaya devam etmelidir.

Dynamic source degisikliklerinde su komutlar calistirilir:

```bash
python evaluation/run_regression_suite.py --profile dynamic-source --use-local-chroma-copy
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
```

## Article-level Retrieval Stabilization

Article matching ve rerank degisikliklerinde once production retrieval metrikleri ve triage zinciri calistirilir:

```bash
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
python evaluation/triage_retrieval_failures.py --report retrieval_evaluation_report.local.json --golden evaluation/golden_questions.json --out retrieval_triage_report.local.json --markdown-out retrieval_triage_summary.local.md
python evaluation/audit_article_metadata.py --golden evaluation/golden_questions.json --out article_metadata_audit.local.json --markdown-out article_metadata_audit.local.md
python evaluation/audit_source_inventory_aliases.py --golden evaluation/golden_questions.json --out source_inventory_alias_audit.local.json --markdown-out source_inventory_alias_audit.local.md
```

Hard-coded question ID patch yapilmaz. `expected_terms` veya `expected_behavior` keyfi olarak zayiflatilmaz; golden expectation degisikligi yalniz audit sonucu mevcut source/metadata ile uyumsuzluk acikca gosterirse ayri gerekceyle yapilir.

## Answer Grounding Evaluation

Final cevabin dogru evidence'a dayanip dayanmadigini olcmek icin answer grounding evaluator kullanilir:

```bash
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md
```

Manuel live QA denemesi gerekiyorsa sinirli calistirilir:

```bash
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md --live-llm --limit 10
```

- Varsayilan mod CI-safe evidence-only calisir ve live LLM cagirmaz.
- Live LLM varsayilan kapali kalir; `GROQ_API_KEY` yoksa live kontrol guvenli sekilde skipped olur.
- `answer_grounding_*.local.*` ciktilari commit edilmez.
- Bu evaluation dogru route, dogru kaynak, dogru belge/madde, expected term, forbidden term ve fallback davranisini olcer.
- Yeni runtime patch yapmadan once grounding failure'lari incelenir.

## Manual Live QA Cleanup

Canli manuel testlerde gorulen cevap ve sunum sorunlari runtime patch yapilmadan once siniflandirilir:

- source discovery presentation
- terminology ambiguity
- duplicate answer sentences
- no-evidence fallback
- retrieval miss

Bu tur duzeltmelerden sonra su kontroller calistirilir:

```bash
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
python -m pytest tests/ -v
```

Kaynak yoksa cevap uydurulmaz. Terminoloji belirsizse cevap temkinli verilir. Source discovery ciktilari kullanici dostu ve Turkce karakterli olmalidir.

## Final Demo / Release Readiness Audit

Bu fazda runtime davranisi degistirilmeden dokumantasyon, demo script, release summary ve repository guvenligi kontrol edilir.

Calistirilacak komutlar:

```bash
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
python evaluation/evaluate_answer_grounding.py --questions evaluation/answer_grounding_questions.json --out answer_grounding_report.local.json --markdown-out answer_grounding_summary.local.md
python -m pytest tests/ -v
```

Release veya tag olusturulmaz. Local artifactler commit edilmez. Son dogrulanmis metrikler dokumanlara gercek komut ciktisi uzerinden yazilir.

## Dynamic Dining Menu Date Queries

Yemekhane reader, endpoint icindeki menu verisini gun bazli parse eder. Tarihli sorgularda yalnizca ilgili gunun menusu dondurulur; hafta sorgularinda gun gun sinirli liste verilir.

Tarih bulunamazsa mevcut tarih araligi belirtilir ve menu uydurulmaz. `Ogun Yok` olan gunlerde bu durum acikca soylenir. Yemekhane verisi ChromaDB snapshot'a gomulmez; dynamic source olarak okunur.

Turkce ekli ay ifadeleri desteklenir: `5 mayista`, `5 Mayis'ta`, `5 mayisda`, `21 mayista`. Gun + ay yakalanirsa single-day intent, hafta/ay liste davranisindan once gelir. Ay geneli belirsiz sorgularda tum ay dokulmez; kullanicidan belirli gun veya tarih istenir.

Test komutlari:

```bash
python evaluation/evaluate_dynamic_menu.py --questions evaluation/dynamic_menu_smoke_questions.json --out dynamic_menu_report.local.json --markdown-out dynamic_menu_summary.local.md
python evaluation/run_regression_suite.py --profile dynamic-source --use-local-chroma-copy
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
python -m pytest tests/ -v
```

## ChromaDB Local Runtime Copy

Normal local evaluation sirasinda tracked `chroma_db/` snapshot dosyalarinin kirlenmesini azaltmak icin local runtime copy modu kullanilabilir:

```bash
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
```

Bu mod child process'lere `CHROMA_USE_LOCAL_COPY=1` verir ve Chroma runtime path'ini `.local_chroma_runtime/chroma_db` altindaki gecici kopyaya yonlendirir. `.local_chroma_runtime/` commit edilmez.

Snapshot update ve ingestion isleri bu modu kullanmaz; bu isler icin ChromaDB snapshot procedure takip edilir. `chroma_db/chroma.sqlite3` local modified gorunurse stage edilmez; branch gecisini engellerse sadece o dosya guvenli stash'e alinir.

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
## Chroma Coverage QA and Rewrite Safety

Faz 10B kapsamındaki güvenlik kontrolleri, mevcut Chroma snapshot'ını değiştirmeden coverage ve manuel kabul risklerini ölçer.

Komutlar:

```bash
python tools/audit_chroma_coverage.py --chroma-dir chroma_db --out chroma_coverage_inventory.local.json --markdown-out chroma_coverage_inventory.local.md
python tools/generate_chroma_coverage_questions.py --chroma-dir chroma_db --out vector_coverage_questions.generated.local.json --markdown-out vector_coverage_questions.generated.local.md
python evaluation/evaluate_vector_coverage.py --questions vector_coverage_questions.generated.local.json --out vector_coverage_report.local.json --markdown-out vector_coverage_summary.local.md
python evaluation/evaluate_manual_acceptance.py --questions evaluation/manual_acceptance_questions.json --out manual_acceptance_report.local.json --markdown-out manual_acceptance_summary.local.md
python evaluation/run_regression_suite.py --profile full --use-local-chroma-copy
```

Rewrite veya multi-query çıktısı, kullanıcı sorusunu "bilgi yok" fallback cevabına dönüştürürse reddedilir. Çift anadal, AGNO/GANO, lisansüstü başvuru ve yemekhane menüsü gibi manuel canlı QA riskleri için hard-coded soru ID patch'i yapılmaz; genel rewrite, routing, rerank ve coverage kuralları kullanılır.
