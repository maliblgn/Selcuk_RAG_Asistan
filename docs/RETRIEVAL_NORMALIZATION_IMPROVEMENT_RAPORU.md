# Retrieval Normalization Improvement Raporu

## Faz 5C Amaci

Faz 5C'nin amaci, Faz 5B triage sonucunda one cikan `query_vocabulary_gap` ve `metadata_title_mismatch` problemlerini tekil soru patch'i yazmadan genel normalization ve alias mekanizmasiyla iyilestirmektir. Calisma 149 kaynaklik corpus geneline yoneliktir.

## Neden Query Vocabulary ve Metadata Alias Hedeflendi?

Faz 5B triage sonucunda failure/inspect kayitlarinin buyuk kismi su iki kok nedene toplandi:

- `query_vocabulary_gap`: 7
- `metadata_title_mismatch`: 6

Bu iki sinif, kullanici sorusundaki terimler ile kaynak basligi, belge ailesi veya metadata alanlari arasindaki yazim/terim farklarindan etkilenir. Bu nedenle cozum, soru ID'sine bagli kural yerine ortak Turkish/ASCII normalization, URL decode, title similarity ve belge ailesi alias eslesmesi olarak tasarlandi.

## Eklenen Normalization Helperlari

Yeni `retrieval_normalization.py` dosyasi eklendi:

- `normalize_text(text)`: URL decode, lower/casefold, Turkce karakter uyumu, Unicode normalize, noktalama ve fazla bosluk temizligi yapar.
- `normalize_ascii_lite(text)`: karsilastirma icin c/g/i/o/s/u gibi ASCII varyant uretir.
- `tokenize_for_match(text)`: kisa tokenlari eleyerek matching token seti uretir.
- `title_similarity_score(query, title, aliases)`: normalized token overlap, phrase ve alias sinyallerini puanlar.
- `article_match_score(expected_or_query, article_no, article_title, content)`: madde no, madde basligi ve content phrase eslesmesini puanlar.
- `load_retrieval_aliases(path)`: alias config yoksa sistemi dusurmeden bos config dondurur.

## Alias Config Yapisi

Yeni `config/retrieval_aliases.json` dosyasi eklendi. Config iki bolumden olusur:

- `term_aliases`: genel terim ailesi es anlamlari
- `document_aliases`: belge ailesi / kaynak basligi aliaslari

Aliaslar soru ID'sine gore degil, genel terim veya belge ailesi duzeyinde tutulur. Ornek alanlar: AKTS, ALES, tez izleme, doktora yeterlik, basari notu, staj, cift ana dal, kutuphane, BAP, etik, mazeret, diploma eki ve ogrenci topluluklari.

## Runtime Entegrasyonu

Runtime davranisinda genel mekanizma olarak iki noktaya entegrasyon yapildi:

- `retrieval_rerank.py`: metadata-aware rerank scoring, shared normalization helperlari ve title/document alias scoring ile guclendirildi.
- `rag_engine.py`: relevance filtering, source title/file name/article title alanlarini daha iyi normalize eder; title similarity ve document alias score ek sinyal olarak kullanilir.

Fallback guardrail korunmak icin operasyonel/guncel bilgi sorularinda acik destek yoksa ek penalti uygulanir. Bu sayede alias/title boost'u kutuphane saati, servis saati, ucret, bugun ve tum ogrencilere yonelik iddialar gibi sorularda kaynak paneline alakasiz belge sokmaz.

## Evaluation Entegrasyonu

`evaluation/evaluate_retrieval.py`, document ve article eslesmelerinde yeni shared normalization helperlarini kullanacak sekilde guncellendi. Beklenen belge aliaslari ve madde basligi eslesmeleri normalize edilmis partial/title similarity ile degerlendirilir. Bu, gercek eslesmeleri katı string farklari yuzunden kacirmayi azaltir.

## Onceki Metrikler

| metrik | onceki |
|---|---:|
| document_hit_at_1 | 0.516 |
| document_hit_at_3 | 0.548 |
| article_hit_at_1 | 0.548 |
| article_hit_at_3 | 0.548 |
| expected_terms_hit_rate | 0.672 |
| fallback_accuracy | 1.000 |
| source_available_rate | 0.710 |
| critical_failure_count | 14 |

Onceki triage kok neden dagilimi:

| root cause | sayi |
|---|---:|
| query_vocabulary_gap | 7 |
| metadata_title_mismatch | 6 |
| article_metadata_mismatch | 3 |
| relevance_filter_too_strict | 2 |
| chunking_or_ocr_issue | 1 |

## Yeni Metrikler

| metrik | yeni |
|---|---:|
| document_hit_at_1 | 0.903 |
| document_hit_at_3 | 0.935 |
| article_hit_at_1 | 0.645 |
| article_hit_at_3 | 0.774 |
| expected_terms_hit_rate | 0.953 |
| fallback_accuracy | 1.000 |
| source_available_rate | 1.000 |
| critical_failure_count | 2 |

Yeni triage kok neden dagilimi:

| root cause | sayi |
|---|---:|
| article_metadata_mismatch | 7 |
| metadata_title_mismatch | 5 |

## Iyilesen ve Kalan Alanlar

Iyilesenler:

- `document_hit_at_1`: 0.516 -> 0.903
- `document_hit_at_3`: 0.548 -> 0.935
- `article_hit_at_1`: 0.548 -> 0.645
- `article_hit_at_3`: 0.548 -> 0.774
- `expected_terms_hit_rate`: 0.672 -> 0.953
- `source_available_rate`: 0.710 -> 1.000
- `critical_failure_count`: 14 -> 2
- `query_vocabulary_gap`: 7 -> 0
- `relevance_filter_too_strict`: 2 -> 0

Kalan ana risk:

- `article_metadata_mismatch` sayisi 7 olarak gorunuyor. Bu, sonraki fazda madde basligi/no extraction ve OCR/chunk metadata toleransinin ayrica ele alinmasi gerektigini gosterir.

## Fallback Accuracy

Ilk denemede alias/title boost'u operasyonel ve corpus disi sorulara fazla kaynak bagladigi icin fallback accuracy 0.769'a dusmustu. Bu kabul edilmedi. Operasyonel/guncel bilgi ve evrensel iddia sorularinda acik destek yoksa penalti uygulanarak fallback accuracy tekrar 1.000 seviyesinde korundu.

## Hard-Coded Patch Notu

Bu fazda `if question == ...` veya golden soru ID'sine bagli bir patch yazilmadi. Alias config genel terim ve belge ailesi duzeyindedir. AKTS, tez izleme ve doktora yeterlik gibi bilinen sorular icin yeni ozel kural eklenmedi.

## Sonraki Oneri

Bir sonraki adimlar:

- Article metadata matching ve article title tolerance iyilestirmesi
- Relevance filter tuning'in category bazli evaluation ile izlenmesi
- Source inventory alias audit
- OCR/chunking supheli kaynaklarin ayri raporlanmasi
