# General Smoke Evaluation Raporu

## Neden Sadece AKTS Sorulari Yeterli Degil?

AKTS, tez izleme komitesi ve doktora yeterlik sorulari sistemin kritik akademik maddeleri yakalayabildigini gosterir; ancak 149 kaynaklik korpusun geneli icin yeterli kanit degildir. RAG davranisinin birkac bilinen maddeye overfit edilmedigini anlamak icin farkli yonerge, fakulte, arastirma idaresi, operasyonel negatif ve hesaplama sorulariyla gorunurluk gerekir.

Bu calisma herhangi bir retrieval kuralini degistirmez. Amac, mevcut retrieval, metadata rerank, relevance filtering ve source-panel aday davranisini LLM cevabi uretmeden olcmektir.

## Temsili Soru Seti Yaklasimi

`evaluation/general_smoke_questions.json` dosyasina 34 soru eklendi. Her soru su alanlari tasir:

- `id`
- `question`
- `category`
- `expected_behavior`
- `expected_terms`
- `expected_document_hint`
- `expected_article_hint`
- `notes`

Soru seti hem cevap beklenen kaynakli sorulari hem de fallback beklenen operasyonel/kaynak disi sorulari icerir.

## Kategori Dagilimi

Ilk smoke kosusunda kategori dagilimi:

- `academic_regulation`: 6
- `directive_variety`: 10
- `operational_current_info`: 4
- `out_of_corpus_hallucination`: 5
- `calculation_numeric`: 4
- `faculty_regulation`: 3
- `research_administration`: 2

## Answer / Fallback Ayrimi

Beklenen davranis dagilimi:

- `answer`: 23
- `fallback`: 11

Fallback beklenen sorular ozellikle guncel saat, gunluk yemek, servis saatleri, rektorun gunluk programi, ucretsiz laptop ve tum ogrencilere aylik burs gibi statik yonerge korpusunda acik desteklenmemesi gereken konulari kapsar.

## Smoke Script

`evaluation/run_general_smoke.py` eklendi. Script LLM cagrisi yapmaz ve asagidaki bilgileri raporlar:

- `retrieved_doc_count`
- `filtered_doc_count`
- `top_document`
- `top_article`
- `expected_behavior`
- `has_relevant_source`
- `should_fallback`
- `source_panel_candidate_count`

Script mevcut `SelcukRAGEngine.retrieve()` ve `prepare_context_and_sources()` helper'larini kullanir. Bu nedenle kaynak paneli adaylari, uygulamanin kullandigi relevance filtering mantigiyla ayni yerden olculur.

## Ilk Smoke Sonucu Ozeti

Komut:

```bash
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json
```

Ozet:

- Soru sayisi: 34
- Kategori sayisi: 7
- Beklenen `answer`: 23
- Beklenen `fallback`: 11
- Smoke kararinda fallback: 19
- Answer beklenirken filtrelenmis kaynak bulunmayan soru sayisi: 10
- Fallback beklenirken filtrelenmis kaynak bulunan soru sayisi: 2

Olumlu ornekler:

- AKTS tanimi lisansustu yonetmeligi Madde 4 ile baglandi.
- Tez izleme komitesi lisansustu yonetmeligi Madde 44 ile baglandi.
- Doktora yeterlik sorusu Madde 43 ile baglandi.
- Turizm Fakultesi staj sorusu Turizm Fakultesi Staj Yonergesi ile baglandi.
- Meslek Yuksekokullari staj sorusu ilgili staj yonergesi Madde 5 ile baglandi.
- Kutuphane odunc verme sorusu Kutuphane Yonergesi ile baglandi.
- Bilimsel arastirma ve yayin etigi sorusu ilgili etik yonerge ile baglandi.
- Operasyonel saat/menu/bugun acik mi sorulari fallback kararina gitti.
- Kaynak disi laptop, aylik burs, servis saatleri ve rektor programi sorulari fallback kararina gitti.

## Gorulen Riskler

Ilk smoke calismasi bazi genisleme alanlarini gosterdi:

- Bazilari cevaplanabilir gorunen burs, diploma eki, ogrenci topluluklari, uzaktan ogretim, Eczacilik staj ve BAP sorularinda filtrelenmis kaynak olusmadi.
- Ders kredisi ve AKTS puani gibi hesaplama sorularinda fallback beklenirken kaynak adayi kalabildi. Bu durum cevap guardrail'leriyle birlikte ayrica izlenmelidir; uzun sayi dizisi uretilmemesi temel kriterdir.
- ALES sorusunda ilgili tanim bulunsa da top kaynak lisansustu yonetmeligi yerine butunlesik yuksek lisans yonergesi olabildi. Bu genel tanim retrieval davranisi acisindan izlenmelidir.
- Tip Fakultesi sinav sorusunda top kaynak genel on lisans/lisans sinav yonetmeligine kaydi. Fakulte-ozel terim agirligi gelecekte ayrica degerlendirilebilir.

## Sonraki Adim Onerisi

Bu fazda hard-coded patch yapilmadi. Sonraki asamada:

- Smoke raporu CI artifact'i olarak uretilebilir.
- `answer_expected_without_source` ve `fallback_expected_with_source` listeleri icin esik tabanli uyarilar eklenebilir.
- LLM'siz smoke sonucuna ek olarak sinirli sayida LLM cevap kalite kontrolu yapilabilir.
- Kaynak ipucu eslesmesi, URL decode ve Turkce karakter normalizasyonuyla daha ayrintili hale getirilebilir.

## Degistirilmeyenler

- ChromaDB icerigi degistirilmedi.
- Yeni ingestion calistirilmadi.
- AKTS, tez izleme veya doktora yeterlik icin yeni ozel kural eklenmedi.
- RAG cevap uretim davranisi degistirilmedi.
- `.env`, secret ve `data/*.pdf` dosyalari commit kapsaminda degildir.
