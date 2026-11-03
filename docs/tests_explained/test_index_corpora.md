# Testy dvojic indexu a chunkování

`tests/test_index_corpora.py` používá izolované SQLite a volitelně skutečný lokální SQL Server. Modely a cloudové Blob úložiště jsou nahrazené, zdrojové TXT originály jsou pouze testovací.

- Dvě konfigurace stejného embeddingového modelu dostanou různé identity, korpusy a počty chunků. Původní texty/revize/vektory a default zůstanou stejné; opakované doplnění neextrahuje hotové originály ani nevolá embeddingový model.
- Exact vektory, keyword prefiltry a rozšíření kontextu vybírají jen zvolený korpus. Chat ukládá jeho citace; smazání vlastního indexu zachová původní index i text a přístup ke známým historickým citacím.
- Název má optimistickou revizi, starý zápis/mazání skončí konfliktem. Výchozí index a mazání během úlohy jsou chráněné. Token jiného tenantu odmítá již autentizační hranice.
- Blob náhled používá přesný klíč, ověřuje checksum, odstraní dočasný soubor a nezapisuje chunky. Cizí token nevyvolá Blob čtení; neplatné kontejnery, traversal, jiné URL a odchod z `data/` jsou odmítnuté bez přístupu ke storage.
- Migrace se zkouší nad schématem bez nových tabulek a sloupce, dvakrát; zachová původní dokument a chunk, kterému přibude NULL korpus.
- Připravený index s chybějícím chunkem zůstane nepřipravený, i když všechny zbývající chunky mají platný vektor. Rozhoduje také zaznamenaný počet chunků každého dokumentu.
- Rozdílné ACL pasáží znepřipraví vlastní index a zastaví přepočet před embeddingem. Chyba sémantického modelu se při plném zpracování nezamění za jiný splitter.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:RUN_LOCAL_SQL_TESTS = '1'
.venv/Scripts/python.exe -m pytest tests/test_index_corpora.py tests/test_index_jobs.py -q
```

SQLite a lokální SQL JSON referenční vektory neprokazují aktuální Azure native `VECTOR`/ANN plán, skutečnou dostupnost JHU, oprávnění k živým Blobům ani GUI/produkční nasazení. Tyto gates zůstávají oddělené. JS regrese navíc ověřuje, že administrační snapshot přenese jen chunkování a zvolené pomocné modely, nikoli rankingová nastavení.
