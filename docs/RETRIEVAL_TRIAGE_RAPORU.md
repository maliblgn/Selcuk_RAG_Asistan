# Retrieval Triage Raporu

## Faz 5B'nin Amaci

Faz 5B'nin amaci, Faz 5A golden retrieval evaluation sonucunda gorulen hatalari sistematik olarak siniflandirmak ve sonraki genel iyilestirme alanlarini belirlemektir. Bu rapor runtime cevap davranisini degistirmez; yalnızca evaluation ciktisini daha okunabilir ve takip edilebilir hale getirir.

## Neden Dogrudan Runtime Patch Yapilmadi?

Ilk metrikler bazi dokuman ve madde eslesmelerinde zayiflik oldugunu gosteriyor, ancak bu zayifliklar tekil sorulara ozel kural ekleyerek cozulmemelidir. Hard-coded patch'ler kisa vadede bir soruyu duzeltirken 149 kaynaklik corpus genelinde retrieval dengesini bozabilir. Bu nedenle once failure tipi, kategori ve olasi kok neden ayrimi yapildi.

## Ilk Retrieval Evaluation Metriklerinin Yorumu

Faz 5A kosusundaki ana metrikler:

| metrik | deger |
|---|---:|
| document_hit_at_1 | 0.516 |
| document_hit_at_3 | 0.548 |
| article_hit_at_1 | 0.548 |
| article_hit_at_3 | 0.548 |
| expected_terms_hit_rate | 0.672 |
| fallback_accuracy | 1.000 |
| critical_failure_count | 14 |

Fallback tarafindaki 1.000 skor, guncel operasyonel veya corpus disi sorularda sistemin kaynak uydurmama davranisinin iyi durumda oldugunu gosterir. Buna karsilik document/article hit metrikleri, farkli yonerge ve fakulte kaynaklarinda query vocabulary, metadata ve article-level matching tarafinda iyilestirme ihtiyaci oldugunu gosterir.

## Failure Type Aciklamalari

- `document_miss`: Beklenen dokuman filtrelenmis ilk 3 kaynakta bulunmadi.
- `article_miss`: Beklenen dokuman gelebilse bile madde no veya madde basligi eslesmedi.
- `no_source_for_answer`: Answer beklenen soru icin filtrelenmis kaynak kalmadi.
- `expected_terms_miss`: Beklenen terimler filtrelenmis kaynak metninde gorulmedi.
- `fallback_mismatch`: Fallback beklenen soruda guclu kaynak kaldi.
- `inspect`: Metrik tamamen basarisiz degil, ama top kaynak veya beklenti manuel incelenmeli.

## Possible Root Cause Aciklamalari

- `query_vocabulary_gap`: Soru terimleri ile kaynak metadata/content dili arasinda kelime, ek, Turkce karakter veya es anlamli farki var.
- `metadata_title_mismatch`: Kaynak basligi, alias veya source title normalizasyonu beklenen dokumanla yeterince eslesmiyor.
- `article_metadata_mismatch`: Madde numarasi veya madde basligi metadata'si beklenen maddeyle uyusmuyor.
- `relevance_filter_too_strict`: Retrieval adaylari var, ancak relevance filter final kaynaklari fazla agresif elemis olabilir.
- `source_missing_or_not_indexed`: Beklenen kaynak ChromaDB snapshot'ta olmayabilir veya inventory ile uyumsuz olabilir.
- `expected_document_hint_too_strict`: Golden beklenti fazla dar yazilmis olabilir.
- `chunking_or_ocr_issue`: Beklenen terim veya madde OCR/chunk siniri nedeniyle final chunk icinde gorunmuyor olabilir.
- `fallback_policy_review`: Fallback beklenen soruda kaynak kalmasi politika/esik incelemesi gerektirir.
- `needs_manual_review`: Otomatik siniflandirma yeterli guven vermiyorsa manuel bakilmalidir.

## Triage Sonucunda Gorulen Ana Problem Kumeleri

Ilk triage, sorunlarin tek bir bilinen akademik sorudan degil, farkli kaynak ailelerinden geldigini gosteriyor:

- Bazi yonerge sorularinda answer beklenirken final filtrelenmis kaynak bulunamiyor.
- Bazi akademik sorularda dogru dokuman bulunuyor ama article title/no eslesmesi katidir veya metadata OCR kaynakli farklilik tasiyor.
- Bazi top document farkliliklari gercek hata degil, golden alias veya beklenen dokuman ipucunun fazla dar olmasindan kaynaklanabilir.
- Fallback beklenen sorular genel olarak iyi durumda; bu alan icin soru bazli patch ihtiyaci yoktur.

## Genel Iyilestirme Onerileri

### A) Query vocabulary / Turkce karakter / es anlamli terim normalizasyonu

Soru terimleri, kaynak basliklari ve article metadata ayni normalizasyon hattindan gecmelidir. Turkce karakter, URL-encoded baslik, ASCII yazim ve sik kullanilan es anlamli terimler evaluation tabanli bir sozlukle izlenebilir.

### B) Metadata title/document alias eslesmesini guclendirme

Golden alias'lar, source inventory ve ChromaDB metadata basliklari karsilastirilmalidir. Bu is runtime patch olmadan once inventory raporu ile dogrulanmalidir.

### C) Article metadata eslesmesini iyilestirme

Madde basliklari OCR nedeniyle parcalanabiliyor veya beklenen baslikla kucuk farklar tasiyabiliyor. Article matching, sadece exact title yerine normalized partial title ve article_no birlikte degerlendirecek sekilde tasarlanabilir.

### D) Relevance filtering threshold ayarlarini evaluation tabanli gozden gecirme

Final source filtering bazi farkli yonerge sorularinda fazla agresif olabilir. Esik degisikligi ancak golden retrieval evaluation metrikleriyle once/sonra karsilastirilmalidir.

### E) Source manifest ve ChromaDB source inventory uyum kontrolu

Beklenen kaynaklarin ChromaDB snapshot'ta olup olmadigi, source_manifest ve runtime inventory arasinda ayri bir kontrolle takip edilmelidir.

### F) OCR/chunking supheli kaynaklarin ayrica isaretlenmesi

Beklenen terimler final chunk icinde gorunmuyorsa kaynak OCR kalitesi, article split sinirlari ve metadata kalitesi incelenmelidir. Snapshot guncellemesi gerekiyorsa bu ayri bir gorev olarak ele alinmalidir.

## Sonuc

Faz 5B sonucunda olusan triage katmani, runtime degisikligi yapmadan hangi genel sistem katmanlarinin iyilestirilecegini gosterir. Siradaki adim, bu kok neden kumelerini tek tek ele alan ve golden metriklerle once/sonra karsilastirilan genel iyilestirme PR'lari olmalidir.
