# Technology Faculty Retrieval Triage Report

## Faz 8B-2A Amaci

Bu rapor, Faz 8B-2 kapsaminda Teknoloji Fakultesi static kaynaklari ChromaDB snapshot'a eklendikten sonra gorulen article hit dususunu ve `critical_failure_count: 2` durumunu analiz eder.

Bu fazda yeni ingestion yapilmadi, ChromaDB snapshot bilincli olarak degistirilmedi ve runtime dosyalarina dokunulmadi.

## Snapshot Sonrasi Metrik Degisimi

Onceki bilinen metrikler:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.677
- article_hit_at_3: 0.774
- fallback_accuracy: 1.000
- critical_failure_count: 2

Snapshot update sonrasi yeniden olculen metrikler:

- document_hit_at_1: 0.903
- document_hit_at_3: 0.935
- article_hit_at_1: 0.645
- article_hit_at_3: 0.710
- expected_terms_hit_rate: 0.953
- fallback_accuracy: 1.000
- critical_failure_count: 2

Belge hit metrikleri ve fallback accuracy korunmustur. Article-level metriklerde dusus vardir.

## Critical Failure Sorulari

Retrieval triage sonucunda kritik iki soru ayni kalmistir:

### golden_ales_definition

- Soru: `Lisansustu basvurularda ALES neyi ifade eder?`
- Beklenen belge: `Lisansustu Egitim ve Ogretim Yonetmeligi`
- Beklenen madde: `4 / Tanimlar`
- Top filtered kaynaklar:
  - `Butunlesik Yuksek Lisans Yonergesi`, Madde 4 / Tanimlar
  - `Ogretim Uyesi Disindaki Ogretim Elemani Kadrolarina Yapilacak Atamalar...`, Madde 4 / Tanimlar
- Teknoloji Fakultesi kaynagi top filtered sonuclara girmedi.
- Degerlendirme: Bu problem Teknoloji Fakultesi ingestion kaynakli degildir. Soru genel `ALES` tanimini hedefledigi icin benzer Madde 4 tanim kaynaklari yuksege cikmaktadir. Kategori: metadata/title expectation veya rerank target document ayrimi.

### golden_onlisans_lisans_agno

- Soru: `On lisans ve lisans egitiminde agirlikli genel not ortalamasi nasil tanimlanir?`
- Beklenen belge: `On Lisans ve Lisans Egitim-Ogretim ve Sinav Yonetmeligi`
- Beklenen baslik: `Tanimlar`
- Top filtered kaynaklar:
  - `Lisansustu Egitim ve Ogretim Yonetmeligi`, Madde 21 / Not ortalamasi
  - `Lisansustu Egitim-Ogretim Yonetmeligi Uygulama Esaslari`
- Teknoloji Fakultesi kaynagi top filtered sonuclara girmedi.
- Degerlendirme: Bu problem Teknoloji Fakultesi ingestion kaynakli degildir. `agirlikli not ortalamasi` ifadesi lisansustu not ortalamasi maddesini yuksege tasimaktadir. Kategori: document discrimination / rerank veya expected document ayrimi.

## Article Hit Dususu

Current article miss listesi:

- `golden_seminer_definition`
- `golden_butunlesik_doktora_definition`
- `golden_cift_anadal_amac`
- `golden_cift_anadal_kapsam`
- `golden_diploma_eki_kapsam`
- `golden_ogrenci_topluluklari_danisman`
- `golden_veteriner_olcme_islemi`
- `golden_yabanci_uyruklu_kabul`

Article hit at-3 false olan answer sorulari:

- Yukaridaki 8 article_miss sorusu
- `golden_onlisans_lisans_agno`

Bu listedeki top-5 filtered sonuclarin hicbirinde `source_family=technology_faculty` kaynagi gorulmedi. Bu nedenle article hit dususu, Teknoloji Fakultesi kaynaklarinin eski mevzuat/legal sorulari bastirmasindan kaynaklanmiyor.

Muhtemel nedenler:

- Snapshot'a yeni embedding eklenmesi ChromaDB koleksiyon skor dagilimini ve yakin komsu siralamasini az da olsa etkiliyor.
- Article-level beklenen madde secimi bazi sorularda dokuman dogru olsa bile farkli maddeye kayiyor.
- Bazi sorularda current behavior zaten Faz 5 sonrasi kalan article metadata/rerank hassasiyetine benziyor.

Bu fazda pre-snapshot local detailed report commitli artifact olarak bulunmadigi icin dususe neden olan iki ek article-at-3 miss'i kesin olarak eski/yeni ID bazinda birebir diff'lemek mumkun olmadi. Ancak current miss setinde Teknoloji Fakultesi kaynaklarinin eski sorulari bastirdigine dair bulgu yoktur.

## Teknoloji Fakultesi Metadata Kontrolu

Teknoloji Fakultesi chunk metadata kontrolu:

- technology chunk count: 107
- technology source count: 8
- source_type dagilimi:
  - web_page: 64
  - web_pdf: 43
- ingestion_batch: `faz8b2_technology_faculty`
- Eksik metadata alanlari: yok

Kontrol edilen alanlar:

- source_owner
- source_family
- category
- source_type
- title
- url
- final_url
- expected_topics
- freshness
- ingestion_batch

## Audit Sonuclari

Retrieval triage:

- total_failures: 12
- article_miss: 8
- document_miss: 2
- inspect: 2
- article_metadata_mismatch: 8
- metadata_title_mismatch: 4

Article metadata audit:

- total_answer_questions: 31
- questions_with_expected_article: 31
- article_miss_candidates: 8
- missing_article_no_count: 0
- missing_article_title_count: 0
- suspected_metadata_mismatch_count: 20

Source inventory alias audit:

- total_sources: 157
- exact_document_matches: 31
- missing_document_matches: 0
- alias_candidate_count: 0
- article_expectation_review_count: 0
- likely_source_metadata_issue_count: 0

## Risk Degerlendirmesi

- Teknoloji Fakultesi source discovery kabul kriterleri karsilandi.
- Normal document_hit_at_1/3 korunuyor.
- fallback_accuracy 1.000 olarak korunuyor.
- Critical failure sayisi artmadi.
- Teknoloji Fakultesi kaynaklari eski kritik/top article miss sorularinda ust siralara girmiyor.
- Article hit metriklerinde dusus var ve izlenmeli.

## Onerilen Karar

Bu triage'a gore Teknoloji Fakultesi ingestion eski retrieval davranisini belirgin sekilde bozmuyor. Main'e alma icin bloklayici bir Teknoloji kaynak gürültüsü bulgusu yoktur.

Ancak article hit dususu goruldugu icin sonraki adim olarak ayri bir article-level retrieval stabilization fazi onerilir:

- article hit regression diff artifact'i kalici hale getirilsin
- query/document discrimination sinyalleri incelensin
- `ALES`, `AGNO`, `amac/kapsam` gibi ortak terimli sorularda document-specific rerank sinyalleri degerlendirilsin
- golden expectation zayiflatmasi yapilmadan once kaynak ve madde uyumu tekrar denetlensin

Bu fazda runtime fix veya golden expectation degisikligi yapilmadi.

## Guvenlik ve Commit Kapsami

- Yeni ingestion calistirilmadi.
- ChromaDB snapshot degisikligi stage edilmedi.
- `data/*.pdf` commit edilmedi.
- `.env` commit edilmedi.
- API key/secret commit edilmedi.
- Local evaluation artifact dosyalari commit edilmedi.
