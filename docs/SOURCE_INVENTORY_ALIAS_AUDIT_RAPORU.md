# Source Inventory Alias Audit Raporu

## Faz 5E Amaci

Faz 5E'nin amaci, Faz 5D sonrasinda kalan `metadata_title_mismatch` ve `article_metadata_mismatch` bulgularini runtime patch yazmadan incelemektir. Bu faz, kalan farklarin gercek retrieval hatasi mi yoksa source inventory baslik varyasyonu, eksik alias, golden expectation fazlaligi, OCR/chunk metadata farki veya dokuman basligi varyasyonu mu oldugunu ayirmaya yarayan audit katmani ekler.

## Neden Source Inventory Alias Audit Yapildi?

Faz 5D sonunda temel retrieval metrikleri guclu kaldi:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.677
- article_hit_at_3: 0.774
- fallback_accuracy: 1.000
- critical_failure_count: 2

Kalan triage kok nedenleri:

- article_metadata_mismatch: 7
- metadata_title_mismatch: 4

Bu tablo, dogrudan scoring degistirmek yerine once golden beklentilerin ve kaynak envanteri basliklarinin birlikte incelenmesi gerektigini gosterdi.

## Runtime Patch Yapilmadi

Bu fazda `app.py`, `rag_engine.py`, `retrieval_rerank.py` ve `retrieval_normalization.py` degistirilmedi. Alias config veya golden question set de degistirilmedi. Eklenen katman yalnizca audit ve raporlama amaclidir.

## Audit Scriptinin Mantigi

Yeni script:

```bash
python evaluation/audit_source_inventory_aliases.py --golden evaluation/golden_questions.json --out source_inventory_alias_audit.local.json --markdown-out source_inventory_alias_audit.local.md
```

Script LLM cagrisi yapmaz. ChromaDB metadata'sini, `evaluation/golden_questions.json` icindeki expected document/article alanlarini ve `config/retrieval_aliases.json` alias yapisini okur.

Script su kontrolleri yapar:

- ChromaDB uzerinden unique source inventory cikarir.
- Golden `expected_document` ve `expected_document_aliases` alanlarini source title, file name ve URL metadata'siyle normalized olarak karsilastirir.
- Exact, alias ve missing document match ayrimi yapar.
- Expected article no/title alanlarini source inventory'deki article number/title setleriyle karsilastirir.
- Alias candidate, golden expectation review ve source metadata/chunking review adaylarini ayirir.

## Ilk Audit Sonucu

Audit sonucu:

- total_sources: 149
- total_golden_questions: 44
- questions_with_expected_document: 31
- exact_document_matches: 29
- alias_document_matches: 2
- missing_document_matches: 0
- alias_candidate_count: 0
- article_expectation_review_count: 2
- likely_source_metadata_issue_count: 0
- top_priority_ids: yok

Issue dagilimi:

- article_title_too_strict: 2
- expected_document_too_strict: 2

Recommended action dagilimi:

- relax_golden_expected_document_alias: 2
- review_expected_article_title: 2

## Alias / Golden Expectation / Source Metadata Ayrimi

Audit, 31 answer beklenen golden sorunun tamaminda beklenen dokumanin inventory tarafinda bulunabildigini gosterdi. Eksik dokuman veya yeni ChromaDB snapshot ihtiyaci isaretlenmedi.

Iki soru document alias uzerinden eslesti. Bu durum runtime alias eksiginden cok golden `expected_document` ifadesinin inventory'deki URL-encoded veya resmi dosya basligi varyasyonuna gore fazla dar olabilecegini gosteriyor.

Iki soru article title expectation review adayi olarak isaretlendi. Bu sorularda beklenen madde numarasi kaynak envanterinde mevcut, ancak expected article title ile chunk metadata title arasinda baslik varyasyonu var. Bu nedenle dogrudan runtime scoring degistirmek yerine golden expected article title'in veya source metadata basliginin incelenmesi onerilir.

## Karar

Bu faz dogrudan alias config'i degistirmez. Bu fazin amaci hangi aliaslarin veya golden expectation duzeltmelerinin guvenli sekilde yapilabilecegini belirlemektir.

Bir sonraki fazda yalniz audit ile desteklenen genel alias/golden duzeltmeleri uygulanabilir. Bu duzeltmeler soru ID'sine gore degil, belge/terim ailesi duzeyinde yapilmalidir.

## Onerilen Sonraki Adimlar

- `expected_document_too_strict` cikan iki golden soruda expected document alias kapsamlarini gozden gecirmek.
- `article_title_too_strict` cikan iki golden soruda expected article title ile ChromaDB article metadata title farkini elle incelemek.
- Source metadata baslik varyasyonlari icin gerekirse belge ailesi duzeyinde alias onermek.
- Runtime scoring degisikligi yapmadan once retrieval evaluation, triage, article audit, source inventory alias audit, general smoke ve pytest komutlarini birlikte calistirmak.
