# Selcuk RAG Asistan Release Summary

## 1. Proje Ozeti

Selcuk RAG Asistan, Selcuk Universitesi resmi yonetmelik, yonerge ve PDF dokumanlari uzerinden calisan RAG tabanli bir asistandir. Kullanici sorulari ChromaDB snapshot uzerinden ilgili kaynaklarla eslestirilir, cevaplar inline citation ve kaynak paneliyle sunulur.

Sistem kaynakta acik bilgi bulamazsa guvenli fallback vermeyi hedefler. Ozellikle saat, ucret, gunluk yemek listesi veya bugunku program gibi guncel operasyonel bilgiler corpus icinde yoksa cevap uydurmamasi beklenir.

## 2. Mevcut Canli Mimari

- Streamlit UI
- ChromaDB runtime snapshot
- Local sentence-transformers embedding
- Groq LLM provider
- Metadata-aware retrieval/rerank
- Answer post-processing ve guardrail katmani
- Hugging Face Spaces Docker deploy
- GitHub Actions otomatik HF deploy

## 3. Veri / Bilgi Tabani Durumu

- Unique source: 149
- Chunk/document count: 2985
- ChromaDB snapshot runtime icin repoda korunur.
- `data/*.pdf` repoda tutulmaz.
- Snapshot uretim ve guncelleme proseduru: `docs/CHROMADB_SNAPSHOT_PROCEDURE.md`

ChromaDB snapshot canli ortamda yeni ingestion yapmadan okunur. Snapshot guncellemesi ayri gorev olarak, test ve evaluation kontrolleriyle ele alinmalidir.

## 4. Kalite Durumu

Son bilinen retrieval metrikleri:

- `document_hit_at_1`: 0.903
- `document_hit_at_3`: 0.935
- `article_hit_at_1`: 0.677
- `article_hit_at_3`: 0.774
- `fallback_accuracy`: 1.000

Son bilinen answer quality live sonucu:

- `source_block_leak_count`: 0
- `url_leak_count`: 0
- `critical_failure_count`: 0

Son bilinen provider comparison Groq live sonucu:

- provider: `groq_llama_3_1_8b_instant`
- `critical_failure_count`: 0
- `source_block_leak_count`: 0
- `url_leak_count`: 0
- `fallback_mismatch_count`: 0

## 5. Guardrail / Guvenlik

Uygulanan temel guardrail katmanlari:

- Alakasiz kaynak filtreleme
- Used-source-only kaynak paneli
- Inline citation ve kaynak paneli sira eslestirmesi
- Model-generated `Kaynaklar` / URL bloklarini temizleme
- Dusuk kaliteli cevap ve uzun sayi dizisi tespiti
- Operasyonel/guncel bilgi sorularinda guvenli fallback

Repo guvenligi:

- `.env`, API key ve secret degerleri commit edilmez.
- `data/*.pdf` commit edilmez.
- Local evaluation artifact dosyalari commit edilmez.
- `chroma_db/` runtime snapshot olarak korunur; guncellemesi prosedurludur.

## 6. Admin / Quality Dashboard

Streamlit admin alaninda read-only kalite paneli bulunur.

Panel:

- ChromaDB health bilgisini gosterir.
- Local evaluation artifact ozetlerini okur.
- UI'dan shell command calistirmaz.
- API key/secret gostermez.
- Raw answer preview gostermez.

Detay: `docs/QUALITY_DASHBOARD_RAPORU.md`

## 7. Deploy Durumu

`main` branch'e push/merge oldugunda GitHub Actions otomatik Hugging Face Space deploy workflow'unu calistirir.

Deploy notlari:

- HF Space Docker SDK kullanir.
- App port: 7860
- `HF_TOKEN` GitHub Actions secret olarak tanimli olmalidir.
- ChromaDB snapshot HF deploy commit'ine Git LFS ile tasinir.
- Workflow `chroma_db/chroma.sqlite3` dosyasinin deploy klasorunde, git index'te ve LFS listesinde oldugunu dogrular.

## 8. Bilinen Sinirlamalar

- ChromaDB snapshot guncellemesi manuel/prosedurlu yapilir.
- Live LLM evaluation API key gerektirir.
- Provider comparison production provider degistirmez.
- Article hit metrigi gelistirmeye aciktir.
- Quality dashboard ilk surumde read-only tasarlanmistir.
- Sistem resmi kaynak yerine gecmez; kritik kararlar icin resmi belge kontrol edilmelidir.

## 9. Sonraki Faz Onerileri

- Admin protected evaluation runner
- Scheduled evaluation
- Provider abstraction / runtime model switch
- RAGAS benzeri sinirli degerlendirme
- Demo/pitch sunumu
