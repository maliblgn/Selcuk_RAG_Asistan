# Dynamic Menu Reader Report

## Faz 8C Amaci

Bu fazda yemekhane menusu gibi gunluk/aylik degisen bilgileri statik ChromaDB snapshot'a eklemeden okuyabilen dar kapsamli bir dynamic reader eklendi.

## Neden ChromaDB Snapshot'a Eklenmedi?

Yemekhane menusu taze ve degisken bir kaynaktir. Statik snapshot icine gomulurse kisa surede bayatlar ve kullaniciya eski bilgi verme riski dogar. Bu nedenle menu bilgisi, RAG corpusundan ayri bir dynamic source olarak okunur.

## Calisma Mantigi

`dynamic_menu_reader.py` asagidaki katmanlari saglar:

- Yemekhane/menu niyetini algilar.
- Resmi yemek menusu aday endpoint'ini dar kapsamli olarak okur.
- HTML tablo, gorunur metin ve script icindeki JSON benzeri yapilardan menu satirlarini ayrisitirmeye calisir.
- Tarihleri mumkun oldugunda `YYYY-MM-DD` formatina normalize eder.
- `bugun` sorgusunda bugunun tarihiyle eslesen menu satirini one alir; bugune ait guvenilir satir yoksa menu uydurmaz.
- Parser sonucu `diagnostics` alaninda http status, content-type, raw length, parse strategy ve parsed item count bilgilerini tasir.
- Endpoint erisilemezse veya parse edilemezse menu uydurmaz.
- Basit bellek cache'i ile tekrar eden istekleri 1 saat boyunca azaltir.

## Desteklenen Soru Kaliplari

- `bugun yemekte ne var`
- `yemekhane menusu`
- `yemek menusu`
- `aylik yemek listesi`
- `bu ay yemekte ne var`
- `ogle yemegi`
- `aksam yemegi`

Asagidaki sorular dynamic menu olarak ele alinmaz:

- `Yemekhane ile ilgili kaynaklar nelerdir?`
- `Yemekhane yonetmeligi var mi?`
- `Yemek bursu yonergesi var mi?`
- `AKTS nedir?`

## Runtime Entegrasyonu

Streamlit chat akisinda oncelik sirasi:

1. Source discovery
2. Dynamic dining menu reader
3. Normal RAG

Bu siralama sayesinde kaynak listeleme sorulari source discovery modunda kalir; yalniz belirgin yemek/menu sorulari dynamic reader'a gider.

## Guvenli Fallback

Endpoint erisilemezse veya icerik guvenilir sekilde ayrisitirilamazsa cevap:

> Yemekhane menusu kaynagina su anda erisemedim veya menu icerigini guvenilir sekilde okuyamadim. Bu nedenle menu icerigi uydurulmadi.

## Faz 8C-1 Parser Stabilizasyonu

Faz 8C-1 kapsaminda parser daha temkinli ve diagnostic odakli hale getirildi:

- `parse_dining_menu_html`: tablo, script JSON ve text stratejilerini sirayla dener.
- `parse_dining_menu_text`: satir bazli menu metinlerini food-hint filtresiyle ayrisitirir.
- `normalize_menu_date`: yaygin `gg.aa.yyyy`, `gg/aa/yyyy` ve `bugun` tarihlerini normalize eder.
- `select_menu_for_query`: bugun sorularinda bugune ait satiri secer; yoksa guvenli fallback'e izin verir.
- `get_dynamic_menu_health`: live fetch yapmadan dynamic source config/health bilgisi dondurur.

Mevcut endpoint bazen sadece portal/login kabugu dondurebilir. Bu durumda `menu`, `yemek` gibi genel kelimeler tek basina yeterli sayilmaz; gercek yemek kalemi sinyali yoksa sonuc `parse_error` olur.

## Live Fetch Debug

Endpoint yapisini incelemek icin local artifact ureten debug komutu eklendi:

```bash
python tools/debug_dynamic_menu_source.py --out dynamic_menu_debug.local.json --markdown-out dynamic_menu_debug.local.md
```

Bu komut HTTP status, content-type, final URL, response length, title, tablo sayisi, candidate line count ve parser diagnostics bilgilerini yazar. Ham HTML commit edilmez ve local debug ciktilari repoya alinmaz.

## Test ve Evaluation

Eklenen kontroller:

- `tests/test_dynamic_menu_reader.py`
- `evaluation/dynamic_menu_smoke_questions.json`
- `evaluation/evaluate_dynamic_menu.py`

Dry-run evaluation live web fetch yapmadan CI-safe calisir.

Opsiyonel live kontrol:

```bash
python evaluation/evaluate_dynamic_menu.py --questions evaluation/dynamic_menu_smoke_questions.json --out dynamic_menu_live.local.json --markdown-out dynamic_menu_live.local.md --live-fetch
```

## Bilinen Sinirlamalar

- Endpoint HTML yapisi degisirse parser guncellenebilir.
- Ilk surum menu karti UI'i sunmaz; metin cevabi uretir.
- Ogle/aksam ayrimi kaynak HTML yapisina baglidir.
- Live fetch opsiyoneldir ve network durumuna bagli olarak unavailable donebilir.

## Sonraki Oneriler

- Gunluk/haftalik/aylik menu ayrimini daha zenginlestirmek
- Ogle/aksam menu secimini UI'da kart olarak gostermek
- Endpoint yapisi degisirse parser adapter'i eklemek
- Quality dashboard'a dynamic source health ozeti eklemek
