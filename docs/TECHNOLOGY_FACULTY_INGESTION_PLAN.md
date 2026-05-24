# Teknoloji Fakultesi Ingestion Plan

## Amac

Teknoloji Fakultesi ile ilgili kaynak kesfi sorularinda guvenilir kaynak listesi dondurmek ve fakulteye ozel staj, Isletmede Mesleki Egitim (IME), yonerge, SSS ve ogrenci sureci sorularini cevaplayabilecek kaynak kapsamını hazirlamaktir.

## Neden Gerekli?

Mevcut ChromaDB snapshot icinde Teknoloji Fakultesi icin guvenilir eslesme bulunmadi. Source Discovery Mode bu durumda dogru sekilde `no_match` donuyor ve kaynak uydurmuyor.

Faz 8B bu eksigi dogrudan snapshot'a yazmaz. Once resmi kaynak adaylari manifest olarak ayrilir, zorunlu alanlari ve kapsam bayraklari denetlenir. Snapshot guncellemesi ayri bir gorev olarak planlanir.

## Aday Kaynak Turleri

- Yonerge ve yonetmelik sayfalari
- Staj Uygulama Yonergesi
- Isletmede Mesleki Egitim kaynaklari
- SSS sayfasi
- Is akis semalari
- Formlar ve dilekceler
- Fakulte katalogu ve alt kaynak indeksleri

## Manifest

Teknoloji Fakultesi kaynak adaylari su dosyada tutulur:

```bash
evaluation/technology_faculty_sources.json
```

Manifest kayitlari source owner, kategori, source type, priority, freshness, expected topics ve ingestion recommendation alanlarini icerir. Bu alanlar snapshot guncellemesi oncesinde kapsam ve risk ayrimi yapmak icin kullanilir.

## Audit Komutu

```bash
python evaluation/audit_technology_faculty_sources.py --sources evaluation/technology_faculty_sources.json --out technology_faculty_sources_audit.local.json --markdown-out technology_faculty_sources_audit.local.md
```

Bu komut yalnizca manifest dogrular; internetten veri cekmez, ChromaDB'yi degistirmez ve ingestion calistirmaz.

## Ingestion Stratejisi

1. Web/PDF kaynak adaylari resmi Selcuk Universitesi alan adlari uzerinden dogrulanir.
2. PDF ve web page kaynaklari ayri islenir.
3. Dinamik veya duyuru niteligindeki kaynaklar statik snapshot'a karistirilmaz.
4. Snapshot update icin ayri gorev acilir.
5. Snapshot update sirasinda `docs/CHROMADB_SNAPSHOT_PROCEDURE.md` takip edilir.
6. Yeni snapshot sonrasi retrieval evaluation, source discovery smoke, general smoke, answer quality dry-run ve pytest birlikte calistirilir.

## Riskler

- Fakulte sayfalari guncellenebilir veya URL yapisi degisebilir.
- PDF linkleri yeni dosya adlariyla yenilenebilir.
- Bazi belgeler tarama/gorsel PDF olabilir ve OCR kalitesi gerekebilir.
- Bolum bazli staj/IME belgeleri farkli alt URL'lerde bulunabilir.
- SSS ve form sayfalari kismi operasyonel bilgi icerebilir; guncellik notu gerekebilir.

## Kabul Kriterleri

Snapshot update sonrasi beklenen davranis:

- `teknoloji fakultesi ile alakali kaynak var mi` en az 3 guvenilir kaynak dondurmeli.
- `teknoloji fakultesi staj yonergesi var mi` ilgili staj kaynagini dondurmeli.
- `isletmede mesleki egitim kaynaklari nelerdir` IME kaynaklarini dondurmeli.
- Normal RAG cevap davranisi bozulmamali.
- Source discovery sadece belirgin kaynak listeleme niyetiyle devreye girmeli.

## Sonraki Adim

Faz 8C veya ayri bir snapshot update gorevinde bu manifestten secilen resmi kaynaklar icin izin/robots kontrolu, crawl/PDF extraction, chunking, ChromaDB snapshot guncellemesi ve tam evaluation zinciri calistirilabilir.
