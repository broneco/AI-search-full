# test_local_embeddings.py

Testuje skutečné hranice nového JHU adaptéru bez modelu v běžné sadě: file-level katalog a konfigurační alias, zachování Azure fingerprintu, odmítnutí jiné revize, oddělené Nomic prefixy, pořadí a počet dávek, `truncate:false`, prázdný vstup bez HTTP a kontrolu digestu před/po volání.

Mock HTTP pokrývá autentizaci, chybějící API/model, odmítnutý vstup, timeout bez retry, busy, změněný model, neúplný batch, chybný rozměr, nečíselné/neplatné/nenormalizované vektory a bezpečnou chybovou zprávu. Sdílený inference/embedding slot a VPN guard brání nechráněnému lokálnímu HTTP volání.

Repository test běží nad SQLite a při `RUN_LOCAL_SQL_TESTS=1` také izolovanou dočasnou SQL Server databází. Ověřuje 1536/768 nad stejným chunkem, zachování legacy embeddingu, resumable backfill, aktivní query/ingest, neúplný starý index a cascade delete. API test používá skutečný retrieval a mock modely: uloží chunk přes aktivní lokální profil, vyhledá jej a vrátí profil v metadatech; nedostupný profil nesmí vytvořit další thread ani použít Azure.

`RUN_JHU_EMBEDDING_TESTS=1` navíc povolí živý syntetický test se skutečným Nomic API a dočasnou lokální SQL databází. Čte pouze JHU connection keys z ignorovaného prostředí a ověří VPN. Referenční 1536 vektory v tomto testu jsou výslovně syntetické, nikoli tvrzení o Azure výstupu. Nezasahuje aplikační data a neprokazuje Azure native/performance ani obecnou relevanci češtiny. [Příkazy](../development/local-embeddings.md).

Aktivní i explicitní provider nyní načítá také tenantový SQL registr; unit fixture bootstrapu používá skutečnou izolovanou session a vícemodelové fixture deklarují runtime katalog.
