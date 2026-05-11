# Hugging Face Spaces Deploy Raporu

## 1. Neden Streamlit Community Cloud'dan geciliyor?

Streamlit Community Cloud ortaminda uygulama mantiksal olarak calissa da canli RAG yukunde kaynak limiti hatalari goruldu:

- `This app has gone over its resource limits`
- `too much memory`
- `/healthz connection reset by peer`
- transformers, torch ve Streamlit watcher kaynakli yogun log/bellek kullanimi

ChromaDB, embedding modeli, BM25/vector hybrid retrieval, metadata-aware rerank ve LLM cevap akisi birlikte calistiginda Community Cloud sinirlari kalici kullanim icin dar kaliyor. Reboot gecici rahatlama saglasa da daha esnek kaynaklara sahip bir ortam gerekiyor.

## 2. Hedef ortam

- Owner: `maliblgn`
- Space name: `selcuk-rag-asistan`
- Beklenen adres: `https://huggingface.co/spaces/maliblgn/selcuk-rag-asistan`
- SDK: Streamlit
- App file: `app.py`

## 3. Gerekli Secrets

- `GROQ_API_KEY`
- `ADMIN_PASSWORD` opsiyonel

Secret veya token dosyaya yazilmayacak, commit edilmeyecek. Hugging Face Space ayarlarindaki Secrets bolumunden girilecek.

## 4. Onerilen Variables

- `FLASHRANK_ENABLED=false`
- `METADATA_RERANK_ENABLED=true`
- `MULTI_QUERY_ENABLED=true`
- `MULTI_QUERY_LEGAL_SAFE_MODE=true`
- `METADATA_RERANK_CANDIDATE_K=25`
- `FINAL_CONTEXT_DOCS=4`
- `MAX_CONTEXT_CHARS=4000`

FlashRank canli/HF ortaminda varsayilan olarak kapali onerilir. Metadata-aware rerank ana siralama gorevini surdurur.

## 5. Deploy adimlari

1. Hugging Face hesabinda New Space olustur.
2. Owner olarak `maliblgn` sec.
3. Space name olarak `selcuk-rag-asistan` gir.
4. SDK olarak Streamlit sec.
5. Space repo'suna bu projeyi pushla.
6. Secrets ve Variables degerlerini Hugging Face Space ayarlarindan gir.
7. Build tamamlandiktan sonra test sorularini calistir.

HF Space olusturulduktan sonra deploy komutlari:

```powershell
git remote add hf https://huggingface.co/spaces/maliblgn/selcuk-rag-asistan
git push hf main
```

Ayrı deploy branch kullanilacaksa:

```powershell
git push hf main:main
```

HF token terminalde kullanici tarafindan girilecek; token veya secret dosyaya yazilmayacak.

## 6. Test sorulari

- AKTS nedir?
- Selcuk Universitesi lisansustu egitiminde AKTS ne anlama gelir?
- Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?
- Selcuk Universitesi'nde doktora yeterlik sinavlari ile ilgili esaslar nelerdir?

## 7. Beklenen davranis

- Kaynaklar panelinde dogru belge, madde, sayfa ve URL gorunur.
- AKTS -> Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 4 - Tanimlar.
- Tez izleme -> Madde 44 - Tez izleme komitesi.
- Doktora yeterlik -> Madde 43 - Doktora yeterlik sinavi.
- Cevap icinde model kaynak listesi yazmaz; uygulama kaynak paneli tek kaynak otoritesidir.

## 8. Notlar

- `chroma_db/` repo snapshot olarak gelir.
- `data/*.pdf` repo icine alinmaz.
- `.env` ve secret/API key commit edilmez.
- `chroma_db_legal_test/` commit edilmez.
- FlashRank canlida kapali onerilir; metadata-aware rerank ana siralama gorevi gorur.
- `requirements.txt` icinde dogrudan nvidia/cuda veya `torchvision` paketi yoktur. Torch/sentence-transformers zinciri embedding sistemi icin korunur.

## 9. Streamlit watcher ayari

`.streamlit/config.toml` icinde watcher kapatildi:

```toml
[server]
fileWatcherType = "none"
headless = true

[browser]
gatherUsageStats = false
```

Bu ayar Streamlit'in transformers/torch paketlerini gereksiz taramasini azaltir ve HF/Streamlit ortaminda log ile bellek yukunu dusurur.

## 10. FlashRank default durumu

`FLASHRANK_ENABLED` varsayilan olarak `false` kabul edilir. Bu durumda FlashRank import edilmez ve modeli yuklenmez. `FLASHRANK_ENABLED=true` verilirse eski davranis opsiyonel olarak calisir. Metadata-aware rerank her durumda aktif kalabilir.

## 11. Test ve preview sonuclari

Bu bolum PR hazirligi sirasinda calistirilan test ve preview sonuclariyla guncellenmistir.

- Test: `python -m pytest tests/ -v` -> `178 passed, 2 skipped`
- `AKTS nedir?` -> Rank 1: Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 4 - Tanimlar, metadata score 105.0
- `Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?` -> Rank 1: Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 44 - Tez izleme komitesi, metadata score 57.6
- `Selcuk Universitesi'nde doktora yeterlik sinavlari ile ilgili esaslar nelerdir?` -> Rank 1: Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 43 - Doktora yeterlik sinavi, metadata score 42.4

## 12. Degisen dosyalar

- `.streamlit/config.toml`
- `docs/HF_SPACES_DEPLOY_RAPORU.md`
- `docs/HF_SPACE_README_TEMPLATE.md`
- `rag_engine.py`
- `tests/test_rag_engine.py`
- `rag_preview_hf_akts.json`
- `rag_preview_hf_tez_izleme.json`
- `rag_preview_hf_doktora_yeterlik.json`

## 13. Degistirilmeyenler

- ChromaDB icerigi yeniden uretilmedi.
- `data/*.pdf` ve `data/manual_pdfs/` commit edilmedi.
- `.env`, secret veya API key commit edilmedi.
- `chroma_db_legal_test/` commit edilmedi.
- Yeni ingestion calistirilmadi.
