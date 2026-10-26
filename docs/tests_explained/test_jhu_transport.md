# Společný JHU transport

Cache sdílí pouze ověřený SSLContext (CERT_REQUIRED a check_hostname), zatímco klienti jsou samostatní a uzavření i mezi dvěma event loopy. Busy regrese prokazuje odmítnutí chatu, embeddingu i discovery před jakýmkoli Docker/KV/HTTP lookupem.

`tests/test_jhu_transport.py` ověřuje chat, Nomic embedding i discovery přes stejný capability endpoint a jediný API KV snapshot. Fiktivní stará env hesla se nepoužijí. Mock HTTPX ověřuje Basic i capability hlavičku, heartbeat a původní digest/dimenzní pravidla.

Nepřipravený helper nesmí dostat modelový request, další otázka po obnovení ve stejném kontejneru může uspět. Timeout neopakuje generaci a nikdy nevolá cloudový model. KV chyba je explicitní a nevypne Azure modely. Skutečná validace Docker metadat odmítá veřejný binding, jiný upstream nebo protokol. Žádná síť, soukromé env, Docker ani KV se v těchto testech nepoužívají; živá akceptace je samostatná.

Veřejný managed CLI probe používá stejný HTTP context a dvě explicitní syntetická volání. Lifespan regrese ověřuje inicializaci jednoho snapshotu před DB startupem a pokračování backendu při volitelné KV chybě; SQL ani skutečné credentials se nevolají.

Chybové CLI případy rozlišují invalid/empty/mismatch a HTTP status. Ověřují jeden generate request, exit code1 a žádný raw provider text v diagnostice; nepřidávají automatické opakování.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_transport.py -q
```
