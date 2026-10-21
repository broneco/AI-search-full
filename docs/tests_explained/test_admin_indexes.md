# Testy administračního porovnání embeddingových indexů

Management katalog vrací veřejné `embedding_location` podle skutečného provideru (Azure cloud, Nomic local). Admin porovnání podle něj plánuje dvě varianty sdílející JHU slot postupně; nikdy neodhaduje umístění podle jména modelu. Regrese dvou indexů ověřuje i toto mapování.

`tests/test_admin_indexes.py` používá stejné dvě syntetické dokumentové/chunkové identity pro Azure a Nomic. Přes skutečné admin API připraví druhý index, opakuje přípravu bez duplicit a nového modelového volání a prokáže zachování původních textů, chunk UUID, legacy vektorů i výchozího ingestion indexu. Dva requesty stejné otázky mají záměrně opačné pořadí podle prostoru; každý použije jeden query provider a vrátí uloženou skutečnou identitu indexu.

Další případy ověřují připnutí explicitního plánu při změně ingestion defaultu během embed callu, dva různé indexy stejného profilu, neznámý profil stejné dimenze, chybějící/cizí/neúplný index, špatné UUID, odmítnutí indexu u keyword-only requestu a chybu před thread/model zápisy. Anonymní a běžný uživatel nemůže připravovat ani podvrhnout index. Lokální guard odmítá cloudový cíl. Timeout ponechá resumable tabulku bez přepsání Azure; ztráta Management během modelového volání zabrání zápisu vektorů.

Základní testy mají fake modely; `RUN_LOCAL_SQL_TESTS=1` navíc používá samostatnou dočasnou lokální SQL databázi. `RUN_JHU_EMBEDDING_TESTS=1` povolí `test_live_local_admin_nomic_roundtrip`: skutečně extrahuje obě veřejné ukázkové PDF, vytvoří Nomic embeddingy přes VPN, připraví index přes admin API a vyhledá přes chatové API. Azure reference a odpovědní LLM jsou v tomto testu syntetické; neprokazuje kvalitu modelu či Azure native výkon a nikdy nepřepíná aplikační index.

Příkazy: `.venv\Scripts\python.exe -m pytest tests/test_admin_indexes.py -q`; opt-in stejný příkaz s uvedenými proměnnými, případně `-k live_local_admin_nomic_roundtrip`.

Běžný přihlášený uživatel smí explicitně zvolit svůj tenantový ingestion default; nezveřejněné experimenty nadále odmítne API. Publikované experimenty a skupinové restrikce prověřuje test_local_model_registry.py.
