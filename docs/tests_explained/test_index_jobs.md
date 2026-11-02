# Trvalé úlohy správních indexů

`tests/test_index_jobs.py` používá izolovaný SQLite a při `RUN_LOCAL_SQL_TESTS=1` také skutečný lokální SQL Server. HTTP testy nevolají JHU ani Azure.

Ověřuje rychlé potvrzení úlohy bez inline modelového volání, oddělené vytvoření a backfill, nezměněné chunky/původní vektory/default a idempotentní přeskočení hotových revizí. Chyba druhé dávky zachová první; resume provede jen chybějící část.

Zrušení, odebrání Management a převzetí vypršelé rezervace během modelového volání musí zabránit zápisu výsledku. Testuje se deduplikace HTTP přijetí, jediné atomické převzetí, čtení přerušeného stavu, nezapisující starý worker a ochrana aktivního ingestovaného indexu. Cizí UUID, jiný profil a podvržené skupinové hlavičky jsou odmítnuté před prací.

Cloudová brána vyžaduje explicitní flag, MSSQL a existující tabulku úloh. Aditivní migrace je opakovatelná; CLI s nesprávným očekávaným cílem nesmí zavolat zápis. SQLite ani SQL Server 2022 nejsou důkazem podpory nativního Azure `VECTOR`; skutečná native/UI akceptace zůstává samostatná.

Průběh navíc ověřuje tenantově omezený přehled souborů bez čtení textů/vektorů, aktuální fázi během modelového požadavku, pokrytí po potvrzení dávky a odmítnutí neznámé nebo nahrazené úlohy.
