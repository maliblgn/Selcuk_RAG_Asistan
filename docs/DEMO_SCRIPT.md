# Demo Script

## Demo Öncesi Kontrol

- HF Space runtime `RUNNING` mi?
- HTTP status `200` mü?
- Uygulamada ChromaDB/traceback/Streamlit exception var mı?
- ChromaDB health `157 source / 3092 document` ile uyumlu mu?
- Demo soruları sırayla hazır mı?
- Kaynak paneli ve inline citation davranışı gözlenecek mi?
- Dynamic menu endpoint parse edilemezse menü uydurmadığı gösterilecek mi?

## Demo Akışı

1. Ana sayfa açılır.
2. ChromaDB snapshot ve kalite paneli durumu kısaca anlatılır.
3. Tanım/RAG soruları ile kaynaklı cevap gösterilir.
4. Mevzuat/şart soruları ile madde ve belge dayanağı gösterilir.
5. Source Discovery Mode ile kaynak listeleme davranışı gösterilir.
6. Dynamic Dining Menu Reader ile güncel/dinamik kaynak fallback davranışı gösterilir.
7. Kapsam dışı soru ile no-hallucination fallback gösterilir.
8. AGNO/GANO gibi terminoloji belirsizliği örneğinde temkinli cevap gösterilir.

## Demo Soruları

### A) Tanım / RAG

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `AKTS nedir?` | `rag` | AKTS tanımını kaynaklı ve kısa verir. | Inline citation ve kaynak paneli görünmeli. |
| `ALES nedir?` | `rag` | ALES tanımını lisansüstü tanımlar evidence'ına dayandırır. | Kaynakta olmayan ek bilgi üretmemeli. |

### B) Mevzuat / Şart

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `Ön lisans ve lisans AGNO şartı nedir?` | `rag` | İlgili not ortalaması/evidence sinyaline dayanarak cevap verir. | Kaynak paneli açık kalmalı. |
| `Çift anadal şartları nelerdir?` | `rag` | Çift Ana Dal Yönergesi ve başvuru/kabul/kayıt koşulları evidence'ını kullanır. | Kaynakta açık olmayan şart genişletilmemeli. |
| `Lisansüstü başvuru şartları nelerdir?` | `rag` | Başvuru/ilan/belge teslimi gibi kaynaklı bilgileri tekrar etmeden sunar. | Gereksiz cümle tekrarları olmamalı. |

### C) Source Discovery

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `Staj yönergesi var mı?` | `source_discovery` | İndekslenmiş staj/yönerge kaynaklarını listeler. | Türkçe karakterli, sade sunum olmalı. |
| `Teknoloji Fakültesi staj kaynakları nelerdir?` | `source_discovery` | Teknoloji Fakültesi staj/İME kaynaklarını listeler. | Kaynak uydurmamalı; mevcut snapshot ile sınırlı kalmalı. |

### D) Dynamic Source

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `Bugün yemekte ne var?` | `dynamic_dining_menu` | Güvenilir menü satırı bulunursa menüyü verir; bulunamazsa fallback verir. | Menü uydurulmamalı. |

### E) Güvenli Fallback

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `Galatasaray maçı ne zaman?` | `fallback` | İndekslenmiş kaynaklarda bilgi olmadığını söyler. | Spor fikstürü uydurulmamalı. |

### F) Terminoloji Belirsizliği

| Soru | Beklenen mode | Beklenen davranış | Dikkat |
| --- | --- | --- | --- |
| `GANO ile AGNO aynı şey mi?` | `rag` | Kaynaklarda GANO evidence'ı varsa bunu belirtir; AGNO/eşdeğerlik açık değilse kesin cevap vermez. | Eşdeğerlik kaynakta yoksa uydurulmamalı. |

## Demo Sırasında Söylenecek Kısa Açıklama

Bu uygulama Selçuk Üniversitesi'nin indekslenmiş resmi yönetmelik, yönerge, PDF ve seçili web kaynakları üzerinde çalışan bir RAG asistanıdır. Soru geldiğinde önce `query_router.py` hangi cevap modunun çalışacağını belirler: kaynak keşfi, dinamik kaynak veya normal RAG.

Normal RAG sorularında ilgili kaynak parçaları ChromaDB snapshot içinden alınır, metadata-aware rerank ile sıralanır, ardından model yalnız bu bağlama dayanarak cevap üretir. Son cevap kaynak bloğu temizleme, URL sızıntısı önleme, tekrar azaltma, citation ve güvenli fallback guardrail'lerinden geçer.

Kaynak keşfi sorularında LLM cevabı üretilmez; mevcut indekslenmiş kaynaklar listelenir. Yemekhane menüsü gibi güncel bilgiler statik snapshot'a gömülmez, dinamik reader üzerinden okunur; güvenilir parse yapılamazsa menü uydurulmaz.

## Demo Notları

- Bu sistem resmi belge yerine geçmez.
- Cevaplar mevcut indekslenmiş kaynaklarla sınırlıdır.
- Yeni kaynaklar ingestion yapılmadan cevap kapsamına girmez.
- Dynamic menu endpoint değişirse fallback davranışı korunur.
- Admin kalite paneli read-only çalışır ve shell command çalıştırmaz.
