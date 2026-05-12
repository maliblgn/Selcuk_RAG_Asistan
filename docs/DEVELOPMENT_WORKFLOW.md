# Development Workflow

## Branch modeli

- `main`: Kararli surum dalidir. Calisan, testlerden gecmis ve deploy edilebilir durumdaki kod burada tutulur.
- `dev`: Aktif gelistirme dalidir. Yeni isler varsayilan olarak burada yapilir.

Bu duzende yeni feature branch acmak varsayilan akisa dahil degildir. Buyuk ve riskli degisiklikler icin once kapsam netlestirilir.

## Calisma akisi

1. `dev` dalini guncelle.
2. Degisikligi `dev` uzerinde yap.
3. Testleri calistir.
4. Yasakli dosyalarin stage edilmedigini kontrol et.
5. `origin/dev` dalina pushla.
6. `main`e alma karari ayrica verilir.

## Test komutu

```bash
python -m pytest tests/ -v
```

Testler gecmeden `main`e alinmaz.

## Yasakli dosyalar

Asagidaki dosyalar commit edilmez:

- `.env`
- API key, token veya secret iceren herhangi bir dosya
- `data/*.pdf`
- `data/manual_pdfs/`
- `chroma_db_legal_test/`
- `custom_urls.txt`
- `selcuk_links.txt`
- lokal healthcheck, preview ve generated report dosyalari

## ChromaDB kurali

`chroma_db/` bu projede runtime snapshot olarak tracked kalir. Silinmez, yeniden uretilmez ve bu tip dokumantasyon/temizlik islerinde degistirilmez.

## Deploy kurali

HF Spaces deploy guncellemesi ayrica yapilir. Normal repo hygiene veya dokumantasyon isleri HF orphan branch islemi gerektirmez.

## Ingestion kurali

Yeni ingestion sadece acik gorev olarak istenirse calistirilir. Normal uygulama mevcut ChromaDB snapshot ile calisir.
