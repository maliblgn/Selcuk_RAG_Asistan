# Article Metadata Matching Raporu

## Faz 5D Amaci

Faz 5D'nin amaci, Faz 5C sonrasi kalan `article_metadata_mismatch` ve `article_miss` bulgularini tekil soru patch'i yazmadan genel madde eslesmesi mekanizmasi ile iyilestirmektir. Calisma madde no, madde basligi, icerikte gecen `MADDE` ifadeleri, OCR/chunk varyasyonlari ve baslik normalizasyonuna odaklandi.

## Neden Article Metadata Mismatch Hedeflendi?

Faz 5C sonunda query vocabulary ve source title alias sorunlari buyuk olcude cozuldu:

- `query_vocabulary_gap`: 0
- `no_source_for_answer`: 0
- `relevance_filter_too_strict`: 0

Kalan riskler agirlikli olarak dogru belge icinde dogru maddeyi yakalama ve madde basligini toleransli okuma tarafinda toplandi. Bu nedenle Faz 5D, retrieval davranisini dar bir soru listesine gore degil, genel article metadata sinyallerine gore iyilestirdi.

## Eklenen Article Helperlari

`retrieval_normalization.py` icine su genel helperlar eklendi:

- `normalize_article_no`: `MADDE 43`, `43 uncu madde`, `43. madde`, `MADDE-43` gibi bicimleri ortak madde numarasina indirger.
- `extract_article_numbers`: content ve baslik icinden `MADDE 44`, `44 uncu madde` gibi madde numaralarini cikarir.
- `normalize_article_title`: madde no prefixlerini temizleyerek baslik karsilastirmasini sade hale getirir.
- `article_title_similarity_score`: normalized title overlap, phrase match ve content destegi ile baslik benzerligi hesaplar.
- `article_metadata_score`: beklenen madde no/baslik ile gercek metadata ve chunk content'i arasinda sinirli bir skor uretir.

Bu helperlar soru ID'sine bagli degildir; belge ailesi ve madde yapisi gibi genel sinyallerle calisir.

## Runtime Entegrasyonu

`retrieval_rerank.py` genel madde numarasi sinyallerini normalize ederek kullanacak sekilde guncellendi. Soru acikca `Madde X` gibi bir sinyal tasiyorsa ayni madde numarasi metadata veya content icinde bulunan chunk sinirli pozitif boost alir; farkli madde numarasi bulunan chunk ise kucuk negatif sinyal alir.

`rag_engine.py` relevance filtering tarafinda ayni genel article-number sinyali kullanildi. Bu entegrasyon sadece madde numarasi iceren sorularda sinirli skor etkisi yaratir; operasyonel fallback ve source panel guardrail davranisi korunur.

## Evaluation Entegrasyonu

`evaluation/evaluate_retrieval.py` icinde `article_hit_at_1` ve `article_hit_at_3` hesaplamalari artik:

- normalized article no karsilastirmasi,
- content icinden madde numarasi cikarimi,
- normalized/partial article title similarity,
- `article_metadata_score`

kullanir. Bu sayede format farklari basarisizlik olarak sayilmaz; ancak yanlis madde numarasi sadece baslik benziyor diye kolayca dogru kabul edilmez.

`evaluation/triage_retrieval_failures.py` direct script calistirmasinda root import path ile uyumlu hale getirildi ve article metadata mismatch ayrimi normalized helperlarla desteklendi.

## Article Metadata Audit Scripti

Yeni script:

```bash
python evaluation/audit_article_metadata.py --golden evaluation/golden_questions.json --out article_metadata_audit.local.json --markdown-out article_metadata_audit.local.md
```

Bu script golden answer sorularinda beklenen madde no/baslik ile production retrieval sonucundaki top kaynak metadata'sini karsilastirir. Cikti local artifact'tir ve commit edilmez.

Audit ozeti:

- total_answer_questions: 31
- questions_with_expected_article: 31
- article_miss_candidates: 7
- missing_article_no_count: 0
- missing_article_title_count: 0
- content_article_phrase_found_count: 31
- suspected_metadata_mismatch_count: 20

## Onceki Metrikler

Faz 5C baseline:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.645
- article_hit_at_3: 0.774
- expected_terms_hit_rate: 0.953
- fallback_accuracy: 1.000
- critical_failure_count: 2

## Yeni Metrikler

Faz 5D sonrasi:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.677
- article_hit_at_3: 0.774
- expected_terms_hit_rate: 0.953
- fallback_accuracy: 1.000
- critical_failure_count: 2

Triage sonucu:

- article_miss: 7
- document_miss: 2
- inspect: 2
- article_metadata_mismatch: 7
- metadata_title_mismatch: 4

## Article Hit Degisimi

`article_hit_at_1` 0.645'ten 0.677'ye yukseldi. `article_hit_at_3` 0.774 seviyesinde korundu. Bu, top-1 siralamada bazi format/tolerans sorunlarinin daha iyi yakalandigini, ancak kalan hatalarin cogunlukla daha derin metadata baslik veya golden expectation incelemesi gerektirdigini gosterir.

## Fallback Accuracy

`fallback_accuracy` 1.000 olarak korundu. Operasyonel/guncel bilgi ve corpus disi sorularda guvenli fallback davranisi zayiflatilmadi.

## Kalan Riskler

- Bazi madde basliklari dogru belge icinde olsa bile golden expected title ile chunk metadata title arasinda kismi farklar kalabiliyor.
- Audit, content icinde madde ifadelerinin bulundugunu ancak baslik eslesmesinde daha ayrintili inceleme gerektiren adaylar oldugunu gosteriyor.
- Kalan `document_miss` ornekleri source alias/golden expectation tarafinda ayrica ele alinmali.

## Hard-Coded Patch Yapilmadi

Bu fazda yeni soru ID'sine veya belirli golden soruya ozel kural eklenmedi. Degisiklikler genel article normalization, madde no extraction, title similarity ve evaluation toleransi uzerinden yapildi.

## Sonraki Oneriler

- Source inventory alias audit ile kalan metadata title mismatch adaylarini incelemek.
- OCR/chunking supheli kaynaklari ayri listelemek.
- Sinirli LLM answer quality evaluation veya RAGAS benzeri cevap-kalite denemesi yapmak.
