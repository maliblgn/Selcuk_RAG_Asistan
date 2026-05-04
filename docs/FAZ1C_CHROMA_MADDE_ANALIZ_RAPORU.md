# Faz 1C Chroma Madde Analiz Raporu

Rapor tarihi: 2026-05-04T08:41:51+00:00

## 1. Amaç

Bu rapor mevcut ChromaDB snapshot'ını değiştirmeden madde bazlı chunklama ihtiyacını analiz eder. ChromaDB'ye yazma/silme yapılmadı, ingestion çalıştırılmadı, PDF indirilmedi ve web fetch yapılmadı.

## 2. Genel Kapsam

- ChromaDB mevcut mu: True
- Toplam chunk: 659
- Benzersiz kaynak: 45
- MADDE yapısı görülen kaynak: 41
- Tahmini toplam farklı MADDE numarası: 890

Source type dağılımı:

| source_type | chunk sayısı |
|---|---:|
| web_page | 2 |
| web_pdf | 657 |

Doc type dağılımı:

| doc_type | chunk sayısı |
|---|---:|
| akademik_takvim | 35 |
| burs | 1 |
| duyuru | 22 |
| genel | 394 |
| karar | 78 |
| mezuniyet | 14 |
| staj | 4 |
| sınav | 40 |
| yönerge | 2 |
| yönetmelik | 69 |

## 3. En Çok Chunk İçeren Kaynaklar

| # | chunk | doc_type | source_type | title | source |
|---:|---:|---|---|---|---|
| 1 | 59 | genel | web_pdf | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf` |
| 2 | 53 | genel | web_pdf | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf` |
| 3 | 50 | genel | web_pdf | B%C4%B0LG%C4%B0%20ED%C4%B0NME%20HAKKI%20KANUNUNUN%20UYGULANMASINA_638218311039291120.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/B%C4%B0LG%C4%B0%20ED%C4%B0NME%20HAKKI%20KANUNUNUN%20UYGULANMASINA_638218311039291120.pdf` |
| 4 | 36 | genel | web_pdf | Akademik%20Te%C5%9Fvik%20Y%C3%B6netmeli%C4%9Fi_638695962474551552.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/Akademik%20Te%C5%9Fvik%20Y%C3%B6netmeli%C4%9Fi_638695962474551552.pdf` |
| 5 | 29 | yönetmelik | web_pdf | KAMU%20KURUM%20VE%20KURULU%C5%9ELARINDA%20G%C3%96REVDE%20Y%C3%9CKSELME%20VE%20UNVAN%20DE%C4%9E%C4%B0%C5%9E%C4%B0KL%C4%B0%C4%9E%C4%B0%20ESASLARINA%20DA%C4%B0R%20GENEL%20Y%C3%96NETMEL%C4%B0K_638218311042851616.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/KAMU%20KURUM%20VE%20KURULU%C5%9ELARINDA%20G%C3%96REVDE%20Y%C3%9CKSELME%20VE%20UNVAN%20DE%C4%9E%C4%B0%C5%9E%C4%B0KL%C4%B0%C4%9E%C4%B0%20ESASLARINA%20DA%C4%B0R%20GENEL%20Y%C3%96NETMEL%C4%B0K_638218311042851616.pdf` |
| 6 | 26 | sınav | web_pdf | D%C4%B0LEK%20SABANCI%20DEVLET%20KONSERVATUVARI%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638899175173608173.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/D%C4%B0LEK%20SABANCI%20DEVLET%20KONSERVATUVARI%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638899175173608173.pdf` |
| 7 | 26 | genel | web_pdf | f0ec2685-f79b-46c2-92c7-be2f1b8b6bda.pdf | `https://webadmin.selcuk.edu.tr/uploads//pressFiles/42026/f0ec2685-f79b-46c2-92c7-be2f1b8b6bda.pdf` |
| 8 | 24 | genel | web_pdf | %C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638315843142205508.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/%C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638315843142205508.pdf` |
| 9 | 24 | genel | web_pdf | %C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638893979669167204.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/%C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638893979669167204.pdf` |
| 10 | 24 | genel | web_pdf | 87d58e75-737b-4705-9796-e512c76bc572.pdf | `https://webadmin.selcuk.edu.tr/uploads//pressFiles/42026/87d58e75-737b-4705-9796-e512c76bc572.pdf` |
| 11 | 23 | genel | web_pdf | RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf` |
| 12 | 20 | akademik_takvim | web_pdf | 2025-2026%20E%C4%9Fitim-%C3%96%C4%9Fretim%20Y%C4%B1l%C4%B1%20Genel%20Akademik%20Takvimi_638895488876249013.pdf | `https://webadmin.selcuk.edu.tr/uploads/Contents/main/icerik/3252/2025-2026%20E%C4%9Fitim-%C3%96%C4%9Fretim%20Y%C4%B1l%C4%B1%20Genel%20Akademik%20Takvimi_638895488876249013.pdf` |
| 13 | 17 | sınav | web_pdf | D%C4%B0%C5%9E%20HEK%C4%B0ML%C4%B0%C4%9E%C4%B0%20FAK%C3%9CLTES%C4%B0%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638914509492090889.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/D%C4%B0%C5%9E%20HEK%C4%B0ML%C4%B0%C4%9E%C4%B0%20FAK%C3%9CLTES%C4%B0%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638914509492090889.pdf` |
| 14 | 16 | sınav | web_pdf | DILEK-SABANCI-EGT-OGR-SINAV-YONETMELIGI_638218311040514839.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/DILEK-SABANCI-EGT-OGR-SINAV-YONETMELIGI_638218311040514839.pdf` |
| 15 | 15 | genel | web_pdf | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20OTOMOT%C4%B0V%20TEKNOLOJ%C4%B0LER%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEKL%C4%B0%C4%9E%C4%B0_638218311050893258.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20OTOMOT%C4%B0V%20TEKNOLOJ%C4%B0LER%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEKL%C4%B0%C4%9E%C4%B0_638218311050893258.pdf` |
| 16 | 11 | genel | web_pdf | DOGAL-URUNLER_638218311041373728.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/DOGAL-URUNLER_638218311041373728.pdf` |
| 17 | 11 | genel | web_pdf | S-U-ANADOLU-ARKEOLOJISI-SERAMIGI-UYGULAMA-VE-ARASTIRMA-MERKEZI_638218311057088519.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/S-U-ANADOLU-ARKEOLOJISI-SERAMIGI-UYGULAMA-VE-ARASTIRMA-MERKEZI_638218311057088519.pdf` |
| 18 | 10 | yönetmelik | web_pdf | 2809-SAYILI-YUKSEKOGRETIM-KURUMLARI-TESKILATI-KANUNUNUN-EK-55-INCI-MADDESINDE-BELIRTILEN-OZEL-HESABIN-OLUSTURULMASI-KULLANIMI-VE-DENETIMINE-DAIR-YONETMELIK_638218311037386811.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/2809-SAYILI-YUKSEKOGRETIM-KURUMLARI-TESKILATI-KANUNUNUN-EK-55-INCI-MADDESINDE-BELIRTILEN-OZEL-HESABIN-OLUSTURULMASI-KULLANIMI-VE-DENETIMINE-DAIR-YONETMELIK_638218311037386811.pdf` |
| 19 | 10 | genel | web_pdf | KULTUR-SANAT-UYGULAMA-VE-ARASTIRMA-MERKEZI-YONETMELIGI_638218311043276564.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/KULTUR-SANAT-UYGULAMA-VE-ARASTIRMA-MERKEZI-YONETMELIGI_638218311043276564.pdf` |
| 20 | 10 | genel | web_pdf | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20SAVUNMA%20TEKNOLOJ%C4%B0S%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638218311053410501.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20SAVUNMA%20TEKNOLOJ%C4%B0S%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638218311053410501.pdf` |

## 4. MADDE Yapısı Tespiti

- MADDE yapısı görülen kaynak sayısı: 41
- Tahmini toplam farklı MADDE numarası: 890

| # | chunk | tahmini madde | ilk madde numaraları | title | source |
|---:|---:|---:|---|---|---|
| 1 | 59 | 58 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf` |
| 2 | 53 | 58 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf` |
| 3 | 50 | 46 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | B%C4%B0LG%C4%B0%20ED%C4%B0NME%20HAKKI%20KANUNUNUN%20UYGULANMASINA_638218311039291120.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/B%C4%B0LG%C4%B0%20ED%C4%B0NME%20HAKKI%20KANUNUNUN%20UYGULANMASINA_638218311039291120.pdf` |
| 4 | 36 | 13 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | Akademik%20Te%C5%9Fvik%20Y%C3%B6netmeli%C4%9Fi_638695962474551552.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/Akademik%20Te%C5%9Fvik%20Y%C3%B6netmeli%C4%9Fi_638695962474551552.pdf` |
| 5 | 29 | 18 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | KAMU%20KURUM%20VE%20KURULU%C5%9ELARINDA%20G%C3%96REVDE%20Y%C3%9CKSELME%20VE%20UNVAN%20DE%C4%9E%C4%B0%C5%9E%C4%B0KL%C4%B0%C4%9E%C4%B0%20ESASLARINA%20DA%C4%B0R%20GENEL%20Y%C3%96NETMEL%C4%B0K_638218311042851616.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/KAMU%20KURUM%20VE%20KURULU%C5%9ELARINDA%20G%C3%96REVDE%20Y%C3%9CKSELME%20VE%20UNVAN%20DE%C4%9E%C4%B0%C5%9E%C4%B0KL%C4%B0%C4%9E%C4%B0%20ESASLARINA%20DA%C4%B0R%20GENEL%20Y%C3%96NETMEL%C4%B0K_638218311042851616.pdf` |
| 6 | 26 | 27 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | D%C4%B0LEK%20SABANCI%20DEVLET%20KONSERVATUVARI%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638899175173608173.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/D%C4%B0LEK%20SABANCI%20DEVLET%20KONSERVATUVARI%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638899175173608173.pdf` |
| 7 | 26 | 26 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | f0ec2685-f79b-46c2-92c7-be2f1b8b6bda.pdf | `https://webadmin.selcuk.edu.tr/uploads//pressFiles/42026/f0ec2685-f79b-46c2-92c7-be2f1b8b6bda.pdf` |
| 8 | 24 | 28 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | %C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638315843142205508.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/%C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638315843142205508.pdf` |
| 9 | 24 | 28 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | %C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638893979669167204.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/%C3%96n%20Lisans%20ve%20Lisans%20E%C4%9Fitim-%C3%96%C4%9Fretim%20ve%20S%C4%B1nav%20Y%C3%B6netmeli%C4%9Fi_638893979669167204.pdf` |
| 10 | 24 | 25 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | 87d58e75-737b-4705-9796-e512c76bc572.pdf | `https://webadmin.selcuk.edu.tr/uploads//pressFiles/42026/87d58e75-737b-4705-9796-e512c76bc572.pdf` |
| 11 | 23 | 31 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf` |
| 12 | 17 | 25 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | D%C4%B0%C5%9E%20HEK%C4%B0ML%C4%B0%C4%9E%C4%B0%20FAK%C3%9CLTES%C4%B0%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638914509492090889.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/D%C4%B0%C5%9E%20HEK%C4%B0ML%C4%B0%C4%9E%C4%B0%20FAK%C3%9CLTES%C4%B0%20E%C4%9E%C4%B0T%C4%B0M-%C3%96%C4%9ERET%C4%B0M%20VE%20SINAV%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638914509492090889.pdf` |
| 13 | 16 | 27 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | DILEK-SABANCI-EGT-OGR-SINAV-YONETMELIGI_638218311040514839.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/DILEK-SABANCI-EGT-OGR-SINAV-YONETMELIGI_638218311040514839.pdf` |
| 14 | 15 | 21 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20OTOMOT%C4%B0V%20TEKNOLOJ%C4%B0LER%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEKL%C4%B0%C4%9E%C4%B0_638218311050893258.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20OTOMOT%C4%B0V%20TEKNOLOJ%C4%B0LER%C4%B0%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEKL%C4%B0%C4%9E%C4%B0_638218311050893258.pdf` |
| 15 | 11 | 19 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | DOGAL-URUNLER_638218311041373728.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/DOGAL-URUNLER_638218311041373728.pdf` |

## 5. Lisansüstü Yönetmelik Odak Kontrolü

| chunk | tahmini madde | AKTS | Tanımlar | Yeterlik | title | source |
|---:|---:|---:|---:|---:|---|---|
| 59 | 58 | True | True | True | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf` |
| 53 | 58 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf` |

## 6. Sonuç ve Sonraki Adım

Mevcut ChromaDB içinde yönetmelik/yönerge benzeri PDF kaynaklarında `MADDE` yapısı ölçülebiliyor. Ancak mevcut chunklar sayfa veya semantik bölünmüş olabilir; bir madde birden fazla chunk'a dağılabilir veya tek chunk içinde birden fazla madde bulunabilir. Bu nedenle madde bazlı cevap doğruluğu için bir sonraki fazda `legal_chunker.py` tasarlanmalı ve ingestion'a uygulanmadan önce ayrı örnek metinlerle doğrulanmalıdır.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe analysis_chroma_articles.py --json --out chroma_article_analysis.json --markdown-out docs/FAZ1C_CHROMA_MADDE_ANALIZ_RAPORU.md
```
