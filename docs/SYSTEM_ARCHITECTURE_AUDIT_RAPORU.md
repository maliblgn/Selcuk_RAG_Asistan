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

## Faz 9E ChromaDB Read-only Local Dev Strategy

Faz 9E kapsaminda local evaluation sirasinda tracked ChromaDB snapshot'in kirlenmesini azaltmak icin `chroma_runtime.py` eklendi. `CHROMA_USE_LOCAL_COPY=1` verildiginde runtime path `.local_chroma_runtime/chroma_db` altindaki ignored kopyaya yonlendirilir.

Bu strateji varsayilan runtime/HF davranisini degistirmez; flag set edilmediginde uygulama mevcut `chroma_db/` snapshot ile calisir. Snapshot update ve ingestion akislari degistirilmedi ve bu mod tarafindan otomatik olarak calistirilmaz.

Regression runner `--use-local-chroma-copy` flag'i ile child evaluation komutlarina bu modu aktarabilir. `.local_chroma_runtime/`, `chroma_runtime_*.local.*` ve regression local raporlari commit kapsamina alinmaz.

## Faz 9F Dynamic Source Interface / Registry

Faz 9F kapsaminda `dynamic_sources/` altyapisi eklendi. Ortak result/health dataclass'lari, reader protocol'u ve registry katmani dynamic kaynaklari tek yerden yonetmek icin hazirlandi.

Dining menu reader mevcut davranis korunarak registry altina baglandi. `dynamic_menu_reader.py` geriye uyumluluk icin korunur; mevcut intent, fetch, parse, format ve health fonksiyonlari calismaya devam eder.

Bu fazda yeni dynamic source eklenmedi. Query routing onceligi korunur: source discovery once, dynamic source sonra, RAG en son calisir. Runtime/HF davranisi, ChromaDB snapshot ve ingestion akislari degistirilmedi.

## Faz 9G Article-level Retrieval Stabilization

Faz 9G kapsaminda article-level retrieval borcu analiz edildi. `golden_ales_definition` ve `golden_onlisans_lisans_agno` critical failure sorulari triage edildi; iki soruda da dogru kaynak/chunk snapshot icinde bulunmasina ragmen ilk retrieval havuzuna yeterince guclu girmedigi goruldu.

Hard-coded soru ID patch'i yapilmadi. Bunun yerine genel mekanizma olarak akademik akronim tanim sorulari ve on lisans/lisans not ortalamasi sorulari icin snapshot icinden guvenli fallback adaylari eklendi. Rerank tarafinda genis lisansustu yonetmelik ve on lisans/lisans not ortalamasi kaynak sinyalleri dengeli sekilde guclendirildi.

Golden expectation zayiflatilmadi ve ChromaDB snapshot degistirilmedi. Sonraki kalite borcu olarak article title/metadata kismi uyumsuzluklari ve AGNO/GANO terminoloji farki ayri audit konusu olarak izlenebilir.

## Faz 9H Answer Grounding & Live QA Verification

Faz 9H kapsaminda `evaluation/answer_grounding_questions.json` ve `evaluation/evaluate_answer_grounding.py` eklendi. Bu katman, final cevabin dogru evidence'a dayanip dayanmadigini olcmek icin route, kaynak, belge, madde, expected term, forbidden term ve fallback sinyallerini kontrol eder.

Varsayilan evaluation CI-safe evidence-only calisir ve live LLM cagirmaz. Live QA yalniz `--live-llm` flag'i ile, manuel ve sinirli calistirilir; provider key yoksa guvenli sekilde skipped olur. `evaluation/run_regression_suite.py` full profiline grounding evidence step'i eklendi.

Bu fazda runtime cevap davranisi, ChromaDB snapshot, ingestion akisi, query router onceligi, dynamic source registry ve provider/model ayarlari degistirilmedi.

## Faz 9I Manual Live QA Findings Cleanup

Faz 9I kapsaminda canli manuel QA bulgulari incelendi. Source discovery cevaplari teknik/debug gorunumunden uzaklastirilip Turkce karakterli ve kullanici dostu sunuma cekildi.

`Cift anadal sartlari nelerdir?` sorusu triage edildi; indeksli snapshot icinde Cift Ana Dal Yonergesi ve basvuru/kabul/kayit kosullari maddesi bulundu. `GANO ile AGNO ayni sey mi?` sorusunda indeksli kaynaklarda GANO sinyali bulunurken AGNO teriminin dogrudan gecmedigi goruldu; bu nedenle terminoloji belirsizliginde temkinli cevap ilkesi guclendirildi.

Lisansustu basvuru gibi cevaplarda ayni cumlenin tekrar etmesi riskini azaltmak icin dar kapsamli cumle tekillestirme uygulanir. Query routing, ChromaDB snapshot, ingestion, dynamic source registry ve provider/model ayarlari degistirilmedi.

## Faz 9J Final Demo & Release Readiness Audit

Faz 9J kapsaminda runtime davranisi degistirilmeden final demo ve release-readiness dokumantasyonu guncellendi. README, demo script, architecture overview, release summary, final checklist ve repository audit raporlari son dogrulanmis duruma cekildi.

Canli demo soru seti RAG, source discovery, dynamic dining menu, fallback ve terminoloji belirsizligi davranislarini kapsayacak sekilde netlestirildi. Son metrikler ve bilinen sinirliliklar dokumanlara eklendi.

ChromaDB snapshot, ingestion akisi, provider/model, dependency, query routing, dynamic source registry ve RAG scoring/rerank davranisi degistirilmedi. Release, tag veya version bump olusturulmadi.

## Faz 10A Dynamic Dining Menu Date Query Support

Faz 10A kapsaminda Yemekhane dynamic reader, endpoint icindeki menu verisini gun bazli parse edecek sekilde guclendirildi. Tarihli sorgular yalnizca ilgili gunu secer; hafta sorgulari sinirli, gun gun liste verir.

Belirsiz gun adi sorgularinda birden fazla eslesme varsa tum liste dokulmez ve tarih istenir. `Ogun Yok` gunleri acikca belirtilir. Tarih menü araligi disindaysa mevcut tarih araligi soylenir ve menu icerigi uydurulmaz.

ChromaDB snapshot, ingestion akisi, provider/model, dependency, source discovery, query router onceligi ve static RAG scoring/rerank davranisi degistirilmedi.

## Faz 10A-1 Dining Menu Turkish Date Suffix Hotfix

Faz 10A-1 kapsaminda `mayista`, `Mayis'ta`, `mayisda` gibi Turkce ekli tarih ifadeleri exact date olarak normalize edildi. Gun + ay iceren sorgularin hafta/ay liste davranisina dusmesi engellendi.

`5 mayista yemekhane menusu ne` gibi sorgular yalnizca 5 Mayis entry'sini secer. `21 mayista ne yemek var` sorgusunda 21 Mayis varsa yalnizca o gun dondurulur; yoksa mevcut tarih araligi belirtilerek menu uydurulmaz. Ay geneli belirsiz sorgularda tum ay dokulmez.

ChromaDB snapshot, ingestion, provider/model, dependency, source discovery, query router onceligi ve static RAG degistirilmedi.
## Faz 10B Chroma Coverage QA & Rewrite Safety Hardening

- Rewrite guardrail eklendi: LLM rewrite sonucu fallback/cevap cümlesine dönüşürse veya kritik terim ailesini kaybederse orijinal soru korunur.
- Multi-query varyasyonları için alakasız alan drift'i filtrelenir; özellikle AGNO/GANO gibi akademik terimler kimya/biyoloji benzeri ilgisiz sorgulara taşınmaz.
- Yemekhane dynamic reader geniş "menü ne" sorularında ilk günleri dökmek yerine tarih/gün netleştirmesi ister.
- Çift anadal ve lisansüstü başvuru sorguları için genel metadata/rerank sinyalleri güçlendirildi; hard-coded question ID patch yapılmadı.
- Chroma coverage audit, generated vector coverage questions, vector coverage evaluator ve manual acceptance evaluator eklendi.
- ChromaDB snapshot, ingestion, routing sırası, provider/model ve dependency ayarları değiştirilmedi.

## Faz 11A Session-Only PDF & Manual URL RAG

- Kullanıcının oturum içinde PDF yükleyip manuel URL ekleyebileceği, ana ChromaDB snapshot'a yazmayan geçici kaynak katmanı eklendi.
- Geçici kaynaklar yalnızca bellekte chunklanır ve lexical in-memory store üzerinden cevaplanır; dosya, PDF veya URL içeriği repoya ya da `chroma_db/` snapshot'a eklenmez.
- Query routing sırası korunarak `source_discovery -> dynamic_dining_menu -> session_upload_rag -> rag` akışı belgelendi. Source discovery ve yemekhane niyetleri geçici kaynak tarafından gölgelenmez.
- URL loader SSRF/private-host koruması, robots.txt kontrolü, boyut sınırı, HTML/text/PDF ayrımı ve güvenli hata mesajları içerir.
- Geçici kaynakta kanıt yoksa sistem ana RAG'e otomatik düşmez; bilgi uydurmadan güvenli fallback verir ve kullanıcı isterse normal Selçuk kaynaklarında yeniden sorabilir.
- ChromaDB snapshot, ingestion, provider/model, dependency, dynamic source endpoint ve static RAG scoring/rerank davranışı değiştirilmedi.

## Faz 11A-2 Session RAG Answer Quality Hardening

- PDF/URL session kaynaklarında text quality cleanup, section-aware chunking ve metadata-aware retrieval güçlendirildi.
- E-posta, telefon, URL, dil seviyesi, GPA, tarih, proje listesi, beceri listesi ve şart/gerekli belge listesi gibi sorularda ham chunk dökmek yerine hedefli extractor ve structured answer synthesis kullanılır.
- CV, yönerge, yönetmelik, duyuru, ders izlencesi, akademik takvim, rapor ve web sayfası gibi genel belge türleri için bölüm sinyalleri (`section_title`, `section_type`) ve içerik bayrakları eklenir.
- Session kaynaklarında ana ChromaDB'ye fallback yapılmadı; kaynakta olmayan bilgi güvenli fallback ile karşılanır.
- Prompt injection cümleleri belge verisi kabul edilir, sistem talimatı olarak uygulanmaz.
- ChromaDB snapshot, ingestion, dependency/provider/model, query routing sırası, dynamic menu ve static RAG davranışı değiştirilmedi.

## Faz 11A-1B HF Upload 403 Diagnostics and Fallback Paths

- Hugging Face Space yapılandırması Docker SDK, `app_port: 7860`, Dockerfile CMD/env port `7860` ve `.streamlit/config.toml` üzerinden incelendi; port 8501'e çevrilmedi.
- `.streamlit/config.toml` upload için `address = "0.0.0.0"`, `enableCORS = false`, `enableXsrfProtection = false`, `maxUploadSize = 25` ve `maxMessageSize = 25` ayarlarıyla netleştirildi.
- Session source UI'a PDF URL ve metin yapıştırma fallback yolları eklendi; bu kaynaklar yalnız session belleğinde tutulur ve ana ChromaDB snapshot'a yazılmaz.
- PDF URL'leri `pdf_url`, yapıştırılan metinler `pasted_text` session source olarak işlenir; cevap citation ve source noun üretimi bu source type'ları destekler.
- Secret-safe upload diagnostics eklendi; token/API key/env secret değerleri UI veya local report içinde gösterilmez.
- ChromaDB snapshot, ingestion, dependency/provider/model, query routing sırası, dynamic menu ve static RAG davranışı değiştirilmedi.

## Faz UI-1 Selçuk-AI Chat Interface Refresh

- Uygulama markası `Selçuk-AI` olarak güncellendi ve koyu tema `#121212`, metin `#e0e0e0`, vurgu `#00a8cc` paletine taşındı.
- ChatGPT benzeri sol sidebar, sohbet arama/son sohbetler, veri kaynakları, kontrol paneli, YZ araçları, admin ve yardım navigasyonu eklendi.
- Session kaynak kontrolleri PDF, PDF URL, web URL ve metin yapıştırma akışlarını görünür kılar; ana ChromaDB snapshot'a yazmaz.
- Kontrol paneli read-only kalite/health katmanını göstermeye devam eder. YZ araçları ekranı gerçek routing ve mevcut mod bilgisini gösterir; backend'i olmayan sesli komut pasif kalır.
- Query routing, dynamic source registry, ChromaDB snapshot, ingestion, dependency/provider/model ve static RAG scoring/rerank davranışı değiştirilmedi.
