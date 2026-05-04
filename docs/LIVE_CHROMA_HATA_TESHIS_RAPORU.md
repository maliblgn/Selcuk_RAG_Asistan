# Live ChromaDB Hata Teshis Raporu

## 1. Hata
Canli ortamda gorulen hata:

`Error getting collection: Collection [008ae1a6-e807-4cd2-aa5b-980d6103af81] does not exist.`

Bu hata ChromaDB persist dizini bulunsa bile icindeki collection referansinin okunamadigini, eksik oldugunu veya deployment sirasinda beklenen index artifact'inin canli ortama tasinmadigini gosterir.

## 2. Local vs Live Farki
Local ortamda `chroma_db/` klasoru mevcut ve healthcheck sonucu okunabilir:

- status: `ok`
- document_count: `659`
- unique_source_count: `45`
- source_type_counts: `web_page=2`, `web_pdf=657`

GitHub'a `chroma_db/` commit edilmedigi icin canli ortamda bu klasor eksik, bos, bozuk veya farkli bir path'te olabilir. Localde cevap uretilebilmesi canli ortamda ayni index'in var oldugu anlamina gelmez.

## 3. Kodda DB Path Kullanimi
Incelenen dosyalar:

| Dosya | DB path kullanimi | Not |
| --- | --- | --- |
| `rag_engine.py` | `os.path.dirname(os.path.abspath(__file__)) / chroma_db` | Repo dosyasina gore absolute path olusturuyor. CWD degisiminden etkilenmez. |
| `data_ingestion.py` | `_BASE_DIR / chroma_db` | Ingestion ayni repo kokundeki `chroma_db` dizinine yazar. |
| `index_report.py` | `BASE_DIR / chroma_db / chroma.sqlite3` | SQLite dosyasini dogrudan okur. |
| `app.py` | `data_ingestion.DB_DIR` ve `SelcukRAGEngine` | Admin panel index durumunu healthcheck ile gosterir. |

Sonuc: Path hardcoded olarak repo kokundeki `chroma_db` dizinine bagli. Live deploy ortami bu klasoru kalici depolama olarak tasimiyorsa index kaybolur.

## 4. Eklenen Healthcheck
Yeni script:

```powershell
python check_chroma_health.py --db-path chroma_db
python check_chroma_health.py --db-path chroma_db --json --out chroma_health_report.json
```

Kontroller:

- `db_path` var mi?
- `chroma.sqlite3` var mi?
- Chroma collection okunabiliyor mu?
- document/chunk sayisi
- benzersiz source sayisi
- `source_type` dagilimi
- collection hatasi varsa acik `status` ve `error`

Olası status degerleri:

- `missing`
- `missing_sqlite`
- `collection_missing`
- `collection_unreadable`
- `empty`
- `ok`

## 5. Uygulama Fallback Davranisi
`rag_engine.py` baslangicinda ChromaDB health validation eklendi. DB eksik, bos veya collection okunamazsa `KnowledgeBaseUnavailableError` uretilir.

Kullaniciya raw collection UUID yerine su mesaj gosterilir:

`Bilgi tabani canli ortamda hazir degil. Lutfen yonetici panelinden veri indeksleme islemini calistirin veya ChromaDB kalici depolamasini kontrol edin.`

Teknik detay loglarda ve Streamlit expander icinde korunur. Boylece sorun gizlenmez, fakat son kullaniciya ham Chroma internal UUID hatasi dusmez.

Admin panelde ek olarak:

- ChromaDB path
- DB var/yok
- collection okunuyor/okunamiyor
- document count
- unique source count

gosterilir.

## 6. Kalici Cozum Secenekleri
Kalici cozum icin ChromaDB'nin canli ortamda uretilebilir veya korunabilir olmasi gerekir:

- Live ortamda kontrollu ingestion calistirmak.
- Streamlit/hosting ortaminda persistent volume kullanmak.
- Build/release asamasinda index olusturmak.
- Guvenli DB artifact/backup restore akisi kurmak.
- `chroma_db/` klasorunu GitHub'a commit etmemeye devam etmek.

## 7. Sonraki Adim
Canli ortamda su komut calistirilip health sonucu kontrol edilmeli:

```powershell
python check_chroma_health.py --db-path chroma_db --json --out chroma_health_report.json
```

Eger status `missing`, `missing_sqlite`, `collection_missing` veya `empty` ise problem koddan cok canli index hazirlik/persistent storage problemidir. Bu durumda ingestion veya artifact restore stratejisi secilmelidir.
