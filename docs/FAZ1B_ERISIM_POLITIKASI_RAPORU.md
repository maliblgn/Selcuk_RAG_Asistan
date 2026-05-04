# Faz 1B Erişim Politikası Raporu

Rapor tarihi: 2026-05-04T08:36:29+00:00

## 1. Amaç

Bu rapor kritik kaynaklar için robots.txt ve permission durumunu güvenli şekilde raporlar. Preflight modu sayfa HTML'i çekmez, PDF link çıkarmaz, PDF indirmez, ingestion çalıştırmaz ve ChromaDB'ye dokunmaz.

## 2. Varsayılan Güvenli Mod

`AUTHORIZED_SOURCE_MODE=false` iken `requires_permission=true` kaynaklar fetch denemesine alınmaz. `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=false` iken robots.txt engeli aşılmaz. Pasif kaynaklar sadece `--include-inactive` ile raporlama amacıyla değerlendirilir; manifestteki `active=false` değerleri değiştirilmez.

## 3. Kritik Kaynakların Preflight Sonucu

| source_id | active | requires_permission | authorized_source_mode | robots_override | robots_allowed | can_attempt_fetch | blocked_by | message |
|---|---:|---:|---:|---:|---:|---:|---|---|
| central_regulations_listing | false | true | false | false | false | false | requires_permission | Kaynak requires_permission=true ve AUTHORIZED_SOURCE_MODE kapali. |
| central_directives_listing | false | true | false | false | false | false | requires_permission | Kaynak requires_permission=true ve AUTHORIZED_SOURCE_MODE kapali. |

## 4. İzinli Mod Notu

Kritik kaynaklar için kurumsal/yazılı izin varsa izinli mod `.env` üzerinden bilinçli şekilde açılmalıdır: `AUTHORIZED_SOURCE_MODE=true`. robots engelini yetkili modda aşmak gerekiyorsa ayrıca `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=true` gerekir. Bu iki ayar varsayılan olarak kapalı kalmalıdır ve açıkken raporlarda/loglarda görünür olmalıdır.

## 5. Sonraki Teknik Adım

Kaynaklar izinli modda erişilebilir hale getirilirse önce PDF inventory dry-run tekrar çalıştırılmalı, ardından ayrı bir fazda PDF fetch dayanıklılığı ve ingestion öncesi kaynak seçimi ele alınmalıdır.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe discovery_report.py --manifest source_manifest.json --source-id central_regulations_listing --source-id central_directives_listing --include-inactive --access-preflight-only --json --out critical_access_preflight.json
```
