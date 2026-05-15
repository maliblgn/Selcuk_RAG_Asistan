# Answer Quality Leak Triage Raporu

## Faz 5I Amaci

Faz 5I'nin amaci, Faz 5H live LLM evaluation sonucunda gorulen source block ve URL leak bulgusunun production final cevabinda mi, yoksa yalnizca raw model ciktisinda mi olustugunu ayirmaktir.

## Faz 5H Bulgusu

Faz 5H limit 10 live run sonucunda:

- source_block_leak_count: 7
- url_leak_count: 7
- quality_status_counts: `ok: 3`, `source_block_leak: 7`

Bu sonuc ilk bakista production cevabinda kaynak/URL blogu sizintisi var gibi gorunuyordu.

## Raw ve Final Cevap Ayrimi

Production UI akisi raw model cevabini dogrudan gostermez. `app.py` cevabi kullaniciya gostermeden once su post-processing adimlarini uygular:

- `strip_model_generated_sources`
- `ensure_inline_citation`
- `is_low_quality_answer`
- gerekirse `build_safe_fallback`

Faz 5G harness eski halinde leak tespitini `raw_answer or final_answer` uzerinden yaptigi icin raw model ciktisindaki kaynak/URL blogunu final kullanici cevabi gibi sayabiliyordu.

## Evaluation Harness Hizalamasi

`evaluation/evaluate_answer_quality.py` raw ve final alanlarini ayri uretir hale getirildi:

- `raw_answer_text_preview`
- `final_answer_text_preview`
- `raw_source_block_leak`
- `final_source_block_leak`
- `raw_url_leak`
- `final_url_leak`
- `postprocess_removed_source_block`
- `postprocess_removed_url`
- `citation_present_final`
- `quality_status_raw`
- `quality_status_final`

Geriye uyumluluk icin mevcut alanlar final cevabi temsil eder:

- `source_block_leak_count = final_source_block_leak_count`
- `url_leak_count = final_url_leak_count`
- `critical_failure_count = final_critical_failure_count`

## Runtime Fix Durumu

Runtime fix yapilmadi. Production akisi zaten final cevaba kaynak blogu temizleme ve inline citation koruma adimlarini uyguluyor. Bu fazdaki degisiklik evaluation harness hizalamasidir.

## Yeni Metrikler

Faz 5I live limit 10 sonucunda:

- total_questions: 10
- evaluated_questions: 10
- raw_source_block_leak_count: 7
- final_source_block_leak_count: 0
- raw_url_leak_count: 6
- final_url_leak_count: 0
- postprocess_removed_source_block_count: 7
- postprocess_removed_url_count: 6
- source_block_leak_count: 0
- url_leak_count: 0
- raw_critical_failure_count: 7
- final_critical_failure_count: 1
- critical_failure_count: 1
- quality_status_counts: `ok: 9`, `expected_terms_miss: 1`
- quality_status_raw_counts: `ok: 3`, `source_block_leak: 7`

Bu sonuc, Faz 5H'deki leak bulgusunun final kullanici cevabindan degil raw model ciktisindan geldigini gosterir. Production final cevapta source block veya URL leak kalmamistir. Kalan final kritik bulgu `answer_tez_izleme_komitesi` icin `expected_terms_miss` durumudur; bu leak degil, cevap icerigi/terim kapsami inceleme adayidir.

## Sonraki Oneriler

- Final cevapta leak gorulurse runtime guardrail genisletilmeli.
- Raw leak sikligi yuksek kalirsa prompt kurallari ayrica gozden gecirilebilir.
- Answer quality raporu UI/admin kalite panelinde raw/final ayrimiyla gosterilebilir.
