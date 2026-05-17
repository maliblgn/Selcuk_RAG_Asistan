# Answer Expected Terms Review Raporu

## Faz 5J Amaci

Bu fazda Faz 5I live answer quality kosusunda kalan tek final kritik bulgu incelendi:

- `answer_tez_izleme_komitesi`
- durum: `expected_terms_miss`

Amac runtime davranisini degistirmek degil, answer quality evaluation beklentisinin final kullanici cevabi ve kaynak baglamiyla uyumlu olup olmadigini kontrol etmektir.

## Incelenen Bulgu

Soru:

> Tez izleme komitesi kac ogretim uyesinden olusur?

Live final cevap:

> Tez izleme komitesi uc ogretim uyesinden olusur. [1]

Final cevapta:

- inline citation vardir.
- source block leak yoktur.
- URL leak yoktur.
- cevap dogru belge ve madde baglamiyla kaynaklidir.

## Expected Terms Incelemesi

Onceki `expected_terms`:

- `uc`
- `ogretim uyesi`
- `danisman`

Live final cevapta bulunan terimler:

- `uc`
- `ogretim uyesi`

Eksik gorunen terim:

- `danisman`

Bu soru komitenin kac ogretim uyesinden olustugunu sordugu icin `danisman` terimi zorunlu cevap beklentisi olarak fazla dardir. Danisman bilgisi kaynak maddede komitenin yapisi icinde yer alabilir, ancak sayi sorusuna verilen kisa ve dogru cevap icin zorunlu kalite terimi olmamalidir.

## Sorun Sinifi

Sinif:

- `expected_terms_too_strict`

Bu bulgu modelin final cevabinda source block veya URL kacagi oldugunu gostermemektedir. Ayrica retrieval/runtime hatasi da degildir.

## Yapilan Degisiklik

Sadece `evaluation/answer_quality_questions.json` icindeki `answer_tez_izleme_komitesi` kaydi guncellendi:

- `danisman` terimi `expected_terms` listesinden cikarildi.
- Kayda Faz 5J incelemesini aciklayan `notes` alani eklendi.

Runtime dosyalari degistirilmedi:

- `app.py`
- `rag_engine.py`
- `retrieval_rerank.py`
- `retrieval_normalization.py`

## Yeni Sonuc Beklentisi

Bu duzeltmeden sonra ayni final cevap kalite olarak `ok` sayilmalidir:

- `expected_terms_found`: `uc`, `ogretim uyesi`
- `expected_terms_missing`: bos
- `source_block_leak_count`: 0
- `url_leak_count`: 0

## Sonraki Oneri

Benzer durumlar cogalirsa answer quality schema'sina genel `expected_term_groups` veya alternatif terim gruplari eklenebilir. Bu fazda buna gerek duyulmadi; tek sorun, soru kapsamindan daha dar bir zorunlu terim beklentisiydi.
