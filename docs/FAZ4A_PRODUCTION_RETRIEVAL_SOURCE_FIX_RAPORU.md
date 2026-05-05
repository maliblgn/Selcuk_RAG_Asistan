# Faz 4A Production Retrieval Source Fix Raporu

Rapor tarihi: 2026-05-05

## 1. Canli Hata

Canli sistemde ChromaDB saglikli olmasina ragmen su soru yanlis negatif cevap uretiyordu:

```text
Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?
```

Canli cevap `Bu bilgi dokumanlarda yer almiyor.` seklindeydi. Oysa bilgi index icinde Lisansustu Egitim ve Ogretim Yonetmeligi, Madde 44 kapsaminda bulunuyor:

```text
Tez izleme komitesi uc ogretim uyesinden olusur.
```

## 2. Neden DB veya Token Problemi Degil?

Loglarda motor basariyla aciliyor, ChromaDB okunuyor ve Hybrid + MultiQuery sonrasi cok sayida aday dokuman bulunuyordu. Sorun index eksikligi degil, dogru aday dokumanin final context icine guvenilir sekilde baglanamamasi ve FlashRank/multi-query akisi icinde alakasiz adaylarin one cikabilmesiydi.

## 3. Query Normalization

`rag_engine.py` icine `normalize_user_question_for_retrieval` eklendi.

Temizlenen girdiler:

- Bastaki `1.`, `2.`, `3)` gibi numaralar.
- Markdown liste isaretleri.
- Bas/son tirnaklar.
- Gereksiz bosluklar.

Bu normalize soru `rewrite_query`, `multi_query`, `retrieve`, `rerank` ve `stream_answer` akisinda kullaniliyor.

## 4. Multi-Query Safe Mode

Yeni env ayarlari:

```env
MULTI_QUERY_ENABLED=true
MULTI_QUERY_LEGAL_SAFE_MODE=true
```

Mevzuat/madde sorularinda kritik terimi kaybeden LLM varyasyonlari filtreleniyor. Ornek olarak `tez izleme komitesi` sorusundan uretilen `tez danismanlik komitesi` veya `tez savunma komitesi` varyasyonlari eleniyor. Orijinal normalize soru her zaman ilk query olarak kaliyor.

## 5. Metadata-Aware Rerank

Evaluation tarafinda dogrulanan metadata-aware rerank mantigi production tarafinda ortak `retrieval_rerank.py` dosyasina tasindi.

Yeni env ayarlari:

```env
METADATA_RERANK_ENABLED=true
METADATA_RERANK_CANDIDATE_K=40
```

Kullanilan sinyaller:

- `article_no`, `article_title`, `title`, `source`, `page_start/page_end`.
- Query/article title token ve phrase overlap.
- `tez izleme komitesi`, `doktora yeterlik`, `AKTS` gibi kritik exact phrase sinyalleri.
- Content icinde cevabi destekleyen ifade.
- Lisansustu yonetmelik kaynak boost'u.

Article metadata eksik olan eski chunklarda, guclu content eslesmelerinde article bilgisi kontrollu sekilde inference metadata olarak ekleniyor. Bu DB icerigini degistirmez; yalnizca runtime retrieved doc metadata'sini guclendirir.

## 6. FlashRank Guvenlik Duzeltmesi

Akis artik once metadata-aware rerank ile aday setini siraliyor, sonra FlashRank'i bu aday seti uzerinde calistiriyor. Metadata acisindan guclu adaylar final top-k icinde korunuyor. Boylece FlashRank alakasiz ama yuksek skor verdigi bir parcayi one alsa bile Madde 44 / Madde 43 gibi guclu mevzuat chunklari context disina dusmuyor.

FlashRank esigi dusuk olsa bile guclu metadata eslesmesi varsa sistem uyari dokumani uretilmiyor.

## 7. Kaynak Gosterme Duzeltmesi

`format_context` artik LLM'e zengin kaynak basligi veriyor:

```text
[1] Kaynak: LISANSUSTU EGITIM VE OGRETIM YONETMELIGI
Madde: 44 - Tez izleme komitesi
Sayfa: 16-17
URL: ...
Icerik:
...
```

Streamlit kaynak paneli de ayni helper ile gercek retrieved docs uzerinden uretiliyor:

- `[1] Belge adi`
- `Madde 44 - Tez izleme komitesi`
- `Sayfa`
- `URL`

Retrieved docs varsa, cevap "bilgi yok" dese bile kaynak paneli bos kalmaz.

## 8. Preview Sonuclari

LLM cagrisi yapmadan dry-run preview calistirildi.

| Soru | Sonuc |
| --- | --- |
| Tez izleme komitesi kac ogretim uyesinden olusur? | Rank 1: Madde 44 - Tez izleme komitesi, metadata score 30.0 |
| Doktora yeterlik sinavlari ile ilgili esaslar nelerdir? | Rank 1: Madde 43 - Doktora yeterlik sinavi, metadata score 17.0 |
| AKTS nedir? | Rank 1: Madde 4 - Tanimlar |

Uretilen preview dosyalari:

- `rag_preview_tez_izleme.json`
- `rag_preview_doktora_yeterlik.json`
- `rag_preview_akts.json`

## 9. Test Sonucu

Komut:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Sonuc:

```text
160 passed, 2 skipped
```

## 10. Degistirilmeyenler

- Yeni ingestion calistirilmadi.
- `chroma_db/` icerigi degistirilmedi.
- `data/*.pdf` dosyalarina dokunulmadi.
- `.env` veya secret/API key dosyasi degistirilmedi.
- `chroma_db_legal_test/` commit kapsaminda degil.
