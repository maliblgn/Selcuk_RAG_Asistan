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

## Otomatik Hugging Face Deploy

- Gelistirme `dev` branch uzerinde yapilir.
- Degisiklikler test edildikten sonra `dev` -> `main` alinir.
- `main` branch'e push/merge oldugunda `.github/workflows/deploy-hf-space.yml` otomatik calisir.
- Workflow Hugging Face Space reposuna temiz deploy commit'i gonderir.
- Buyuk ChromaDB dosyalari workflow icinde Git LFS ile gonderilir.
- `.gitignore` ChromaDB snapshot'ini normal `git add -A` akisinda dislayabildigi icin deploy workflow'u yalniz `chroma_db/` klasorunu bilincli olarak `git add -f chroma_db` ile ekler.
- Workflow `chroma_db/chroma.sqlite3` dosyasinin deploy klasorunde bulundugunu, git index'e eklendigini ve Git LFS tarafindan izlendigini commit oncesi dogrular.
- Gerekli GitHub Actions secret:
  - `HF_TOKEN`
- `HF_TOKEN` Hugging Face write token olmalidir.
- Token repoya veya dosyaya yazilmaz.
- Workflow `workflow_dispatch` ile manuel de calistirilabilir.

## Ingestion kurali

Yeni ingestion sadece acik gorev olarak istenirse calistirilir. Normal uygulama mevcut ChromaDB snapshot ile calisir.
