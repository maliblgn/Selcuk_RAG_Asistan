# Answer Quality Evaluation Raporu

## Faz 5G Amaci

Faz 5G'nin amaci, retrieval metrikleri oturduktan sonra sinirli bir soru alt kumesinde LLM cevap kalitesini olculebilir hale getirmektir. Bu faz runtime davranisini degistirmez; cevap kalitesi icin ayri bir evaluation harness ekler.

## Neden Retrieval Metriklerinden Sonra Gerekli?

Retrieval evaluation, dogru kaynak ve madde adayinin bulunup bulunmadigini gosterir. Ancak kullaniciya giden nihai cevap icin ek riskler vardir:

- Cevap kaynaga sadik mi?
- Inline citation var mi?
- Model kendi `Kaynaklar` veya URL blogunu uretiyor mu?
- Fallback beklenen sorularda uydurma bilgi veriliyor mu?
- Uzun sayi dizisi, tekrar veya dusuk kaliteli cevap uretiliyor mu?

Bu nedenle Faz 5G, retrieval katmanindan sonra cevap kalitesi icin sinirli ve kontrollu bir olcum katmani ekler.

## Answer Quality Question Subset

`evaluation/answer_quality_questions.json` dosyasinda 14 soru bulunur:

- Kaynakli cevap beklenen akademik/yonerge sorulari
- Fallback beklenen operasyonel/guncel veya kaynak disi sorular
- Hesaplama ve sayi dizisi riski tasiyan sorular

Her kayit `expected_behavior`, `expected_terms`, `forbidden_terms` ve `quality_checks` alanlariyla takip edilir.

## Olculen Metrikler

`evaluation/evaluate_answer_quality.py` su ozet alanlarini uretir:

- `total_questions`
- `evaluated_questions`
- `skipped_questions`
- `citation_present_rate`
- `source_block_leak_count`
- `url_leak_count`
- `fallback_correct_count`
- `fallback_mismatch_count`
- `low_quality_answer_count`
- `long_number_sequence_count`
- `critical_failure_count`

Soru bazinda `quality_status` alanlari:

- `ok`
- `skipped_live_llm`
- `citation_missing`
- `source_block_leak`
- `url_leak`
- `fallback_mismatch`
- `low_quality_answer`
- `expected_terms_miss`
- `live_llm_error`
- `inspect`

## Dry-run ve Live LLM Modlari

Varsayilan mod CI-safe dry-run modudur. Bu modda gercek LLM cagrisi yapilmaz; retrieval ve source panel hazirligi calistirilir, cevap kalitesi ise `skipped_live_llm` olarak raporlanir.

Live LLM modu sadece manuel olarak `--live-llm` ile calistirilir. `GROQ_API_KEY` yoksa script kontrollu hata kodu ile durur. CI'da gercek Groq/OpenAI cagrisi yapilmaz.

## Ilk Dry-run Sonucu

Faz 5G dry-run calistirildi:

- total_questions: 14
- evaluated_questions: 0
- skipped_questions: 14
- quality_status_counts: `skipped_live_llm: 14`
- critical_failure_count: 0

Dry-run amaci live provider'a baglanmadan harness, soru seti, JSON/Markdown raporlama ve retrieval hazirligini dogrulamaktir.

## Live Run Durumu

Bu fazda live LLM run zorunlu tutulmadi. Live run yerel olarak su komutla yapilabilir:

```bash
python evaluation/evaluate_answer_quality.py --questions evaluation/answer_quality_questions.json --out answer_quality_report.local.json --markdown-out answer_quality_summary.local.md --live-llm --limit 10
```

## Sinirlamalar

- Dry-run cevap metni uretmez; cevap kalitesi metrikleri ancak live modda anlam kazanir.
- Live mod provider, rate limit ve model davranisina baglidir.
- Bu faz otomatik karar kapisi degil, gozlem ve kalite takibi altyapisidir.

## Sonraki Oneriler

- Sinirli RAGAS benzeri cevap kalite denemesi yapmak.
- UI/admin kalite panelinde answer quality ozetlerini gostermek.
- Ayni soru setiyle provider/model karsilastirmasi yapmak.
