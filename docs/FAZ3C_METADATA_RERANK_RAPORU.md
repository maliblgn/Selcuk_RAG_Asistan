# Faz 3C Metadata-Aware Rerank Raporu

Rapor tarihi: 2026-05-04T10:02:03+00:00

## 1. Amaç

Ana ChromaDB'yi bozmadan retrieval başarısını ölçmek. Bu rapor LLM/Groq çağrısı yapmadan, ChromaDB SQLite snapshot'ını okuyarak üretilmiştir.

## 2. Rerank Kuralları

- Definition intent: `nedir`, `ne demektir`, `nasıl tanımlanır`, `kısaltması hangi sistemin adıdır` gibi kalıplarla yakalanır.
- Acronym detect: AKTS, ALES, DUS, EAB gibi büyük harfli tokenlar çıkarılır.
- `Tanımlar` article_title, `article_no=4`, `{ACRONYM}:` pattern ve title/query token örtüşmesi boost alır.
- Tanım intentinde alakasız bazı başlıklar düşük ceza alır.

## 3. Genel Metrikler

| metric | baseline_current_index | legal_test_index | delta |
|---|---:|---:|---:|
| document_hit_at_1 | 1.000 | 1.000 | +0.000 |
| document_hit_at_3 | 1.000 | 1.000 | +0.000 |
| document_hit_at_5 | 1.000 | 1.000 | +0.000 |
| article_hit_at_1 | 0.600 | 0.800 | +0.200 |
| article_hit_at_3 | 0.867 | 1.000 | +0.133 |
| article_hit_at_5 | 0.933 | 1.000 | +0.067 |
| expected_terms_hit_at_5 | 0.800 | 0.867 | +0.067 |

## 4. AKTS Özel Karşılaştırma

| alan | baseline | legal_test |
|---|---|---|
| Madde 4 yakalandı mı | False | True |
| Avrupa Kredi Transfer Sistemi yakalandı mı | False | True |
| rank1 | 12 Yatay geçiş yoluyla öğrenci kabulü | 4 Tanımlar |
| detected intent | None | definition |
| acronym_terms |  | AKTS |
| rerank explanation |  | [{'reason': 'definition_intent_title_tanimlar', 'boost': 8.0}, {'reason': 'definition_intent_article_4', 'boost': 5.0}, {'reason': 'acronym_colon_AKTS', 'boost': 10.0}, {'reason': 'acronym_near_definition_phrase_AKTS', 'boost': 3.0}] |

## 5. Diğer Tanım Soruları
- lisansustu_intihal_tanim: article_hit@5 True -> True, expected_terms@5 False -> False
- lisansustu_butunlesik_doktora_tanim: article_hit@5 True -> True, expected_terms@5 True -> True

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
| lisansustu_tez_onerisi_savunma_sure | 45 | True | True | 42 | Süre |
| lisansustu_tez_onerisi_rapor_sure | 45 | True | True | 45 | İkinci tez danışmanının olması durumunda |
| lisansustu_tezli_yuksek_lisans_amac | 24 | True | True | 4 | Tanımlar |
| lisansustu_tezli_yuksek_lisans_ders_kredi | 26 | True | True | 26 | Ders yükü |
| lisansustu_yuksek_lisans_tez_savunma_jurisi | 29 | True | True | 44 | Tez izleme komitesi |

## 7. Sonraki Adım

Metadata-aware rerank başarılıysa sonraki adım bu scoring katmanını rag_engine.py içine opsiyonel ve kontrollü şekilde taşımaktır. Rule-based boostlar fazla agresif olabileceği için production entegrasyonunda feature flag ve ek regression seti kullanılmalıdır.

## Çalıştırılan Komut

```powershell
.\venv\Scripts\python.exe evaluation\evaluate_retrieval.py --questions evaluation\golden_questions.json --db-path chroma_db_legal_test --out retrieval_legal_test_rerank_report.json --markdown-out docs\FAZ3C_METADATA_RERANK_RAPORU.md --top-k 5 --candidate-k 30 --metadata-rerank --baseline retrieval_legal_test_report.json
```
