# System Architecture Audit Report

## Amac

Bu rapor, Faz 9A kapsaminda Selcuk RAG Asistan'in mevcut mimarisini refactor oncesi analiz eder. Bu fazda runtime davranisi, ChromaDB snapshot, ingestion akisi, provider secimi veya RAG scoring degistirilmedi.

## Mevcut Sistem Ozeti

Sistem artik birden fazla cevap modu ve kalite katmani iceriyor:

- Static ChromaDB RAG: resmi yonetmelik, yonerge, PDF ve web kaynaklari uzerinden retrieval/rerank/LLM answer akisi.
- Source Discovery Mode: kullanici kaynak listesi istediginde LLM'e gitmeden indekslenmis kaynaklari listeler.
- Technology Faculty snapshot expansion: 8 Teknoloji Fakultesi kaynagi ChromaDB snapshot'a alinmis durumda.
- Dynamic Dining Menu Reader: yemekhane menusu gibi taze veriyi statik snapshot'a gommeden dar kapsamli dynamic source olarak okur.
- Quality dashboard: local evaluation artifact ozetlerini ve sistem health bilgisini read-only gosterir.
- Evaluation/audit sistemi: retrieval, triage, article metadata, source inventory alias, answer quality, provider comparison, source discovery, dynamic menu ve source candidate audit komutlari.

Son bilinen runtime snapshot: 157 source / 3092 chunk. Retrieval metrikleri document seviyesinde guclu, article seviyesinde ise iyilestirme alani var.

## Mevcut Query Flow

Streamlit chat akisi `app.py` icinde su sirayla ilerliyor:

1. Kullanici mesaji session state'e eklenir.
2. Kaynak envanteri/source inventory hafif cevap kontrolu yapilir.
3. Source discovery intent kontrolu yapilir.
4. Dynamic dining menu intent kontrolu yapilir.
5. Normal RAG motoru baslatilir.
6. Takip sorusu rewrite edilir.
7. Retrieval ve relevance/source filtering uygulanir.
8. LLM cevabi stream edilir.
9. Post-processing guardrail'leri uygulanir.
10. Kaynak paneli ve follow-up onerileri session state'e yazilir.

Source discovery su anda dynamic dining menu'den once calisiyor. Bu iyi bir varsayim: `yemekhane ile ilgili kaynaklar nelerdir` gibi sorular menu reader'a degil kaynak kesfine gider. `bugun yemekte ne var` ise source discovery sayilmaz ve dynamic reader'a gider. `AKTS nedir` normal RAG modunda kalir.

Akis calisiyor, ancak routing kararinin tamamlanmis bir query router yerine UI dosyasi icinde yapilmasi app.py'yi buyutuyor.

## Guclu Taraflar

- RAG runtime davranisi test ve evaluation zinciriyle olculebilir hale geldi.
- Source discovery ve dynamic menu gibi LLM disi cevap modlari, belirgin intent ile sinirli tutuldu.
- ChromaDB snapshot update proseduru ve triage dokumantasyonu mevcut.
- Dynamic menu reader menuyu uydurmadan fallback verecek sekilde tasarlandi.
- Quality dashboard read-only ve secret gostermeyen sekilde kurgulandi.
- Local artifact ignore kapsami genisledi.
- main/dev workflow ve HF deploy akisi belgeli.

## Karmasiklasan/Kirlenen Alanlar

- `app.py` 900+ satir ve UI disinda routing, dynamic answer, RAG orchestration ve error handling is mantigi da tasiyor.
- `rag_engine.py` 1100+ satir ve retrieval, LLM, source formatting, guardrail, inventory, dynamic-doc temp db gibi cok sayida sorumlulugu birlestiriyor.
- Dynamic source mimarisi henuz tekil `dynamic_menu_reader.py` dosyasi uzerinden ilerliyor; yeni dynamic kaynaklar eklenirse ortak interface ihtiyaci artacak.
- Evaluation komutlari cok sayida ve tekrarli; hangi durumda hangi zincirin calistirilacagi dokumanda var ama tek komutlu runner yok.
- ChromaDB local modified problemi devam ediyor; read-only sanilan bazi ChromaDB acilislarinin sqlite dosyasini touched/modified gostermesi muhtemel.

## app.py Sorumluluk Analizi

`app.py` su alanlari birlikte tasiyor:

- Streamlit layout, CSS, sidebar ve chat UI.
- Admin/quality dashboard entegrasyonu.
- Uploaded/dynamic docs session state akisi.
- Source inventory, source discovery ve dynamic menu routing.
- RAG motoru cache'i, rewrite, retrieval, answer streaming, source panel, follow-up onerileri.
- Runtime error ve ChromaDB unavailable fallback mesajlari.

Bu durum canli akisin tek dosyada gorulebilmesini kolaylastiriyor, fakat yeni cevap modu eklendikce dosya degisikligi riski artiyor. Ilk refactor icin `app.py` icindeki routing ve assistant response orchestration bolumu ayri bir servis fonksiyonuna alinabilir.

## Routing / Intent Yonetimi Analizi

Mevcut routing dagilimi:

- `source_discovery.py`: source discovery intent ve source matching.
- `dynamic_menu_reader.py`: dining menu intent ve dynamic parse.
- `app.py`: bu intent fonksiyonlarini hangi sirayla calistiracagina karar verir.
- `rag_engine.py`: normal RAG ve source inventory cevaplari.

`query_router.py` veya `routing/query_router.py` ihtiyaci belirgin. Ancak ilk adim buyuk refactor olmamali. Once mevcut sirayi koruyan kucuk, testli bir route descriptor yapisi onerilir:

```text
route_query(query) -> {
  "mode": "source_discovery" | "dynamic_dining_menu" | "rag",
  "reason": "...",
}
```

Bu modul app.py'nin karar karmasasini azaltir; source discovery ve dining menu fonksiyonlarini yeniden yazmadan kullanir. Siralama ve niyet testleri burada toplanabilir.

## Dynamic Source Mimarisi Analizi

`dynamic_menu_reader.py` dar kapsamli ve guvenli bir cozum. Fakat announcement/calendar/library gibi yeni dynamic source ihtimallerinde her kaynak icin ayri intent/fetch/format/doc adapter yazmak daginiklasabilir.

Onerilen gelecek klasor yapisi:

```text
dynamic_sources/
  base.py
  dining_menu.py
  registry.py
  health.py
```

Basit interface:

```text
DynamicSourceReader
  id
  is_query(query)
  fetch()
  format_response(data, query)
  to_documents(data)
  health()
```

Bu refactor icin acele edilmemeli. Ikinci dynamic source eklenene kadar dining menu modulunun calisan yapisi korunabilir; ancak query router ile birlikte registry hazirligi yararli olur.

## ChromaDB Local Modified Analizi

Repo durumunda sikca `chroma_db/chroma.sqlite3` modified goruluyor. Olasiliklar:

- `langchain_chroma.Chroma(persist_directory=...)` collection acarken sqlite metadata dosyasina write-ahead veya migration benzeri kucuk yazimlar yapabiliyor.
- `check_chroma_health.py`, `source_discovery.py`, `rag_engine.py` ve bazi evaluation scriptleri ChromaDB'yi client uzerinden aciyor; bu okumalar read-only sqlite modunda degil.
- `evaluate_retrieval.py` gibi bazi scriptler sqlite'i `mode=ro` ile okuyor; bunlar daha guvenli.
- Tests ve local app calistirmalari ayni tracked snapshot'i kullandigi icin local dev calismalari working tree'yi kirletebiliyor.

Riskli olmayan cozum onerileri:

1. Evaluation ve smoke komutlari icin varsayilan olarak temp copy ChromaDB kullanimi.
2. Read-only source inventory icin Chroma client yerine sqlite `mode=ro` helper kullanimi.
3. `CHROMA_READONLY_COPY=1` gibi local dev env flag'i.
4. Snapshot update disindaki komutlarda tracked `chroma_db/` yerine `.local_chroma_runtime/` temp kopya.
5. Workflow dokumanina stash stratejisi korunarak kisa "local Chroma dirty" proseduru eklenmesi.

Bu fazda ChromaDB davranisi degistirilmedi.

## Evaluation Sistemi Analizi

Evaluation/audit alt sistemi buyudu. Ana komut gruplari:

- Retrieval: `evaluate_retrieval.py`, `triage_retrieval_failures.py`
- Metadata/audit: `audit_article_metadata.py`, `audit_source_inventory_aliases.py`
- Smoke: `run_general_smoke.py`
- Answer quality: `evaluate_answer_quality.py`
- Provider comparison: `compare_llm_providers.py`
- Source discovery: `evaluate_source_discovery.py`
- Dynamic menu: `evaluate_dynamic_menu.py`
- Web/source planning: `audit_web_source_candidates.py`, `audit_technology_faculty_sources.py`

Tek komutlu regression runner faydali olur. Onerilen profiller:

- `fast`: syntax + dynamic menu dry-run + source discovery + pytest targeted veya full pytest.
- `full`: fast + retrieval + general smoke + answer quality dry-run + provider comparison dry-run.
- `snapshot-update`: full + source inventory alias audit + article metadata audit + source discovery smoke.
- `dynamic-source`: dynamic source debug + dynamic source evaluation + source discovery + general smoke.

Onerilen dosya: `evaluation/run_regression_suite.py`.

Local artifact ignore kurallari genel olarak yeterli; yeni komut eklendikce `.local.json` / `.local.md` kaliplari merkezi olarak standardize edilebilir.

## Retrieval Kalite Borclari

Bilinen durum:

- `document_hit_at_1`: 0.903 civari
- `document_hit_at_3`: 0.935 civari
- `fallback_accuracy`: 1.000
- `article_hit_at_1`: 0.645 civari
- `article_hit_at_3`: 0.710 civari
- `critical_failure_count`: 2

Faz 8B-2A triage sonucu critical failure sorulari:

- `golden_ales_definition`
- `golden_onlisans_lisans_agno`

Teknoloji Fakultesi kaynaklari bu iki kritik sorunun top filtered sonuclarina girmiyor. Bu nedenle bilinen risk Teknoloji ingestion gürültüsü degil, article-level document discrimination / rerank / metadata matching borcudur.

Bu fazda runtime fix yapilmadi. Onerilen ayri faz: Article-level retrieval stabilization.

## Risk Matrisi

### P0: Canli sistemi bozabilecek riskler

- `app.py` icinde routing ve UI'nin ayni yerde buyumesi, yeni mod eklerken normal RAG akisini bozma riski.
- Tracked ChromaDB snapshot'in local komutlarla modified hale gelmesi ve yanlislikla stage edilmesi.
- Snapshot update sirasinda dynamic/fresh kaynaklarin statik ChromaDB'ye karismasi.

### P1: Gelistirme hizini dusuren teknik borclar

- Query routing kararlarinin app.py icinde daginik kalmasi.
- Dynamic source reader'lar icin ortak interface olmamasi.
- Evaluation komutlarinin tek runner/profil altinda toplanmamis olmasi.
- `rag_engine.py` icinde retrieval, prompt, guardrail, source inventory ve temp dynamic docs islevlerinin birikmesi.

### P2: Kalite/metrik borclari

- Article hit metriklerinin document hit'e gore dusuk kalmasi.
- `critical_failure_count: 2` durumunun article-level stabilization gerektirmesi.
- Dynamic menu endpoint parse basarisinin kaynagin HTML yapisina bagimli olmasi.
- Provider comparison'in henuz production provider karari icin yeterli coklu provider verisi uretmemesi.

### P3: Dokumantasyon/sunum borclari

- DEVELOPMENT_WORKFLOW fazlar ilerledikce uzadi; hizli karar tablosu eksik.
- Evaluation komutlari birden fazla dokumanda tekrar ediyor.
- Demo/release dokumanlari iyi durumda ancak dynamic source ve query router mimarisi yeni fazlarla guncellenmeli.

## Onerilen Refactor Fazlari

1. **Faz 9B - Query Router Extraction**
   - `query_router.py` ekle.
   - Source discovery, dynamic menu ve normal RAG kararini tek noktada descriptor olarak dondur.
   - Runtime davranisi ayni kalmali.

2. **Faz 9C - App Orchestration Cleanup**
   - app.py chat submit bolumundeki source discovery / dynamic menu / RAG response assembly fonksiyonlarini kucuk helperlara bol.
   - UI rendering ile cevap uretim mantigini ayir.

3. **Faz 9D - Dynamic Source Interface**
   - `dynamic_sources/` klasorunu ve basit reader interface/registry yapisini hazirla.
   - Dining menu reader'i davranis degistirmeden bu yapinin altina tasimayi degerlendir.

4. **Faz 9E - Evaluation Runner Profiles**
   - `evaluation/run_regression_suite.py` ile `fast`, `full`, `snapshot-update`, `dynamic-source` profilleri ekle.
   - CI-safe varsayilanlar korunmali.

5. **Faz 9F - ChromaDB Read-only Local Dev Strategy**
   - Read-only sqlite inventory helperlarini genislet.
   - Evaluation icin temp Chroma copy opsiyonunu ekle.
   - Tracked snapshot'in local dirty hale gelmesini azalt.

6. **Faz 9G - Article-level Retrieval Stabilization**
   - `golden_ales_definition` ve `golden_onlisans_lisans_agno` dahil article miss setini ayrik triage et.
   - Rerank/metadata matching iyilestirmesi genel mekanizma olarak tasarlanmali.

## Dokunulmamasi Gereken Calisan Parcalar

- Source discovery intent ve no-hallucination davranisi.
- Dynamic menu safe fallback ve diagnostic mantigi.
- ChromaDB snapshot update proseduru.
- Answer post-processing guardrail'leri: source block stripping, URL leak temizligi, inline citation korumasi.
- HF deploy workflow'unun ChromaDB LFS dogrulama akisi.
- Golden expectation review prensipleri.

## Ilk Uygulanacak Temizlik Onerisi

Ilk uygulanacak temizlik `query_router.py` olmalidir. Nedeni:

- En dusuk riskli ayrimdir.
- app.py icindeki karar akisini sadeleştirir.
- Dynamic source interface ve app orchestration cleanup icin zemin hazirlar.
- Runtime davranisi korunarak test edilebilir.

Basari kriteri:

- `yemekhane ile ilgili kaynaklar nelerdir` source discovery kalir.
- `bugun yemekte ne var` dynamic dining menu kalir.
- `AKTS nedir` normal RAG kalir.
- Mevcut source discovery/dynamic menu/retrieval evaluation metrikleri degismez.

## Guvenlik ve Commit Kapsami

Bu Faz 9A calismasinda:

- Runtime dosyalarina dokunulmadi.
- ChromaDB snapshot degistirilmedi.
- Yeni ingestion calistirilmadi.
- `data/*.pdf`, `.env`, API key/secret ve local artifact dosyalari commit kapsamina alinmadi.
- Rapor ve workflow notu disinda degisiklik yapilmadi.

## Faz 9B Query Router Extraction

Faz 9B kapsaminda `query_router.py` eklendi ve cevap modu secimi tek noktaya alindi. Router mevcut intent fonksiyonlarini yeniden yazmaz; `source_discovery.py` icindeki source discovery intent kontrolunu ve `dynamic_menu_reader.py` icindeki dining menu intent kontrolunu kullanir.

Korunan routing sirasi:

1. Source discovery
2. Dynamic dining menu
3. Normal RAG

Bu ayrim app.py'yi tamamen refactor etmez; yalnizca routing kararini `route_query()` uzerinden alir. Cevap uretimi, Streamlit session state akisi, source panel davranisi ve normal RAG pipeline korunur.

Basari kriterleri:

- `yemekhane ile ilgili kaynaklar nelerdir` source discovery modunda kalir.
- `teknoloji fakultesi ile alakali kaynak var mi` source discovery modunda kalir.
- `bugun yemekte ne var` dynamic dining menu modunda kalir.
- `AKTS nedir` normal RAG modunda kalir.

## Faz 9C App Orchestration Cleanup

Faz 9C kapsaminda app.py icindeki chat orchestration bloklari kucuk helper fonksiyonlara ayrildi. `app_chat_handlers.py` source discovery cevabi, dynamic dining menu cevabi, assistant mesaj ekleme ve guvenli hata mesaji hazirlama sorumluluklarini toplar.

Bu degisiklik UI rendering'i bastan yazmaz; Streamlit layout, session state akisi, kaynak paneli ve RAG pipeline app.py tarafinda korunur. `query_router.py` routing davranisi degistirilmedi.

Korunan davranislar:

- Source discovery sorulari kaynak listeleme modunda kalir.
- Dynamic dining menu sorulari ChromaDB snapshot'a dokunmadan dinamik reader'a gider.
- Normal RAG sorulari mevcut retrieval/rerank/LLM zincirini kullanmaya devam eder.
- Hata durumunda Streamlit exception yerine mevcut guvenli hata/fallback mesajlari korunur.

## Faz 9D Evaluation Runner Profiles

Faz 9D kapsaminda `evaluation/run_regression_suite.py` eklendi. Tekrarlanan test/evaluation komutlari profile-based runner altinda toplandi:

- `fast`
- `full`
- `dynamic-source`
- `snapshot-update`

Runner runtime davranisini degistirmez; mevcut evaluation scriptlerini sirayla cagirir. Varsayilan profiller live LLM cagrisi, dynamic live fetch, ingestion veya ChromaDB mutasyonu yapmaz. Local `regression_suite_*.local.*` raporlari commit kapsamina alinmaz.
