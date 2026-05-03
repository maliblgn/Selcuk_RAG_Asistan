# Web Crawling Policy

Bu proje, Selcuk Universitesi kaynaklarini web uzerinden kullanirken guvenli ve savunulabilir bir tarama politikasi uygular.

## Kurallar

- Yerel PDF yukleme varsayilan veri yolu degildir.
- Otomatik tarama yalnizca izinli domainler ve robots.txt politikasina uygun URL'ler icin calisir.
- robots.txt okunamazsa URL guvenli tarafta bloklanir.
- robots.txt tarafindan engellenen sayfa veya PDF'ler bypass edilmez.
- Kimlik dogrulama, otomatik tarama izni yerine gecmez; kurumsal izin veya robots-allowed alternatif kaynak gerekir.
- Tarama limitleri dusuk tutulur: dusuk derinlik, dusuk sayfa limiti ve istekler arasi bekleme.
- Engellenen kaynaklar raporlanir, fakat bilgi tabanina eklenmez.

## Yetkili Kaynak Modu

Kurumsal veya proje kapsaminda acik izin alinmis kaynaklar icin iki asamali koruma vardir:

- `AUTHORIZED_SOURCE_MODE=true`: Manifestte `requires_permission: true` olarak isaretlenen kaynaklari kapsam icine alir.
- `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=true`: Yazili/kurumsal izin varsa robots engelini loglayarak yetkili modda gecirir.

Bu iki ayar varsayilan olarak kapali tutulur. Acildiginda sistem sessiz davranmaz; loglarda yetkili mod kullanimi gorunur.

## Aktif Kaynak Stratejisi

`source_manifest.json` aktif kaynaklari yonetir. `active: false` olan kaynaklar projede belgelenir ama otomatik islenmez. `requires_permission: true` isaretli kaynaklar icin kurumsal izin veya robots tarafindan izin verilen alternatif URL gerekir.

## Demo ve Degerlendirme

Demo bilgi tabani `curated_web_sources.txt` ile kontrollu sekilde kurulabilir. Bu liste yalnizca robots politikasina uygun oldugu dogrulanan kaynaklari aktif tutmalidir.
