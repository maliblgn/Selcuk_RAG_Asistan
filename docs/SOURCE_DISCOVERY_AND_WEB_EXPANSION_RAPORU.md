# Source Discovery ve Web Expansion Raporu

## Faz 8A Amaci

Faz 8A, kullanicinin dogrudan cevap degil indekslenmis kaynak listesi istedigi durumlari ayri bir mod olarak ele alir. Bu fazda yeni ingestion yapilmadi, ChromaDB snapshot degistirilmedi ve provider degistirilmedi.

## Source Discovery Mode Nedir?

Source discovery mode, "X ile ilgili kaynaklar nelerdir?", "hangi belgeler var?", "yonerge var mi?" gibi kaynak listeleme niyetlerini yakalar. Bu mod normal answer generation zincirine girmek yerine mevcut ChromaDB/source metadata uzerinden ilgili kaynaklari listeler.

Bu ayrim gereklidir; cunku kullanici bazen "bu konuda cevap ver" degil, "bu konuda hangi kaynaklar indekslenmis?" diye sorar. Normal RAG modunda kaynakta acik cevap bulunamadiginda fallback dogru olabilir, fakat kaynak kesfi modunda daha faydali davranis ilgili kaynak listesini gostermektir.

## Desteklenen Soru Kaliplari

Genel intent kaliplari:

- `kaynak var mi`
- `kaynaklar nelerdir`
- `hangi kaynaklar var`
- `hangi belgeler var`
- `hangi dokumanlar var`
- `hangi yonergeler var`
- `hakkinda kaynak`
- `ile ilgili kaynak`
- `alakali kaynak`
- `yonerge var mi`
- `dokuman var mi`

Bu kaliplar soru ID'sine veya tekil konuya gore degil, genel intent ve kaynak terimleri uzerinden calisir.

## Source Discovery Nasil Calisir?

1. `is_source_discovery_query()` kaynak listeleme niyetini belirler.
2. `extract_source_discovery_topic()` kullanicinin konu ifadesini ayiklar.
3. `discover_sources()` ChromaDB metadata ve dokuman parcaciklari uzerinden kaynaklari skorlar.
4. Ayni source duplicate olarak dondurulmez.
5. Yeterli skor yoksa `no_match` doner.
6. App tarafinda LLM cagrisi yapmadan kaynak kesfi cevabi uretilir.

Source paneli icin discovery sonucundaki kaynaklar lightweight `Document` objelerine cevrilir. Boylece mevcut UI kaynak paneli bozulmadan kullanilir.

## Web Source Expansion Audit Nedir?

`evaluation/web_source_candidates.json`, ileride eklenebilecek web kaynak adaylarini tutan manifesttir. Bu fazda yalnizca aday manifest dogrulandi; internetten veri cekilmedi ve ingestion calistirilmadi.

Audit komutu:

```bash
python evaluation/audit_web_source_candidates.py --candidates evaluation/web_source_candidates.json --out web_source_candidates_audit.local.json --markdown-out web_source_candidates_audit.local.md
```

Audit; unique id, zorunlu alanlar, priority, freshness ve ingestion recommendation alanlarini kontrol eder.

## Neden Bu Fazda Ingestion Yapilmadi?

Mevcut demo release ChromaDB snapshot'i stabil durumda: 149 kaynak ve 2985 chunk. Yeni kaynak eklemek snapshot degisikligi, test/evaluation karsilastirmasi ve HF deploy dogrulamasi gerektirir. Bu nedenle Faz 8A yalnizca kaynak adaylarini belirledi ve dogruladi.

## Kaynak Adaylari Hakkinda Notlar

- Yemekhane menusu dinamik ve sik degisen veri oldugu icin statik ChromaDB snapshot yerine dynamic reader veya timestamp'li ayrik akis gerektirir.
- Teknoloji Fakultesi yonerge kaynaklari staj, isletmede mesleki egitim ve fakulte surecleri icin yuksek oncelikli static ingestion adayidir.
- Ogrenci duyurulari yuksek freshness gerektirir; gecerlilik tarihi ve timestamp olmadan kalici snapshot'a alinmasi risklidir.

## Sonraki Faz Onerileri

- Faz 8B Web Source Ingestion Plan
- Yemekhane dynamic menu reader
- Teknoloji Fakultesi static source ingestion
- Source discovery UI iyilestirmeleri
- Source discovery evaluation seti
