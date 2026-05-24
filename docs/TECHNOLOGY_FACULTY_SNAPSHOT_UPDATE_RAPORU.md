# Technology Faculty Snapshot Update Report

## Faz 8B-2 Amaci

Bu fazda Teknoloji Fakultesi icin daha once manifest ve audit katmani hazirlanan statik web/PDF kaynaklari kontrollu sekilde mevcut ChromaDB snapshot'a eklendi.

Bu calisma yalnizca Teknoloji Fakultesi static kaynaklarini kapsar. Yemekhane, ogrenci duyurulari veya yuksek tazelik gerektiren dinamik kaynaklar snapshot'a eklenmedi.

## Islenen Kaynaklar

Toplam 8 resmi kaynak adayi islendi:

- Teknoloji Fakultesi Yonerge ve Yonetmelikler
- Teknoloji Fakultesi Staj Uygulama Yonergesi
- Teknoloji Fakultesi Isletmede Mesleki Egitim Nedir
- Teknoloji Fakultesi Isletmede Mesleki Egitim Yonergesi
- Teknoloji Fakultesi Sikca Sorulan Sorular
- Teknoloji Fakultesi Is Akis Semasi
- Teknoloji Fakultesi Akademik Formlar
- Teknoloji Fakultesi Fakulte Katalogu

Manifestteki iki PDF URL'si resmi Teknoloji Fakultesi yonerge sayfasindaki guncel `webadmin.selcuk.edu.tr` PDF adresleriyle hizalandi. Eski `tf.selcuk.edu.tr` PDF adresleri preflight sirasinda 404 dondugu icin snapshot'a alinmadi.

## Preflight Sonucu

- total_sources: 8
- successful_count: 8
- failed_count: 0
- high_priority_count: 5
- high_priority_successful_count: 5
- pdf_count: 2
- html_count: 6
- all_high_priority_accessible: true

## Ingestion Sonucu

- processed_source_count: 8
- successful_source_count: 8
- failed_source_count: 0
- deleted_existing_chunks: 0
- added_chunk_count: 107
- net_document_count_delta: 107
- net_unique_source_count_delta: 8

## Snapshot Sayilari

Once:

- unique_source_count: 149
- document/chunk count: 2985
- technology_source_count: 0

Sonra:

- unique_source_count: 157
- document/chunk count: 3092
- technology_source_count: 8

## Source Discovery Evaluation

`evaluation/evaluate_source_discovery.py` smoke seti basariyla calisti:

- total_questions: 3
- passed: 3
- failed: 0
- mode_match_rate: 1.0
- min_match_pass_rate: 1.0
- expected_terms_hit_rate: 1.0
- no_match_count: 0

Manual kontrol sonucu:

- `teknoloji fakultesi ile alakali kaynak var mi`: source discovery modunda 8 eslesme dondu.
- `teknoloji fakultesi staj yonergesi var mi`: ilgili Teknoloji Fakultesi Staj Uygulama Yonergesi ilk sirada dondu.
- `isletmede mesleki egitim kaynaklari nelerdir`: Teknoloji Fakultesi IME sayfasi ve IME yonergesi ust siralarda dondu.
- `AKTS nedir`: source discovery moduna girmedi; normal RAG cevap modunda kaldi.

## Retrieval / Smoke / Answer Quality

Retrieval evaluation sonrasi:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.645
- article_hit_at_3: 0.710
- expected_terms_hit_rate: 0.953
- fallback_accuracy: 1.000
- critical_failure_count: 2

Belge hit metrikleri ve fallback accuracy korundu. Article hit metriklerinde mevcut local olcumde onceki bilinen degerlere gore dusus goruldu; bu durum snapshot update raporunda acik risk olarak not edildi ve sonraki fazda article-level retrieval stabilizasyonu icin izlenmelidir.

General smoke:

- total_questions: 34
- triage_status_counts.ok: 23
- smoke_fallback_count: 11

Answer quality dry-run:

- total_questions: 14
- skipped_questions: 14
- source_block_leak_count: 0
- url_leak_count: 0
- critical_failure_count: 0

Provider comparison dry-run:

- total_providers: 1
- evaluated_providers: 0
- skipped_providers: 1
- provider_status_counts.skipped_disabled: 1

Test:

- 278 passed
- 2 skipped

## Riskler ve Sinirlamalar

- Teknoloji Fakultesi kaynaklari resmi web/PDF adreslerinden alinmistir; sayfa veya PDF URL'leri ileride degisebilir.
- Article-level retrieval metrikleri snapshot update sonrasinda izlenmelidir.
- Bu faz dynamic kaynaklari kapsamaz.
- Yemekhane menu ve ogrenci duyurulari statik snapshot'a eklenmedi.

## Guvenlik ve Commit Kapsami

- ChromaDB snapshot bilincli olarak degisti.
- `data/*.pdf` commit edilmedi.
- `.env` commit edilmedi.
- API key/secret commit edilmedi.
- Local preflight/ingestion/evaluation artifact dosyalari commit edilmedi.
