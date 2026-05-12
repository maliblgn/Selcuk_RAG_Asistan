# General RAG Guardrails Raporu

## Neden AKTS'e ozel cozum yetmez?

AKTS sorusu daha once dar bir kaynak baglama problemi gibi gorunse de canli sorunlar ayni kok nedene isaret ediyor: retrieval sonucundaki her belge final context ve kaynak paneline tasinabiliyor, model kendi kaynak blogunu uretebiliyor ve cevap kalitesi post-processing ile yeterince denetlenmiyor. Bu nedenle cozum AKTS'e ozel degil, tum 149 kaynak / 2985 chunk icin calisan genel bir RAG guvenlik katmani olarak ele alindi.

## Gorulen genel problemler

- Model cevap sonunda kendi `Kaynaklar` veya URL listesi uretebiliyordu.
- Alakasiz retrieval sonuclari kaynak paneline girebiliyordu.
- Inline `[1]` ile paneldeki `[1]` ayni belgeyi gostermeyebiliyordu.
- Operasyonel/guncel bilgi sorularinda acik destek yokken alakasiz belge paneli kalabiliyordu.
- Dusuk kaliteli cevaplarda uzun sayi dizileri gibi hallucination belirtileri yakalanmiyordu.

## Query type siniflandirmasi

`classify_query_type(question)` eklendi. Soru su siniflardan birine ayriliyor:

- `legal_definition`
- `legal_article`
- `operational_current_info`
- `general_document_question`

Saat, yemekhane, kutuphane, ucret ve tarih gibi operasyonel/guncel sinyaller `operational_current_info` sayiliyor. Bu sinifta acik kaynak destegi yoksa cevap uydurmak yerine guvenli fallback uretiliyor.

## Relevance filtering

`filter_relevant_docs(question, docs)` retrieval sonrasinda calisiyor. Soru terimleri belge basligi, source, madde basligi ve chunk icerigiyle karsilastiriliyor. Genel sinyaller:

- Alan terimi yoksa belge dusuk skorlu kaliyor.
- `kutuphane` sorusunda kutuphane ve saat destegi olmayan belge eleniyor.
- `yemekhane` sorusunda yemekhane destegi olmayan belge kaynak paneline girmiyor.
- `tez izleme komitesi`, `doktora yeterlik`, `AKTS`, `Avrupa Kredi Transfer Sistemi` gibi exact/critical ifadeler yuksek skor aliyor.
- Hesaplama sorularinda formel destek yoksa belge cezalandiriliyor.

Final context yalnizca esigi gecen belgelerden olusuyor. Hic belge gecmezse docs bos kabul ediliyor.

## Used-source-only source panel

`prepare_context_and_sources(question, docs)` tek helper olarak eklendi. Helper hem context'i hem de panel kaynaklarini ayni filtrelenmis doc listesi uzerinden uretir. Streamlit app artik raw retrieval listesini degil `prepared["docs"]` listesini saklar ve panelde sadece bu kullanilan kaynaklar gorunur.

Bilgi-yok fallback'inde ilgili guclu kaynak yoksa panel bos kalir ve UI kisa not gosterir: `Bu cevap icin guvenilir kaynak eslesmesi bulunamadi.`

## Citation binding

Context icindeki `[1]`, `[2]` numaralari `prepare_context_and_sources` icinde uretilir. Source panel ayni siradaki `prepared["docs"]` ile render edilir. Boylece context `[1]` hangi belgeyse panel `[1]` de ayni belge olur.

`ensure_inline_citation(answer, used_sources)` ile kaynak kullanildigi halde cevapta citation yoksa cevap sonuna `[1]` eklenir. Bilgi-yok fallback cevaplarina citation zorlanmaz.

## Source block stripping

`strip_model_generated_sources(answer)` genellestirildi. Temizlenen formatlar:

- `Kaynak:`
- `Kaynaklar:`
- `KAYNAK:`
- `KAYNAKLAR:`
- `--- KAYNAK ---`
- `--- KAYNAKLAR ---`
- `### Kaynaklar`
- `**Kaynaklar**`
- Sondaki URL listeleri
- `[1] https://...`
- `URL: ...`

Metin icindeki inline citation korunur.

## Low-quality answer detection

`is_low_quality_answer(answer)` eklendi. Yakalanan sinyaller:

- 20'den fazla ardisik sayi
- 50'den fazla virgulle ayrilmis sayi
- Tekrarlayan kelime/cumle bloklari
- Cok uzun fakat citation'siz cevap
- Strip sonrasi neredeyse bos cevap

Dusuk kaliteli cevap yakalanirsa `build_safe_fallback(...)` ile guvenli metne dusulur.

## Safe fallback

`build_safe_fallback(question, relevant_docs, query_type)` eklendi.

- Relevant doc yoksa: `Bu bilgi mevcut indekslenmis yonetmelik/yonerge kaynaklarinda guvenilir sekilde bulunamadi.`
- Operational/current info ise: `Bu soru guncel operasyonel bilgi gerektiriyor olabilir. Mevcut yonetmelik/yonerge kaynaklarinda acik ve guvenilir saat bilgisi bulunamadi.`
- Relevant doc var ama cevap low-quality ise: `Bu konuda kaynaklarda acik bir bilgi tespit edemedim. Kaynak panelindeki belgeyi kontrol edebilirsin. [1]`

## Prompt kurallari

Prompt kurallari genellestirildi:

- Kaynakta acikca yer almayan bilgi uydurma.
- Saat, tarih, ucret, hesaplama ve sayi listelerinde baglamda acik ifade yoksa bilmiyorum de.
- Cevap sonunda kaynak basligi veya URL listesi yazma.
- Sadece baglamdaki kaynaklara dayan.
- Uzun sayi araligi/liste uretme.

## Test sonucu

Komut:

```bash
python -m pytest tests/ -v
```

Sonuc:

```text
188 passed, 2 skipped
```

Yeni dosya `tests/test_rag_guardrails.py` su davranislari kapsar:

- Kutuphane sorusunda FTR klinik uygulamalar kaynagi elenir.
- Yemekhane sorusunda kutuphane/FTR/is sagligi gibi alakasiz kaynaklar panelde kalmaz.
- Operational/current info ve relevant doc yoksa safe fallback uretilir.
- Model kaynak blogu temizlenir.
- Inline `[1]` korunur.
- Citation yoksa `[1]` eklenir.
- Context `[1]` ile panel `[1]` ayni doc'a baglanir.
- Uzun sayi listesi low-quality sayilir.
- Normal AKTS cevabi low-quality sayilmaz.
- Bilgi-yok fallback'inde alakasiz source panel gosterilmez.

## Preview sonucu

Komutlar:

```bash
python analysis_rag_retrieval_preview.py --question "AKTS nedir?" --out rag_preview_guardrail_akts.json
python analysis_rag_retrieval_preview.py --question "Selcuk Universitesi kutuphanesinde hangi saatlerde hizmet sunulur?" --out rag_preview_guardrail_kutuphane.json
python analysis_rag_retrieval_preview.py --question "Selcuk Universitesi yemekhane hizmetleri hangi saatlerde sunulur?" --out rag_preview_guardrail_yemekhane.json
python analysis_rag_retrieval_preview.py --question "Selcuk Universitesi'nde ders kredisi nasil hesaplanir?" --out rag_preview_guardrail_ders_kredisi.json
```

Ozet:

- AKTS: raw 10, filtered 10. Top kaynak `Lisansustu Egitim ve Ogretim Yonetmeligi`, Madde 4 `Tanimlar`.
- Kutuphane saatleri: raw 10, filtered 0. Safe fallback uretildi; alakasiz FTR/kutuphane yonergesi panelde kalmadi.
- Yemekhane saatleri: raw 10, filtered 0. Safe fallback uretildi; alakasiz kaynak paneli yok.
- Ders kredisi: raw 10, filtered 2. Formul iceren ders kredisi kaynaklari kaldi; uzun sayi listesi uretilmesi post-processing guardrail ile yakalanacak.

## Degistirilmeyenler

- ChromaDB icerigi degistirilmedi.
- Yeni ingestion calistirilmadi.
- `data/*.pdf` commit kapsaminda degil.
- `.env` veya secret/API key dosyalari degistirilmedi.
- OpenAI entegrasyonu eklenmedi.
- Hugging Face deploy/orphan branch islemi yapilmadi.
