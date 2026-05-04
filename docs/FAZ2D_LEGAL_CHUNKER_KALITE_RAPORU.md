# Faz 2D Legal Chunker Kalite Raporu

Rapor tarihi: 2026-05-04T09:10:41+00:00

## 1. Amaç

Bu rapor mevcut ChromaDB snapshot'ını değiştirmeden legal chunker çıktısını doğrulamak için üretildi. ChromaDB'ye yazma/silme yapılmadı, data_ingestion çalıştırılmadı, web fetch veya PDF indirme yapılmadı.

Faz 2C'de görülen başlık, duplicate madde ve bağlam kalıntısı sorunları için kalite iyileştirmeleri ölçüldü.

## 2. Yapılan İyileştirmeler

- `preceding_heading` ile MADDE öncesindeki kısa başlık satırı tercih ediliyor.
- `[Bağlam: ...]`, `[Madde ...]` ve `...[bağlam kısaltıldı]` satırları temizleniyor.
- Duplicate madde numaraları için daha uzun/temsilci içerik korunuyor ve sayfa aralığı birleştiriliyor.

## 3. Test Sonuçları

```text
121 passed, 2 skipped
```

## 4. Preview Karşılaştırması

Çalıştırılan komut:

```powershell
.\venv\Scripts\python.exe legal_chunk_preview.py --source-contains L%C4%B0SANS%C3%9CST%C3%9C  --limit-sources 2 --json --out legal_chunk_preview_after_quality.json --markdown-out docs/FAZ2D_LEGAL_CHUNKER_KALITE_RAPORU.md
```

### Seçilen Kaynaklar

| # | source | title | original_chunk_count |
|---:|---|---|---:|
| 1 | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf` | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | 59 |
| 2 | `https://webadmin.selcuk.edu.tr/uploads//contents/main/icerik/2447/SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf` | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | 53 |

### Duplicate Before/After

| source | before | after | duplicate before | duplicate after | Madde 4 | Madde 43 | Madde 44 | İlk 10 madde no |
|---|---:|---:|---|---|---:|---:|---:|---|
| L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf | 59 | 58 | 58 | Yok | True | True | True | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf | 59 | 58 | 57 | Yok | True | True | True | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |

### Kritik Madde Önizlemeleri

### L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf

**Madde 4**

- Bulundu: True
- Başlık: Tanımlar
- Başlık kaynağı: preceding_heading
- Sayfa: 1 - 2
- Önizleme: MADDE 4 - (1) Bu Yönetmelikte geçen; a) AKTS: Avrupa Kredi Transfer Sistemini, b) ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını, c) Bütünleştirilmiş doktora: Doktora programına lisans derecesi ile başvuru imkânı sağlayan üstün başarılı öğrencilere yönelik, yüksek lisans ve doktorayı birleştiren programı, ç) DUS: Diş Hekimliğinde Uzmanlık Sınavını, d) (Değişik ibare:RG-11/1/2024-32426) Enstitü anabilim dalı (EAB) /anasanat dalı: İlgili enstitü anabilim/anasanat dalını, e) EAB/an...

**Madde 43**

- Bulundu: True
- Başlık: Doktora yeterlik sınavı
- Başlık kaynağı: preceding_heading
- Sayfa: 16 - 16
- Önizleme: MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır: a) Öğrenci derslerini ve seminerini başarı ile tamamladıktan sonra, temel konular ve doktora alanı ile ilgili konularda derinliğe sahip olup olmadığının belirlenmesi amacıyla en geç beşinci yarıyılda, bütünleştirilmiş doktora programında ise en geç yedinci yarıyılda bir yeterlik sınavına tabi tutulur. (Ek cümleler:RG -3/4/2020-31088) Geçerli bir mazereti olmaksızın, belirtilen bu sürelerde yeterlik sınavına girmeyen öğren...

**Madde 44**

- Bulundu: True
- Başlık: Tez izleme komitesi
- Başlık kaynağı: preceding_heading
- Sayfa: 16 - 17
- Önizleme: MADDE 44 - (1) Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak ilgili EAB/anasanat dalı kurulunun önerisi ve enstitü yönetim kurulu kararı ile bir ay içi nde tez izleme komitesi oluşturulur. (2) Tez izleme komitesi üç öğretim üyesinden oluşur. Komitede danışmandan başka EAB/anasanat dalı içinden ve dışından birer üye yer alır. İkinci tez danışmanının olması durumunda ikinci tez danışmanı dilerse komite toplantılarına oy hakkı olmaksızın katılabilir. (3) Tez izleme...

### SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf

**Madde 4**

- Bulundu: True
- Başlık: Tanımlar
- Başlık kaynağı: preceding_heading
- Sayfa: 1 - 2
- Önizleme: MADDE 4 - (1) Bu Yönetmelikte geçen; a) AKTS: Avrupa Kredi Transfer Sistemini, b) ALES: Akademik Personel ve Lisansüstü Eğitimi Giriş Sınavını, c) Bütünleştirilmiş doktora: Doktora programına lisans derec esi ile başvuru imkânı sağlayan üstün başarılı öğrencilere yönelik, yüksek lisans ve doktorayı birleştiren programı, ç) DUS: Diş Hekimliğinde Uzmanlık Sınavını, d) EAB/anasanat dalı: İlgili enstitü anabilim/anasanat dalını, e) EAB/anasanat dalı başkanı: İlgili EAB/anasanat dalı başkanını, f)...

**Madde 43**

- Bulundu: True
- Başlık: Doktora yeterlik sınavı
- Başlık kaynağı: preceding_heading
- Sayfa: 14 - 15
- Önizleme: MADDE 43 - (1) Doktora yeterlik sınavları ile ilgili esaslar şunlardır: a) Öğrenci derslerini ve seminerini başarı ile tamamladıktan sonra, temel konular ve doktora alanı ile ilgili konularda derinliğe sahip olup olmadığının belirlenmesi amacıyla en geç beşinci yarıyılda, bütünleştirilmiş doktora programında ise en geç yedinci yarıyılda bir yeterlik sınavına tabi tutulur. (Ek cümleler:RG-3/4/2020-31088) Geçerli bir mazereti olmaksızın, belirtilen bu sürelerde yeterlik sınavına girmeyen öğrenc...

**Madde 44**

- Bulundu: True
- Başlık: Tez izleme komitesi
- Başlık kaynağı: preceding_heading
- Sayfa: 15 - 15
- Önizleme: MADDE 44 - (1) Yeterlik sınavında başarılı bulunan öğrenci için, danışmanın görüşü alınarak ilgili EAB/anasanat dalı kurulunun önerisi ve enstitü yönetim kurulu kararı ile bir ay içinde tez izleme komitesi oluşturulur. (2) Tez izleme komitesi üç öğret im üyesinden oluşur. Komitede danışmandan başka EAB/anasanat dalı içinden ve dışından birer üye yer alır. İkinci tez danışmanının olması durumunda ikinci tez danışmanı dilerse komite toplantılarına oy hakkı olmaksızın katılabilir. (3) Tez izleme...

## 5. Riskler

- L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf:
  - article_title alanları önceki başlık satırı uygunsa oradan, değilse MADDE satırındaki ilk cümle/girişten üretildi.
  - page_start/page_end `page_metadata` modu ile tahmin edildi.
  - Duplicate madde numarası before/after: 58 / Yok.
  - Bağlam prefix temizliği uygulandı mı: True.
  - Mevcut index chunk sırası, kaynak metni yaklaşık yeniden kurmak için kullanıldı; mevcut chunklar sayfa içinde semantik bölünmüş olabileceğinden bu çıktı dry-run önizleme olarak değerlendirilmelidir.
- SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf:
  - article_title alanları önceki başlık satırı uygunsa oradan, değilse MADDE satırındaki ilk cümle/girişten üretildi.
  - page_start/page_end `page_metadata` modu ile tahmin edildi.
  - Duplicate madde numarası before/after: 57 / Yok.
  - Bağlam prefix temizliği uygulandı mı: True.
  - Mevcut index chunk sırası, kaynak metni yaklaşık yeniden kurmak için kullanıldı; mevcut chunklar sayfa içinde semantik bölünmüş olabileceğinden bu çıktı dry-run önizleme olarak değerlendirilmelidir.

## 6. Sonraki Adım

Preview başarılıysa bir sonraki adım küçük ve kontrollü bir belge üzerinde legal-chunking ingestion dry-run veya retrieval evaluation hazırlığıdır. Bu adımda da önce dry-run yaklaşımı korunmalı, ChromaDB yeniden üretimi ayrı onayla ele alınmalıdır.
