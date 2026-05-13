# Retrieval Evaluation Raporu

## Faz 5A Amaci

Faz 5A'nin amaci, RAG sisteminin yalnizca AKTS, tez izleme ve doktora yeterlik gibi bilinen sorulara ozel kalmadigini olcmek icin daha resmi bir golden question regression seti ve retrieval metrikleri olusturmaktir. Bu faz LLM cevabi uretmez; retrieval, relevance filtering ve source mapping katmaninin davranisini gorunur hale getirir.

## Golden Question Set Yaklasimi

`evaluation/golden_questions.json` dosyasi resmi regression seti olarak genisletildi. Set, akademik tanimlar, madde bazli akademik yonetmelik sorulari, farkli yonergeler, fakulteye ozel kaynaklar, arastirma yonetimi, sayisal/hesaplama sorulari, guncel operasyonel bilgi ve corpus disi hallucination testlerini kapsar.

Set ozeti:

- Toplam soru: 44
- Answer beklenen soru: 31
- Fallback beklenen soru: 13
- Kategori sayisi: 8

Kategori dagilimi:

| kategori | soru sayisi |
|---|---:|
| academic_article | 7 |
| academic_definition | 5 |
| calculation_numeric | 3 |
| directive_specific | 11 |
| faculty_specific | 3 |
| operational_current_info | 9 |
| out_of_corpus_hallucination | 4 |
| research_administration | 2 |

## Answer / Fallback Ayrimi

Answer beklenen sorularda golden kayit, beklenen belge, belge alias'lari, madde numarasi, madde basligi ve beklenen terimleri tasir. Fallback beklenen sorularda guncel operasyonel bilgi veya corpus disi iddia vardir; guclu kaynak kalmamasi dogru kabul edilir.

AKTS, tez izleme ve doktora yeterlik sorulari sette korunmustur, ancak toplam setin kucuk bir bolumudur. Burs, staj, cift ana dal, kutuphane, bilimsel arastirma/yayin etigi, mazeret, diploma eki, ogrenci topluluklari, veteriner olcme-degerlendirme ve yabanci uyruklu ogrenci kabul kaynaklari da kapsama alindi.

## Kullanilan Metrikler

`evaluation/evaluate_retrieval.py` su metrikleri uretir:

- `document_hit_at_1`: beklenen belge ilk filtrelenmis kaynakta mi?
- `document_hit_at_3`: beklenen belge ilk uc filtrelenmis kaynak icinde mi?
- `article_hit_at_1`: beklenen madde ilk filtrelenmis kaynakta mi?
- `article_hit_at_3`: beklenen madde ilk uc filtrelenmis kaynak icinde mi?
- `expected_terms_hit_rate`: beklenen terimlerin filtrelenmis kaynak metinlerinde bulunma orani
- `fallback_accuracy`: fallback beklenen sorularda filtrelenmis kaynak kalmama orani
- `source_available_rate`: answer beklenen sorularda en az bir filtrelenmis kaynak bulunma orani
- `critical_failure_count`: `document_miss`, `fallback_mismatch` ve `no_source_for_answer` sayisi

Soru bazinda `evaluation_status` su degerlerden biri olur:

- `ok`
- `document_miss`
- `article_miss`
- `expected_terms_miss`
- `fallback_mismatch`
- `no_source_for_answer`
- `inspect`

## Ilk Evaluation Sonucu

Calistirilan komut:

```bash
python evaluation/evaluate_retrieval.py --golden evaluation/golden_questions.json --out retrieval_evaluation_report.local.json --markdown-out retrieval_evaluation_summary.local.md
```

Ilk metrik ozeti:

| metrik | deger |
|---|---:|
| document_hit_at_1 | 0.516 |
| document_hit_at_3 | 0.548 |
| article_hit_at_1 | 0.548 |
| article_hit_at_3 | 0.548 |
| expected_terms_hit_rate | 0.672 |
| fallback_accuracy | 1.000 |
| source_available_rate | 0.710 |
| critical_failure_count | 14 |

Durum dagilimi:

| status | sayi |
|---|---:|
| ok | 25 |
| inspect | 1 |
| expected_terms_miss | 1 |
| article_miss | 3 |
| document_miss | 5 |
| no_source_for_answer | 9 |

## Riskli Soru Tipleri

Ilk kosuda ozellikle bazi farkli yonerge sorularinda filtrelenmis kaynak bulunamadi. Bu durum dogrudan runtime patch gerektirmez; hangi kaynaklarin query vocabulary, metadata veya chunking nedeniyle zayif kaldigini inceleme adayi yapar.

Article miss olan bazi akademik sorularda beklenen dokuman bulunurken madde basligi veya OCR/chunk metadata varyasyonu nedeniyle madde eslesmesi kacabilir. Bu da Faz 5B'de daha ayrintili golden evaluation ile izlenmelidir.

Fallback beklenen sorularda ilk kosu basarilidir: guncel operasyonel veya corpus disi sorularda kaynak bulunmama davranisi 1.000 fallback accuracy verdi.

## Runtime Davranisi

Bu fazda runtime RAG davranisi degistirilmedi. `app.py`, `rag_engine.py` ve `retrieval_rerank.py` dosyalarina dokunulmadi. Yeni calisma yalnizca evaluation seti, evaluation scripti, testler ve dokumantasyon ekler.

## Sonraki Faz 5B Onerisi

Faz 5B icin onerilen adim, bu retrieval metriklerini sinirli LLM cevap kalite degerlendirmesiyle birlestirmektir. Kucuk bir subset uzerinde citation binding, fallback dogrulugu, source-grounded answer kalitesi ve olasi RAGAS benzeri metrikler denenebilir. Bu adimda da hard-coded soru patch'lerinden kacinilmali ve once metriklerle riskli basliklar netlestirilmelidir.
