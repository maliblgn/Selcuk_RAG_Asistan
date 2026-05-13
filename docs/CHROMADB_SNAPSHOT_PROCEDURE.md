# ChromaDB Snapshot Proseduru

## 1. Snapshot Nedir?

`chroma_db/` klasoru bu projenin runtime bilgi tabanidir. Uygulama normal calismada yeni ingestion yapmaz; mevcut ChromaDB snapshot'ini okur ve cevaplari bu kalici indeks uzerinden uretir.

Snapshot, Selcuk Universitesi resmi kaynaklarindan uretilmis dokuman parcaciklarini, metadata alanlarini ve vektor indeks dosyalarini icerir. Hugging Face Spaces deploy akisi bu snapshot'i Git LFS ile Space reposuna tasir.

## 2. Mevcut Snapshot Durumu

Guncel snapshot durumu:

- document_count / chunk count: 2985
- unique_source_count: 149
- ana kaynak tipi: Selcuk Universitesi yonetmelik, yonerge ve resmi PDF dokumanlari
- source_type dagilimi: agirlikli olarak `web_pdf`

Bu snapshot runtime icin gereklidir. `chroma_db/` klasoru olmadan uygulama canli ortamda bilgi tabanini okuyamaz.

## 3. Neden `chroma_db/` Repoda Tutuluyor?

`chroma_db/` repoda bilincli olarak tutulur:

- HF runtime'in hizli acilmasi icin.
- Canli ortamda ingestion calistirmamak icin.
- Robots, izin, OCR ve network sorunlarini runtime disina almak icin.
- Deterministik demo, test ve deploy ortami saglamak icin.
- Ayni Git commit'inin ayni bilgi tabaniyla calismasini saglamak icin.

## 4. Neden `data/*.pdf` Repoya Alinmiyor?

PDF dosyalari runtime icin gerekli degildir. Snapshot, uygulamanin cevap uretmesi icin gereken chunk, metadata ve vektor indeks bilgisini zaten icerir.

`data/*.pdf` dosyalari repoya alinmaz cunku:

- Repo boyutunu gereksiz buyutur.
- Telif, dagitim ve kaynak sahipligi riski olusturabilir.
- Runtime deploy icin gerekli degildir.
- Yeni ingestion gerektiğinde PDF'ler lokal veya kontrollu bir ortamda yeniden elde edilir.

## 5. Healthcheck Komutlari

Temel saglik kontrolu:

```bash
python check_chroma_health.py --db-path chroma_db --json
```

Opsiyonel local cikti dosyasi:

```bash
python check_chroma_health.py --db-path chroma_db --json --out chroma_health_check.local.json
```

`.local.json` healthcheck ciktilari commit edilmez.

Beklenen degerler:

- `status`: `ok`
- `document_count`: `2985`
- `unique_source_count`: `149`
- `collection_readable`: `true`

## 6. Snapshot Guncelleme Ne Zaman Yapilir?

Snapshot guncellemesi normal gelistirme akisinin parcasi degildir. Sadece acik ve gerekceli bir gorev olarak yapilir.

Guncelleme adaylari:

- Yeni resmi kaynak eklendiginde.
- Eksik OCR PDF tamamlandiginda.
- Yanlis chunking tespit edildiginde.
- `source_manifest.json` ile ChromaDB arasinda ciddi tutarsizlik varsa.
- Evaluation veya general smoke sonuclari bir kaynagin eksik oldugunu gosterirse.

## 7. Snapshot Guncelleme Oncesi Kontrol Listesi

Guncelleme baslamadan once:

- Neden guncelleme yapildigi net mi?
- Hangi kaynak eklenecek veya degisecek?
- Kaynagin resmi ve izinli oldugu dogrulandi mi?
- Robots ve permission politikasi uygun mu?
- `data/*.pdf` dosyalari commit disinda kalacak mi?
- Eski snapshot icin backup veya geri donus stratejisi var mi?
- Golden evaluation ve general smoke testleri hazir mi?
- Degisiklik baska refactor veya runtime davranis degisikligiyle karistirilmiyor mu?

## 8. Snapshot Guncelleme Sonrasi Zorunlu Kontroller

Snapshot degistirildikten sonra su kontroller zorunludur:

```bash
python check_chroma_health.py --db-path chroma_db --json
```

```bash
python evaluation/run_general_smoke.py --questions evaluation/general_smoke_questions.json --out general_smoke_report.local.json --markdown-out general_smoke_summary.local.md
```

```bash
python -m pytest tests/ -v
```

Ayrica raporlanmasi gerekenler:

- `document_count` once/sonra degisimi.
- `unique_source_count` once/sonra degisimi.
- Source inventory kontrolu.
- General smoke risk listelerindeki degisim.
- HF deploy sonrasi canli smoke test sonucu.

Local healthcheck ve smoke ciktilari commit edilmez.

## 9. HF Deploy ve Git LFS Notu

`chroma_db/chroma.sqlite3` ve indeks dosyalari buyuk dosyalardir. HF Space reposuna Git LFS ile gonderilir.

GitHub Actions deploy workflow'u `.gitignore` nedeniyle `chroma_db/` klasorunu normal `git add -A` akisi icinde kacirabilir. Bu nedenle workflow temiz HF deploy reposunda snapshot'i bilincli olarak su komutla ekler:

```bash
git add -f chroma_db/
```

Workflow commit oncesi su kontrolleri yapar:

- `chroma_db/` deploy klasorunde var mi?
- `chroma_db/chroma.sqlite3` deploy klasorunde var mi?
- `chroma_db/chroma.sqlite3` git index'e eklendi mi?
- `chroma_db/chroma.sqlite3` Git LFS listesinde gorunuyor mu?
- Birden fazla `chroma_db/` dosyasi LFS tarafindan izleniyor mu?

## 10. Rollback / Geri Donus Mantigi

Snapshot bozulursa once `main` uzerindeki son calisan commit'e donulur. Snapshot guncellemesi tek basina izlenebilir bir commit olmali ve baska buyuk refactorlarla ayni commit'e konmamalidir.

Geri donus ilkeleri:

- ChromaDB degisikligi ayri ve dikkatli commitlenir.
- HF deploy sonrasi canli test basarisizsa yeni snapshot `main` uzerinde tutulmaz.
- Geri donus icin son calisan snapshot commit'i referans alinir.
- Gerekirse snapshot guncellemesi geri alinip tekrar kontrollu ortamda uretilir.

## 11. Yapilmamasi Gerekenler

- Canli HF ortaminda rastgele ingestion calistirma.
- `data/*.pdf` dosyalarini repoya ekleme.
- `.env`, API key veya secret commit etme.
- `chroma_db_legal_test/` commit etme.
- Healthcheck veya local report JSON dosyalarini commit etme.
- Snapshot degisikligini baska buyuk refactor ile ayni commit'e koyma.
- Snapshot guncellemesini gerekcesiz veya testsiz yapma.

## 12. Onerilen Commit Disiplini

Onerilen commit mesajlari:

- `Update ChromaDB snapshot for new official sources`
- `Refresh ChromaDB snapshot after OCR completion`
- `Document ChromaDB snapshot procedure`

Snapshot guncellemesi iceren commit mesajinda kaynak sayisi ve chunk sayisi degisimi PR veya rapor metninde ayrica belirtilmelidir.
