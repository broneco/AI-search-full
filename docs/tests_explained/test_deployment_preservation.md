# test_deployment_preservation

[Testy](../../tests/test_deployment_preservation.py) ověřují [read-only checkpoint nástroj](../../verify_deployment.py) a [provozní postup](../development/deployment-preservation-test.md).

- Skutečná izolovaná SQLite / opt-in lokální SQL Server databáze obsahuje účet, historii, ACL, vlastní tři konfigurace a 1536/768dim indexy nad stejným chunkem.
- Capture vydává pouze SELECTy a agregované otisky; manifest neobsahuje citlivé vstupy ani vektory.
- Přepsání heslového hashe/skupin, zprávy, dokumentu, chunku, Nomic vektoru, promptu a modelového popisu selže i při nezměněných počtech.
- Cizí tenant, rozdíl velikosti písmen i koncová mezera neovlivní snapshot; cizí vektor v tenantové tabulce je explicitní chyba.
- Vyžadované indexy musí existovat a být úplné. Neúplné manifesty a chybné otisky neprojdou jako shoda.
- Skutečné Blob byte streamy mají izolovaný fake klient; změna obsahu je viditelná, selhání a jiný kontejner nemají cache/fuzzy fallback.
- Offline compare odlišuje změnu chráněných credentials od očekávané nové revize/verze. Guard nesprávného cíle selže před SQL a chyby nevypisují soukromé výjimky.
- Existující checkpoint se nepřepíše; samostatný konzolový bundle přenese přesné argumenty bez instalace/private env.
- Disková SQLite s novým enginem, novými image defaults a opakovaným startupem zachová oba indexy, původní řádky a vlastní nastavení, které skutečné loadery dál čtou z SQL.
- MSSQL kompilační regrese kontroluje nativní VECTOR→nvarchar(max), server-side HASHBYTES a parametrizovaný přesný tenant s DATALENGTH/BIN2.

Lokální výsledky neprokazují Azure runtime, VPN, opravdové Blob soubory ani uskutečněné nasazení. Cloudové checkpointy a funkční akceptace patří do privátních receipts a dokončeného deployment reportu.
