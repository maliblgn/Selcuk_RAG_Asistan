# Groq Token Budget Hotfix Raporu

## Hata

Canlı sistemde ChromaDB snapshot çalışır hale geldikten sonra kaynak envanteri sorusu 149 kaynak ve 2985 chunk içeren uzun bir cevap üretiyordu. Bu uzun cevap sohbet geçmişine girdikten sonra sonraki normal sorularda Groq isteği büyüyerek şu hataya yol açtı:

```text
HTTP/1.1 413 Payload Too Large
Requested 16741 tokens
Limit 6000 TPM
```

## Sebep

`rewrite_query` ve cevap üretim promptu, önceki sohbet geçmişini çok uzun haliyle Groq'a taşıyabiliyordu. Özellikle kaynak envanteri cevabı çok satırlı olduğu için `chat_history` prompt bütçesini şişiriyordu.

## Neden DB Problemi Değil?

ChromaDB healthcheck `ok` durumundaydı ve kaynak envanteri sorusunda 149 kaynak / 2985 chunk okunabiliyordu. Hata vektör veritabanı erişiminden değil, LLM prompt/token bütçesinin aşılmasından kaynaklandı.

## Yapılan Düzeltmeler

- `MAX_CONTEXT_CHARS` 12000'den 5000'e indirildi.
- `MAX_CHAT_HISTORY_CHARS`, `MAX_REWRITE_HISTORY_CHARS` ve retry limitleri eklendi.
- Uzun metinler için `trim_text_for_prompt` yardımcı fonksiyonu eklendi.
- Kaynak envanteri cevaplarını yakalayan `is_long_inventory_answer` eklendi.
- Sohbet geçmişini temizleyen `sanitize_chat_history` eklendi.
- Bağımsız sorularda rewrite LLM çağrısını atlayan kontrol eklendi.
- Multi-query çağrısı 413/rate limit durumunda `[question]` fallback ile güvenli hale getirildi.
- `stream_answer` 413/rate limit hatasında daha kısa context/history ile bir kez otomatik retry yapacak hale getirildi.
- Source inventory default liste uzunluğu 120 kaynaktan 30 kaynağa indirildi.

## Chat History Filtreleme

Kaynak envanteri cevabı chat history içine tam liste olarak alınmıyor. Bunun yerine şu kısa placeholder kullanılıyor:

```text
[Onceki mesajda veritabani kaynak envanteri listelendi; detaylar prompttan cikarildi.]
```

Streamlit tarafında prompt geçmişi son 3 kullanıcı/asistan çiftiyle sınırlanıyor. Her mesaj en fazla 800 karakter, toplam history ise 2500 karakter seviyesinde tutuluyor.

## Source Inventory Kısaltma

`build_source_inventory_answer_from_db` ve `build_source_inventory_answer` varsayılan olarak en fazla 30 kaynak gösteriyor. Cevap sonunda kalan kaynak sayısı belirtiliyor ve kullanıcı belge türü veya birim adıyla daha dar liste istemeye yönlendiriliyor.

## 413 Fallback / Retry

Yanıt üretimi sırasında Groq 413 veya rate-limit benzeri bir hata alınırsa uygulama raw hata ile düşmek yerine daha kısa bağlamla bir kez tekrar dener. Retry limitleri:

- context: 2500 karakter
- chat history: 800 karakter

Retry de başarısız olursa kullanıcıya daha dar soru sormasını isteyen güvenli mesaj döner.

## Test Sonucu

```bash
python -m pytest tests/ -v
```

Sonuç:

```text
159 passed, 2 skipped
```

## Sonraki Adım

Faz 4A kapsamında metadata-aware rerank production RAG motoruna ayrı ve kontrollü bir değişiklik olarak taşınabilir. Bu hotfix Faz 4A değildir; yalnızca token budget, chat history ve 413 fallback davranışını düzeltir.
