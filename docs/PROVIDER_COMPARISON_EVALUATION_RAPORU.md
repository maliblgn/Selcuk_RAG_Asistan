# Provider Comparison Evaluation Raporu

## Faz 6A Amaci

Faz 6A, farkli LLM provider/model adaylarini ayni answer quality soru seti uzerinden karsilastirabilecek bir evaluation harness ekler. Bu faz production provider degistirme fazi degildir.

Mevcut hedefler:

- Groq uzerindeki mevcut modeli olcmek.
- Ileride OpenAI veya baska provider adaylarini ayni metriklerle karsilastirabilmek.
- CI'da gercek API cagrisi yapmamak.
- API key yoksa kontrollu skip davranisi saglamak.

## Neden Provider/Model Karsilastirma?

Retrieval, source binding ve answer quality katmanlari olculebilir hale geldikten sonra model secimi de ayni kalite yuzeyiyle izlenmelidir. Farkli modellerin:

- kaynak sadakati,
- inline citation davranisi,
- fallback dogrulugu,
- source block / URL leak riski,
- dusuk kaliteli cevap uretme egilimi

ayni soru setinde gorulebilir olmalidir.

## Config Yapisi

Provider/model adaylari `evaluation/provider_models.json` icinde tutulur.

Ana alanlar:

- `id`: provider/model icin stabil kimlik.
- `provider`: `groq`, `openai` gibi provider ailesi.
- `model`: provider model adi.
- `api_key_env`: okunacak environment secret adi.
- `enabled_by_default`: dry-run ve genel secimde varsayilan aday olup olmadigi.

OpenAI bu fazda opsiyonel config olarak tutulur. `OPENAI_API_KEY` yoksa skip edilir. Production runtime'a OpenAI entegrasyonu eklenmemistir.

## CLI Kullanimi

CI-safe dry-run:

```bash
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md
```

Yerel live Groq denemesi:

```bash
python evaluation/compare_llm_providers.py --config evaluation/provider_models.json --questions evaluation/answer_quality_questions.json --out provider_comparison_report.local.json --markdown-out provider_comparison_summary.local.md --live-llm --provider-id groq_llama_3_1_8b_instant --limit 10
```

## Olculen Metrikler

Provider bazinda su answer quality metrikleri raporlanir:

- `citation_present_rate`
- `source_block_leak_count`
- `url_leak_count`
- `fallback_mismatch_count`
- `low_quality_answer_count`
- `long_number_sequence_count`
- `critical_failure_count`
- `raw_source_block_leak_count`
- `final_source_block_leak_count`
- `raw_url_leak_count`
- `final_url_leak_count`

Raw/final ayrimi korunur. Geriye uyumlu `source_block_leak_count` ve `url_leak_count` final kullanici cevabini temsil eder.

## Dry-Run Sonucu

Dry-run modunda gercek LLM cagrisi yapilmaz. Provider config ve soru seti dogrulanir, provider summary uretilir ve provider status `skipped_disabled` olur. Bu davranis CI icin guvenlidir.

## Live Run Notu

Live run sadece `--live-llm` ile yapilir. API key yoksa ilgili provider `skipped_missing_key` olarak raporlanir ve script tamamen dusmez. API rate limit, timeout veya provider hatalari soru/provider bazinda raporlanir.

## API Key Guvenligi

API key degerleri:

- terminale yazdirilmaz,
- JSON/Markdown raporuna yazilmaz,
- repoya commit edilmez.

Raporlarda yalniz missing environment adi gibi gizli deger icermeyen bilgiler yer alir.

## Production Davranisi

Bu faz production provider'i degistirmez. `app.py` ve runtime RAG akisi degistirilmemistir. Provider comparison yalniz evaluation katmanidir.

## Sonraki Adim

Karsilastirma verisi yeterli hale gelirse sonraki fazlarda:

- provider abstraction,
- runtime model switch,
- UI/admin kalite paneli,
- daha genis live answer quality regression

ayri ve kontrollu isler olarak ele alinabilir.
