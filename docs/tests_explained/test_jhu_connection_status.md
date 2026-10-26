# Testy diagnostiky a obnovy JHU

Odpojení refresh klienta nezruší bounded KV worker a neuvolní sdílený slot před jeho dokončením; samostatná asynchronní regrese ověřuje odmítnutí další operace a následný návrat slotu.

`tests/test_jhu_connection_status.py` používá skutečné tokeny, serverové účty/skupiny a SQLite fixtures, syntetický HTTP/Docker/KV. Stav helperu se nezaměňuje s backend health; raw URL, capability ani credentials se nevrací.

API odmítne anonymní/běžné účty, podvrženou skupinu, odebraná Management práva i cizí přesný tenant. Refresh má sdílený modelový slot a atomicky nahradí snapshot až po ověření helperu a KV. Syntetická rotace načte novou identitu/credentials, zatímco KV chyba zachová předchozí snapshot. Sticky inicializační chybu odstraní jen explicitní refresh. Terminální auth stav nezmizí pouze kvůli starému heartbeat.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_connection_status.py -q
```
