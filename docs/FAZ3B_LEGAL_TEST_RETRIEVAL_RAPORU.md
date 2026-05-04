# Faz 3B Legal Test Index Retrieval Raporu

Rapor tarihi: 2026-05-04T09:56:13+00:00

## 1. Amaç

Ana ChromaDB'yi bozmadan retrieval başarısını ölçmek. Bu rapor LLM/Groq çağrısı yapmadan, ChromaDB SQLite snapshot'ını okuyarak üretilmiştir.

## 2. Test Index Oluşturma

- Soru sayısı: 15
- Değerlendirilen doküman/chunk sayısı: 116
- Kapsam: Madde 4, 24, 26, 29, 43, 44 ve 45 odaklı Lisansüstü Eğitim ve Öğretim Yönetmeliği soruları.

## 3. Genel Metrikler

| metric | baseline_current_index | legal_test_index | delta |
|---|---:|---:|---:|
| document_hit_at_1 | 0.867 | 1.000 | +0.133 |
| document_hit_at_3 | 1.000 | 1.000 | +0.000 |
| document_hit_at_5 | 1.000 | 1.000 | +0.000 |
| article_hit_at_1 | 0.667 | 0.600 | -0.067 |
| article_hit_at_3 | 0.733 | 0.867 | +0.133 |
| article_hit_at_5 | 0.800 | 0.933 | +0.133 |
| expected_terms_hit_at_5 | 0.733 | 0.800 | +0.067 |

## 4. AKTS Özel Karşılaştırma

| alan | baseline | legal_test |
|---|---|---|
| Madde 4 yakalandı mı | False | False |
| Avrupa Kredi Transfer Sistemi yakalandı mı | False | False |
| rank1 | 9 RESM%C3%8E%20YAZI%C5%9EMALARDA%20UYGULANACAK%20ESAS%20VE%20USULLER%20HAKKINDA%20Y%C3%96NETMEL%C4%B0K_638218311045321312.pdf | 12 Yatay geçiş yoluyla öğrenci kabulü |

## 5. Soru Bazlı Sonuçlar

| id | expected_article_no | article_hit@5 | expected_terms_hit@5 | rank1 article_no | rank1 title |
|---|---:|---:|---:|---:|---|
| lisansustu_akts_tanim | 4 | False | False | 12 | Yatay geçiş yoluyla öğrenci kabulü |
| lisansustu_intihal_tanim | 4 | True | False | 31 | Amaç |
| lisansustu_butunlesik_doktora_tanim | 4 | True | True | 12 | Yatay geçiş yoluyla öğrenci kabulü |
| lisansustu_doktora_yeterlik_esaslar | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_doktora_yeterlik_sure | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_butunlesik_doktora_yeterlik_sure | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_doktora_yeterlik_basarisiz | 43 | True | False | 20 | kez bilimsel hazırlık programı uygulanmaz |
| lisansustu_tez_izleme_komitesi_olusturma | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_tez_izleme_komitesi_uye_sayisi | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_ikinci_tez_danismani_komite | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_tez_onerisi_savunma_sure | 45 | True | True | 42 | Süre |
| lisansustu_tez_onerisi_rapor_sure | 45 | True | True | 45 | İkinci tez danışmanının olması durumunda |
| lisansustu_tezli_yuksek_lisans_amac | 24 | True | True | 24 | Amaç |
| lisansustu_tezli_yuksek_lisans_ders_kredi | 26 | True | True | 26 | Ders yükü |
| lisansustu_yuksek_lisans_tez_savunma_jurisi | 29 | True | True | 44 | Tez izleme komitesi |

## 6. Sonuç

Legal test index article metadata taşıdığı için article hit ölçümü doğrudan metadata üzerinden daha temiz yapılabilir. Ana index korunmuştur; bu sonuç, tam ingestion stratejisine geçmeden önce kontrollü karşılaştırma sağlar.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe evaluation\evaluate_retrieval.py --questions evaluation\golden_questions.json --db-path chroma_db_legal_test --out retrieval_legal_test_report.json --markdown-out docs\FAZ3B_LEGAL_TEST_RETRIEVAL_RAPORU.md --top-k 5 --baseline retrieval_baseline_report.json
```
