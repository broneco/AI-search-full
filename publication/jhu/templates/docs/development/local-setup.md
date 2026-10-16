# Lokální vývoj

Kompletní příkazy pro instalaci, persistentní databázi, VS Code tasks a spuštění obou frontendů jsou v [README](../../README.md#rychlý-start-ve-vs-code). Používej lokální SQL Server 2022 Developer, nikoli experimentální PostgreSQL cestu. Po restartu zapni Docker/Rancher a stejnou VS Code úlohu; zachovej .env.local a SQL volume.

Do existujícího .env.local doplň jen své modelové připojení a zachovej generované databázové hodnoty. Startup idempotentně doplní dva české dokumenty o fiktivní škole Aurora, pokud je dostupný embedding provider. Nejde o skutečné předpisy JHU. Bez modelového připojení lze ověřit UI/API a offline testy, nikoli skutečné odpovědi.

| Otázka | Očekávaná informace |
|---|---|
| Kolik kreditů potřebuji pro postup do druhého ročníku? | Alespoň 40 kreditů za první rok. |
| Kolik pokusů mám na zkoušku? | Jeden řádný a dva opravné pokusy. |
| Kdy má studijní oddělení úřední hodiny? | Pondělí a středa, 8:30–11:30. |
| Do kdy se podává přihláška na Erasmus? | Do 15. března. |

Otevři citaci a ověř odpovídající PDF a českou diakritiku. Docker stderr varování samo nemusí znamenat chybu; rozhoduje exit kód a dostupnost Engine. Lokální SQL používá JSON/LIKE referenci a neprokazuje native Azure VECTOR, fulltext nebo DiskANN. [Automatizované testování](testing.md).
