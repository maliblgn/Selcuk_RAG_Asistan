# Selçuk RAG Asistan Demo Release Readiness Summary

Bu doküman GitHub release veya tag oluşturmaz. Faz 9J kapsamında demo/release öncesi mevcut doğrulanmış durumu özetler.

## Son Doğrulanmış Durum

- Son doğrulanmış commit: Faz 9J sonrası dokümantasyon commit'i
- Önceki runtime doğrulama commit'i: `1e5274d8850ca827e6e880d8bb4e5b86962f4ef1`
- ChromaDB snapshot: 157 source / 3092 document/chunk
- HF runtime: RUNNING
- HTTP status: 200
- Traceback/Streamlit exception: yok

## Sistem Özeti

Selçuk RAG Asistan, Selçuk Üniversitesi resmi yönetmelik, yönerge, PDF ve seçili web kaynakları üzerinde çalışan RAG tabanlı demo asistandır. Sistem:

- normal bilgi sorularında static ChromaDB RAG kullanır,
- kaynak listeleme sorularında Source Discovery Mode'a geçer,
- yemekhane menüsü gibi dinamik bilgilerde Dynamic Dining Menu Reader kullanır,
- kaynakta açık bilgi yoksa veya evidence yetersizse cevap uydurmaz.

## Son Doğrulanmış Metrikler

- Answer grounding: 42 passed / 0 failed
- Full regression runner: 12/12 passed
- Tests: 342 passed / 2 skipped
- `document_hit_at_1`: 0.967741935483871
- `document_hit_at_3`: 1.0
- `article_hit_at_1`: 0.6451612903225806
- `article_hit_at_3`: 0.7419354838709677
- `fallback_accuracy`: 1.0
- `critical_failure_count`: 0

## Canlı Smoke Soruları

| Soru | Beklenen davranış |
| --- | --- |
| `AKTS nedir?` | Normal RAG, kaynaklı kısa tanım |
| `ALES nedir?` | Normal RAG, lisansüstü tanımlar evidence'ı |
| `Ön lisans ve lisans AGNO şartı nedir?` | Normal RAG, not ortalaması/evidence sinyali |
| `GANO ile AGNO aynı şey mi?` | Evidence yoksa eşdeğerlik uydurmaz, temkinli cevap |
| `Staj yönergesi var mı?` | Source discovery, Türkçe karakterli kaynak listesi |
| `Çift anadal şartları nelerdir?` | Normal RAG, Çift Ana Dal Yönergesi evidence'ı |
| `Lisansüstü başvuru şartları nelerdir?` | Normal RAG, kaynaklı ve tekrar azaltılmış cevap |
| `Teknoloji Fakültesi staj kaynakları nelerdir?` | Source discovery, Teknoloji Fakültesi kaynakları |
| `Bugün yemekte ne var?` | Dynamic dining menu; güvenilir veri yoksa fallback |
| `Galatasaray maçı ne zaman?` | Kapsam dışı fallback |

## Bilinen Sınırlılıklar

- Cevap kapsamı mevcut ChromaDB snapshot ile sınırlıdır.
- Yeni kaynaklar ingestion yapılmadan cevap kapsamına girmez.
- Yemekhane menüsü endpoint'e ve parse edilebilir güncel veriye bağlıdır.
- Live LLM QA varsayılan kapalıdır ve provider API key gerektirir.
- Article-level metriklerde geliştirme alanı sürmektedir.
- Sistem resmi belge yerine geçmez; kritik kararlar resmi kaynakla doğrulanmalıdır.

## Güvenlik Durumu

- `.env` commit edilmez.
- API key/secret commit edilmez.
- `data/*.pdf` commit edilmez.
- Local evaluation artifact dosyaları commit edilmez.
- `release_notes_v0.1.0-demo.local.md` local dosyadır ve stage edilmez.
- ChromaDB snapshot bu Faz 9J kapsamında değiştirilmez.

## Release / Tag Durumu

Bu fazda release, tag veya version bump oluşturulmamıştır. Bu doküman yalnız demo/release readiness özetidir.
