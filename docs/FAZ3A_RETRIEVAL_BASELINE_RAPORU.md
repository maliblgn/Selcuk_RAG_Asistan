# Faz 3A Retrieval Baseline Raporu

Rapor tarihi: 2026-05-04T09:16:26+00:00

## 1. Amaç

Mevcut ChromaDB index'i değiştirmeden retrieval başarısını ölçmek. Bu rapor LLM/Groq çağrısı yapmadan, ChromaDB SQLite snapshot'ını read-only okuyarak üretilmiştir.

## 2. Golden Question Set

- Soru sayısı: 15
- Kapsam: Madde 4, 24, 26, 29, 43, 44 ve 45 odaklı Lisansüstü Eğitim ve Öğretim Yönetmeliği soruları.

## 3. Genel Metrikler

| metrik | değer |
|---|---:|
| document_hit_at_1 | 0.867 |
| document_hit_at_3 | 1.000 |
| document_hit_at_5 | 1.000 |
| article_hit_at_1 | 0.667 |
| article_hit_at_3 | 0.733 |
| article_hit_at_5 | 0.800 |
| expected_terms_hit_at_5 | 0.733 |

## 4. Soru Bazlı Sonuçlar

| id | expected_article_no | document_hit@5 | article_hit@5 | expected_terms_hit@5 | rank1 source/title |
|---|---:|---:|---:|---:|---|
| lisansustu_akts_tanim | 4 | True | False | False | RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf |
| lisansustu_intihal_tanim | 4 | True | True | False | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20SA%C4%9ELIK%20UYGULAMA%20VE%20ARA%C5%9ETIRMA%20MERKEZ%C4%B0%20Y%C3%96NETMEL%C4%B0%C4%B0%C4%9E%C4%B0_638218311052921921.pdf |
| lisansustu_butunlesik_doktora_tanim | 4 | True | False | False | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_doktora_yeterlik_esaslar | 43 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_doktora_yeterlik_sure | 43 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_butunlesik_doktora_yeterlik_sure | 43 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_doktora_yeterlik_basarisiz | 43 | True | True | False | L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE%20%C3%96%C4%9ERET%C4%B0M%20Y%C3%96NETMEL%C4%B0%C4%9E%C4%B0_638959464713301934.pdf |
| lisansustu_tez_izleme_komitesi_olusturma | 44 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_tez_izleme_komitesi_uye_sayisi | 44 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_ikinci_tez_danismani_komite | 44 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_tez_onerisi_savunma_sure | 45 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_tez_onerisi_rapor_sure | 45 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_tezli_yuksek_lisans_amac | 24 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_tezli_yuksek_lisans_ders_kredi | 26 | True | True | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |
| lisansustu_yuksek_lisans_tez_savunma_jurisi | 29 | True | False | True | SEL%C3%87UK%20%C3%9CN%C4%B0VERS%C4%B0TES%C4%B0%20L%C4%B0SANS%C3%9CST%C3%9C%20E%C4%9E%C4%B0T%C4%B0M%20VE_638218311048381336.pdf |

## 5. AKTS Özel Kontrol

- Top1 kaynak/title: RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf
- Madde 4 yakalandı mı: False
- `Avrupa Kredi Transfer Sistemi` top-k içinde var mı: False

## 6. Sonuç

Mevcut index eski chunk yapısında olduğu için article metadata her sonuçta yoktur; article hit ölçümü metadata yoksa içerikteki `MADDE` numarası regex'iyle yapılmıştır. Legal chunking sonrası beklenen iyileşme, özellikle article_hit ve beklenen terim isabetlerinin daha istikrarlı hale gelmesidir.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe evaluation\evaluate_retrieval.py --questions evaluation\golden_questions.json --out retrieval_baseline_report.json --markdown-out docs\FAZ3A_RETRIEVAL_BASELINE_RAPORU.md --top-k 5
```
