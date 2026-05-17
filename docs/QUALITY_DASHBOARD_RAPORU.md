# Quality Dashboard Raporu

## Faz 6B Amaci

Bu fazda Streamlit yonetici alanina read-only bir sistem/kalite paneli eklendi. Panel production RAG cevap davranisini degistirmez; yalniz mevcut ChromaDB saglik bilgisini ve local evaluation artifact ozetlerini gorunur hale getirir.

## Panelin Kapsami

Panel `quality_dashboard.py` uzerinden calisir ve su bilgileri gosterir:

- ChromaDB klasoru ve collection okunabilirlik durumu
- chunk/document sayisi
- unique source sayisi
- retrieval evaluation ozeti
- general smoke ozeti
- answer quality ozeti
- provider comparison ozeti
- terminalde calistirilabilecek guvenli evaluation komutlari

## Read-Only Tasarim

Panel shell command calistirmaz. Ilk surum bilincli olarak read-only tutuldu:

- HF/production ortaminda kazara agir evaluation veya live LLM cagrisi yapilmaz.
- API key/secret gerektiren komutlar UI uzerinden tetiklenmez.
- Local artifact yoksa panel komutu gosterir ve "henuz uretilmedi" mesajiyla devam eder.

## Okunan Local Artifact Dosyalari

Panel su local artifact dosyalarini okur:

- `retrieval_evaluation_report.local.json`
- `general_smoke_report.local.json`
- `answer_quality_report.local.json`
- `provider_comparison_report.local.json`

Bu dosyalar `.gitignore` kapsamindadir ve commit edilmez.

## Gosterilen Metrikler

Retrieval quality:

- `document_hit_at_1`
- `document_hit_at_3`
- `article_hit_at_1`
- `article_hit_at_3`
- `fallback_accuracy`
- `critical_failure_count`

General smoke:

- toplam soru sayisi
- answer/fallback dagilimi
- riskli soru sayilari

Answer quality:

- toplam/evaluated/skipped soru sayilari
- `source_block_leak_count`
- `url_leak_count`
- `fallback_mismatch_count`
- `critical_failure_count`

Provider comparison:

- provider id/model/status
- evaluated soru sayisi
- critical failure sayisi
- source block / URL leak sayilari
- fallback mismatch sayisi

## Guvenlik Notlari

Panel API key, token, secret veya password gostermemek icin yalniz whitelisted summary alanlarini render eder. Raw answer preview alanlari ilk surumde gosterilmez.

`.env`, `data/`, `chroma_db/` ve local report dosyalari commit edilmez.

## Degistirilmeyenler

- Production provider degistirilmedi.
- Retrieval/rerank scoring degistirilmedi.
- ChromaDB icerigi degistirilmedi.
- Yeni ingestion calistirilmadi.
- RAG cevap akisi degistirilmedi.

## Sonraki Oneriler

- Admin protected command runner
- Scheduled evaluation
- Provider comparison grafik/tablolarinin zenginlestirilmesi
- HF runtime status bilgisinin daha ayrintili gosterimi
