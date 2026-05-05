# AKTS Source Binding Hotfix Raporu

Rapor tarihi: 2026-05-05

## 1. Sorun

Faz 4A sonrasinda tez izleme ve doktora yeterlik sorulari duzelmis olsa da `AKTS nedir?` sorusunda kaynak tutarsizligi goruldu:

- Cevap icinde model kendi `Kaynak:` satirini uretebiliyor.
- Kaynak paneli ise retrieved docs sirasina gore farkli bir belge/madde gosterebiliyor.

Bu durum cevap icindeki `[1]` ile paneldeki `[1]` arasinda guven kaybina yol aciyordu.

## 2. LLM Kaynak Uretimi Neden Kapatildi?

RAG uygulamasinda kaynak listesi deterministik olarak retrieved docs uzerinden uretilmeli. LLM'in cevap sonunda `Kaynak:` veya `Kaynaklar:` bolumu yazmasi, retrieved doc sirasi disinda belge adi uydurmasina veya farkli bir dokumani kaynak gibi gostermesine neden olabilir.

Prompt kurali guclendirildi:

```text
Cevabin sonunda Kaynak veya Kaynaklar basligi acma. URL yazma. Kaynak listesini uygulama gosterecek.
```

Ek olarak `strip_model_generated_sources(answer)` helper'i eklendi. Model yine de kaynak blogu uretirse son cevap kaydedilmeden once bu blok kaldiriliyor; metin icindeki inline `[1]`, `[2]` citation'lar korunuyor.

## 3. Kaynak Paneli Tek Otorite

Kaynak paneli yalnizca retrieved docs uzerinden uretiliyor. `format_context(docs)` ve Streamlit kaynak paneli ayni `docs` listesini ayni sirayla kullaniyor.

Panel formati:

```text
[1] Belge adi
Madde 4 - Tanimlar
Sayfa: X
Kaynaga Git
```

Bu sayede context icindeki `[1]` ile kaynak panelindeki `[1]` ayni retrieved doc'a bagli kaliyor.

## 4. AKTS Rerank Duzeltmesi

`retrieval_rerank.py` icinde AKTS/acronym definition sinyalleri guclendirildi:

- Query icinde `AKTS` varsa acronym/definition intent kabul edilir.
- Content icinde `AKTS` exact match boost alir.
- Content icinde `Avrupa Kredi Transfer Sistemi` geciyorsa cok guclu boost alir.
- `article_no=4` ve `article_title=Tanımlar` boost alir.
- Genel AKTS sorularinda Lisansustu Egitim ve Ogretim Yonetmeligi boost alir.
- `staj`, `fen fakültesi`, `çift ana dal` gibi dar kaynaklar genel AKTS sorusunda Lisansustu Yonetmeliginin onune gecmez.
- Kullanici kaynak ozellestirirse, ornegin `Fen Fakultesi staj yonergesinde AKTS nedir?`, ilgili birim kaynagi boost alabilir.

## 5. Preview Sonuclari

LLM cagrisi yapmadan preview calistirildi.

| Soru | Sonuc |
| --- | --- |
| AKTS nedir? | Rank 1: Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 4 - Tanimlar, metadata score 105.0 |
| Selcuk Universitesi lisansustu egitiminde AKTS ne anlama gelir? | Rank 1: Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 4 - Tanimlar, metadata score 109.0 |

Uretilen preview dosyalari:

- `rag_preview_akts_after_source_fix.json`
- `rag_preview_akts_lisansustu_after_source_fix.json`

## 6. Test Sonucu

Komut:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Sonuc:

```text
177 passed, 2 skipped
```

## 7. Degistirilmeyenler

- Yeni ingestion calistirilmadi.
- `chroma_db/` icerigi degistirilmedi.
- `data/*.pdf` dosyalarina dokunulmadi.
- `.env`, secret veya API key dosyasi degistirilmedi.
- `chroma_db_legal_test/` commit kapsaminda degil.
