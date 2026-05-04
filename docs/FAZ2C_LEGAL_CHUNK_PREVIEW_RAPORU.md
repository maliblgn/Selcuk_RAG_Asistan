# Faz 2C Legal Chunk Preview Raporu

Rapor tarihi: 2026-05-04T08:56:17+00:00

## 1. Amaç

Bu rapor mevcut ChromaDB snapshot'ını değiştirmeden legal chunker çıktısını doğrulamak için üretildi. ChromaDB'ye yazma/silme yapılmadı, data_ingestion çalıştırılmadı, web fetch veya PDF indirme yapılmadı.

## 2. Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe legal_chunk_preview.py --source-contains L%C4%B0SANS%C3%9CST%C3%9C --limit-sources 2 --json --out legal_chunk_preview.json --markdown-out docs/FAZ2C_LEGAL_CHUNK_PREVIEW_RAPORU.md
```

## 3. Seçilen Kaynaklar

| # | source | title | original_chunk_count |
|---:|---|---|---:|
| 1 | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf` | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | 59 |
| 2 | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf` | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | 53 |

## 4. Madde Yakalama Özeti

| source | article_count | Madde 4 | Madde 43 | Madde 44 | İlk 10 madde no |
|---|---:|---:|---:|---:|---|
| L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | 59 | True | True | True | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | 59 | True | True | True | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |

## 5. Kritik Madde Önizlemeleri

### L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf

**Madde 4**

- Bulundu: True
- Başlık: Bu Yönetmelikte geçen
- Sayfa: 1 - 2
- Önizleme: MADDE 4 - (1) Bu Yönetmelikte geçen; a) AKTS: Avrupa Kredi Transfer Sistemini, b) ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını, c) Bütünleştirilmiş doktora: Doktora programına lisans derecesi ile başvuru imkânı sağlayan üstün başarılı öğrencilere yönelik, yüksek lisans ve doktorayı birleştiren programı, ç) DUS: Diş Hekimliğinde Uzmanlık Sınavını, d) (Değişik ibare:RG-11/1/2024-32426) Enstitü anabilim dalı (EAB) /anasanat dalı: İlgili enstitü anabilim/anasanat dalını, e) EAB/an...

**Madde 43**

- Bulundu: True
- Başlık: Doktora yeterlik sınavları ile ilgili esaslar şunlardır
- Sayfa: 16 - 16
- Önizleme: MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır: a) Öğrenci derslerini ve seminerini başarı ile tamamladıktan sonra, temel konular ve doktora alanı ile ilgili konularda derinliğe sahip olup olmadığının belirlenmesi amacıyla en geç beşinci yarıyılda, bütünleştirilmiş doktora programında ise en geç yedinci yarıyılda bir yeterlik sınavına tabi tutulur. (Ek cümleler:RG -3/4/2020-31088) Geçerli bir mazereti olmaksızın, belirtilen bu sürelerde yeterlik sınavına girmeyen öğren...

**Madde 44**

- Bulundu: True
- Başlık: Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak
- Sayfa: 16 - 17
- Önizleme: MADDE 44 - (1) Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak ilgili EAB/anasanat dalı kurulunun önerisi ve enstitü yönetim kurulu kararı ile bir ay içi nde tez izleme komitesi oluşturulur. (2) Tez izleme komitesi üç öğretim üyesinden oluşur. Komitede danışmandan başka EAB/anasanat dalı içinden ve dışından birer üye yer alır. İkinci tez danışmanının olması durumunda ikinci tez danışmanı dilerse komite toplantılarına oy hakkı olmaksızın katılabilir. [Bağlam: L%C4%...

### SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf

**Madde 4**

- Bulundu: True
- Başlık: Bu Yönetmelikte geçen
- Sayfa: 1 - 2
- Önizleme: MADDE 4 - (1) Bu Yönetmelikte geçen; a) AKTS: Avrupa Kredi Transfer Sistemini, b) ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını, c) Bütünleştirilmiş doktora: Doktora programına lisans derec esi ile başvuru imkânı sağlayan üstün başarılı öğrencilere yönelik, yüksek lisans ve doktorayı birleştiren programı, ç) DUS: Diş Hekimliğinde Uzmanlık Sınavını, d) EAB/anasanat dalı: İlgili enstitü anabilim/anasanat dalını, e) EAB/anasanat dalı başkanı: İlgili EAB/anasanat dalı başkanını, f)...

**Madde 43**

- Bulundu: True
- Başlık: Doktora yeterlik sınavları ile ilgili esaslar şunlardır
- Sayfa: 14 - 15
- Önizleme: MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır: a) Öğrenci derslerini ve seminerini başarı ile tamamladıktan sonra, temel konular ve doktora alanı ile ilgili konularda derinliğe sahip olup olmadığının belirlenmesi amacıyla en geç beşinci yarıyılda, bütünleştirilmiş doktora programında ise en geç yedinci yarıyılda bir yeterlik sınavına tabi tutulur. (Ek cümleler:RG-3/4/2020-31088) Geçerli bir mazereti olmaksızın, belirtilen bu sürelerde yeterlik sınavına girmeyen öğrenc...

**Madde 44**

- Bulundu: True
- Başlık: Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak ilgili
- Sayfa: 15 - 15
- Önizleme: MADDE 44 - (1) Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak ilgili EAB/anasanat dalı kurulunun önerisi ve enstitü yönetim kurulu kararı ile bir ay içinde tez izleme komitesi oluşturulur. (2) Tez izleme komitesi üç öğret im üyesinden oluşur. Komitede danışmandan başka EAB/anasanat dalı içinden ve dışından birer üye yer alır. İkinci tez danışmanının olması durumunda ikinci tez danışmanı dilerse komite toplantılarına oy hakkı olmaksızın katılabilir. (3) Tez izleme...

## 6. Kalite Notları

- L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf:
  - article_title alanları MADDE satırındaki ilk cümle/girişten üretildi.
  - page_start/page_end `page_metadata` modu ile tahmin edildi.
  - Duplicate madde numarası: 58.
  - Mevcut index chunk sırası, kaynak metni yaklaşık yeniden kurmak için kullanıldı; mevcut chunklar sayfa içinde semantik bölünmüş olabileceğinden bu çıktı dry-run önizleme olarak değerlendirilmelidir.
- SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf:
  - article_title alanları MADDE satırındaki ilk cümle/girişten üretildi.
  - page_start/page_end `page_metadata` modu ile tahmin edildi.
  - Duplicate madde numarası: 57.
  - Mevcut index chunk sırası, kaynak metni yaklaşık yeniden kurmak için kullanıldı; mevcut chunklar sayfa içinde semantik bölünmüş olabileceğinden bu çıktı dry-run önizleme olarak değerlendirilmelidir.

## 7. Sonraki Adım

Preview başarılıysa bir sonraki adım küçük ve kontrollü bir belge üzerinde ingestion önizleme veya retrieval testi yapmaktır. Bu adımda da önce dry-run yaklaşımı korunmalı, ChromaDB yeniden üretimi ayrı onayla ele alınmalıdır.
