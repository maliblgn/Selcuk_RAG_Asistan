# Dynamic Menu Reader Report

## Faz 8C Amaci

Bu fazda yemekhane menusu gibi gunluk/aylik degisen bilgileri statik ChromaDB snapshot'a eklemeden okuyabilen dar kapsamli bir dynamic reader eklendi.

## Neden ChromaDB Snapshot'a Eklenmedi?

Yemekhane menusu taze ve degisken bir kaynaktir. Statik snapshot icine gomulurse kisa surede bayatlar ve kullaniciya eski bilgi verme riski dogar. Bu nedenle menu bilgisi, RAG corpusundan ayri bir dynamic source olarak okunur.

## Calisma Mantigi

`dynamic_menu_reader.py` asagidaki katmanlari saglar:

- Yemekhane/menu niyetini algilar.
- Resmi yemek menusu aday endpoint'ini dar kapsamli olarak okur.
- HTML tablo veya metin icinden menu satirlarini ayrisitirmeye calisir.
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

## Test ve Evaluation

Eklenen kontroller:

- `tests/test_dynamic_menu_reader.py`
- `evaluation/dynamic_menu_smoke_questions.json`
- `evaluation/evaluate_dynamic_menu.py`

Dry-run evaluation live web fetch yapmadan CI-safe calisir.

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
