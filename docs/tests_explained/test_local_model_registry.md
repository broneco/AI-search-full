# Testy registru lokálních modelů

`tests/test_local_model_registry.py` používá syntetický inventář dvou chatových modelů, Nomic, MXBAI a rerankeru. Ověřuje oddělení read-only discovery od explicitního zápisu, bulk registraci bez generování, idempotenci, zachování Nomic fingerprintu a odlišné query/document instrukce MXBAI. Přesná data tenantu `ju-prod` se nesdílejí s konfigurací aliasu `jhu`.

Testy skutečného API a SQL persistence pokrývají přihlášení, podvržené klientské skupiny, přímý request nezveřejněného modelu, zveřejnění, omezení skupin, porovnání revize a atomické odmítnutí neplatného názvu/digestu/účelu nebo endpointu z klienta. Cloudové defaulty se nemění.

Mock HTTP transport prověří směrování dvou LLM, Basic kontrakt, kontext/výstupní limity, Unicode a odmítnutí dlouhého promptu před HTTP. Změna digestu před nebo po volání, timeout, nesoulad modelu, prázdná či pouze thinking odpověď a dosažený limit nevytvoří skryté další generování ani fallback. Chyby neobsahují credentials/thinking.

Sdílená indexová fixture navíc ověřuje zveřejněný Nomic index v běžné user roli, zachované dokumentové/chunkové ACL, stejné chunky a nezměněný Azure ingestion default. Odebrání dostupnosti zabrání query embeddingu i novému thread zápisu. `RUN_LOCAL_SQL_TESTS=1` zapojí stejnou cestu nad izolovanou Docker SQL databází; aplikační korpus se nepoužije.

Spuštění: `.venv\Scripts\python.exe -m pytest tests/test_local_model_registry.py -q`. Živé testy jsou zvlášť opt-in, neposuzují kvalitu modelů ani výkon a nesmějí automaticky generovat přes celý inventář včetně 120B modelů.

Další regrese brání duplicitě již nakonfigurovaného Qwenu a tiché změně jeho digestu. Změna embeddingových instrukcí při stejném modelu/digestu vytvoří nový profil a starý zůstane nezměněný. Chybějící tabulka umožní původní file katalog, ale chybějící SQL oprávnění skrytá metadaty se nesmějí ignorovat. Migrační DDL vyžaduje přesný host/DB/tenant. Revokace pravidla v další SQL session přebije i dříve načtený ORM objekt.

Finální živý opt-in ověřil krátkou samostatnou generaci llama3.2:3b a celý průchod: skutečné MXBAI embeddingy → izolovaná lokální SQL → skutečná Llama RAG odpověď přes chatové API. Reference Azure byla syntetická, oba dokumenty jsou krátké syntetické texty; aplikační data se nemění. Nejde o plošný test kvality všech LLM ani o cloudový benchmark.
