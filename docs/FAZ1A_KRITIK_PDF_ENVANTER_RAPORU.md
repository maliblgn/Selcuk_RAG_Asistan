# Faz 1A Kritik PDF Envanter Raporu

Rapor tarihi: 2026-05-04T08:36:35+00:00

## 1. Amaç

Bu rapor PDF indirme, PDF parse etme, ChromaDB'ye yazma veya ingestion amacı taşımaz. Sadece manifestteki kritik liste sayfalarının HTML içeriğinden PDF link envanteri çıkarmak için üretilmiştir.

## 2. Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe discovery_report.py --manifest source_manifest.json --source-id central_regulations_listing --source-id central_directives_listing --pdf-inventory-only --include-inactive --json --out critical_pdf_inventory.json
```

## 3. Kaynak Bazlı Sonuçlar

### central_regulations_listing

- Başlık: Selcuk Universitesi Yonetmelikler Listesi
- URL: `https://selcuk.edu.tr/anasayfa/detay/39873`
- Active: `false`
- Requires permission: `true`
- Fetch sonucu: Başarısız
- Hata: Kaynak requires_permission=true ve AUTHORIZED_SOURCE_MODE kapali.
- Bulunan PDF sayısı: 0

İlk 10 PDF listesi: PDF linki bulunamadı.

### central_directives_listing

- Başlık: Selcuk Universitesi Yonergeler Listesi
- URL: `https://selcuk.edu.tr/anasayfa/detay/39874`
- Active: `false`
- Requires permission: `true`
- Fetch sonucu: Başarısız
- Hata: Kaynak requires_permission=true ve AUTHORIZED_SOURCE_MODE kapali.
- Bulunan PDF sayısı: 0

İlk 10 PDF listesi: PDF linki bulunamadı.

## 4. Toplamlar

- Toplam kaynak: 2
- Başarıyla okunan liste sayfası: 0
- Başarısız liste sayfası: 2
- Toplam PDF linki: 0
- Benzersiz PDF linki: 0

## 5. Risk ve Gözlemler

- PDF linki bulunamadıysa sayfa HTML yapısı beklenenden farklı olabilir.
- Linkler JavaScript ile sonradan yükleniyor olabilir.
- Liste sayfasında PDF linkleri doğrudan `<a href="...pdf">` olarak bulunmuyor olabilir.
- robots.txt, whitelist, SSL veya network engeli liste sayfasının okunmasını engellemiş olabilir.
