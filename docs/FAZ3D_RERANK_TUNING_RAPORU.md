# Faz 3D Rerank Tuning Raporu

Rapor tarihi: 2026-05-04T10:07:35+00:00

## 1. Amaç

Ana ChromaDB'yi bozmadan retrieval başarısını ölçmek. Bu rapor LLM/Groq çağrısı yapmadan, ChromaDB SQLite snapshot'ını okuyarak üretilmiştir.

## 2. Yapılan Tuningler

- Purpose intent: `amacı nedir` soruları Tanımlar yerine `Amaç` başlıklı maddeye yönelmeye çalışır.
- Definition intent sınırlandırıldı; Tanımlar boost'u purpose/deadline/procedure sorularına uygulanmaz.
- Definition intent: `nedir`, `ne demektir`, `nasıl tanımlanır`, `kısaltması hangi sistemin adıdır` gibi kalıplarla yakalanır.
- Acronym detect: AKTS, ALES, DUS, EAB gibi büyük harfli tokenlar çıkarılır.
- `Tanımlar` article_title, `article_no=4`, `{ACRONYM}:` pattern ve title/query token örtüşmesi boost alır.
- Title/query phrase overlap ve content/query phrase overlap özellikle tez önerisi, tez jürisi, doktora yeterlik gibi ifadelerde boost üretir.
- Stopword listesi genişletildi; alan terimleri korunur.

## 3. Genel Metrikler

| metric | baseline_current_index | legal_test_index | delta |
|---|---:|---:|---:|
| document_hit_at_1 | 1.000 | 1.000 | +0.000 |
| document_hit_at_3 | 1.000 | 1.000 | +0.000 |
| document_hit_at_5 | 1.000 | 1.000 | +0.000 |
| article_hit_at_1 | 0.800 | 1.000 | +0.200 |
| article_hit_at_3 | 1.000 | 1.000 | +0.000 |
| article_hit_at_5 | 1.000 | 1.000 | +0.000 |
| expected_terms_hit_at_5 | 0.867 | 0.867 | +0.000 |

## 4. AKTS Özel Karşılaştırma

| alan | baseline | legal_test |
|---|---|---|
| Madde 4 yakalandı mı | True | True |
| Avrupa Kredi Transfer Sistemi yakalandı mı | True | True |
| rank1 | 4 Tanımlar | 4 Tanımlar |
| detected intent | definition | definition |
| acronym_terms | AKTS | AKTS |
| rerank explanation |  | [{'reason': 'definition_intent_title_tanimlar', 'boost': 8.0}, {'reason': 'definition_intent_article_4', 'boost': 5.0}, {'reason': 'acronym_colon_AKTS', 'boost': 10.0}, {'reason': 'acronym_near_definition_phrase_AKTS', 'boost': 3.0}] |

## 5. Sorunlu Soruların Kontrolü
| id | Faz 3C rank1 | Faz 3D rank1 | expected_article_no | article_hit@1 düzeldi mi |
|---|---|---|---:|---:|
| lisansustu_tez_onerisi_savunma_sure | 42 Süre | 45 İkinci tez danışmanının olması durumunda | 45 | True |
| lisansustu_tezli_yuksek_lisans_amac | 4 Tanımlar | 24 Amaç | 24 | True |
| lisansustu_yuksek_lisans_tez_savunma_jurisi | 44 Tez izleme komitesi | 29 Yüksek lisans tezinin sonuçlanması | 29 | True |

## 6. Soru Bazlı Sonuçlar

| id | expected_article_no | article_hit@5 | expected_terms_hit@5 | rank1 article_no | rank1 title |
|---|---:|---:|---:|---:|---|
| lisansustu_akts_tanim | 4 | True | True | 4 | Tanımlar |
| lisansustu_intihal_tanim | 4 | True | False | 4 | Tanımlar |
| lisansustu_butunlesik_doktora_tanim | 4 | True | True | 4 | Tanımlar |
| lisansustu_doktora_yeterlik_esaslar | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_doktora_yeterlik_sure | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_butunlesik_doktora_yeterlik_sure | 43 | True | True | 43 | Doktora yeterlik sınavı |
| lisansustu_doktora_yeterlik_basarisiz | 43 | True | False | 43 | Doktora yeterlik sınavı |
| lisansustu_tez_izleme_komitesi_olusturma | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_tez_izleme_komitesi_uye_sayisi | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_ikinci_tez_danismani_komite | 44 | True | True | 44 | Tez izleme komitesi |
| lisansustu_tez_onerisi_savunma_sure | 45 | True | True | 45 | İkinci tez danışmanının olması durumunda |
| lisansustu_tez_onerisi_rapor_sure | 45 | True | True | 45 | İkinci tez danışmanının olması durumunda |
| lisansustu_tezli_yuksek_lisans_amac | 24 | True | True | 24 | Amaç |
| lisansustu_tezli_yuksek_lisans_ders_kredi | 26 | True | True | 26 | Ders yükü |
| lisansustu_yuksek_lisans_tez_savunma_jurisi | 29 | True | True | 29 | Yüksek lisans tezinin sonuçlanması |

## 6. Sonuç

Metadata-aware rerank başarılıysa sonraki adım bu scoring katmanını rag_engine.py içine opsiyonel ve kontrollü şekilde taşımaktır. Rule-based boostlar fazla agresif olabileceği için production entegrasyonunda feature flag ve ek regression seti kullanılmalıdır.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe evaluation\evaluate_retrieval.py --questions evaluation\golden_questions.json --db-path chroma_db_legal_test --out retrieval_legal_test_rerank_tuned_report.json --markdown-out docs\FAZ3D_RERANK_TUNING_RAPORU.md --top-k 5 --candidate-k 30 --metadata-rerank --baseline retrieval_legal_test_rerank_report.json
```
