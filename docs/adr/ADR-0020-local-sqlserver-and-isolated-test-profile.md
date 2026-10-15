# ADR-0020: Lokální SQL Server a izolované profily local/test

- **Status:** Accepted
- **Datum:** 2026-10-12
- **Autor:** AI Search Implementation Team

## Kontext

Backend dosud při běžném spuštění vybíral databázi z přítomnosti `AZURE_SQL_HOST` a prostředí `dev` načítalo tenantí Azure konfiguraci včetně hodnot pro Key Vault. To ztěžovalo bezpečný lokální vývoj a hrozilo připojením na cloudovou databázi.

## Rozhodnutí

- Oddělit `APP_ENV` (`local`, `test`, `dev`, `prod`) od `DATABASE_BACKEND` (`sqlserver`, `azure_sql`, `postgresql`, `auto`). Režim `auto` zachovává dosavadní výběr Azure SQL při nastaveném Azure hostu, jinak PostgreSQL.
- Lokální aplikace používá SQL Server Developer v Dockeru a pojmenovaný persistentní volume. Kontejner vystaví databázi jen na loopbacku; první start vygeneruje heslo do ignorovaného `.env.local`.
- Lokální aplikace sama vytvoří pouze svou databázi `ai_search_local`. Azure SQL zůstává provisionované mimo aplikaci.
- `local` a `test` načítají jen svůj kořenový env soubor a nepoužívají Key Vault. Jejich změny tenantích JSON souborů se zapisují do oddělených ignorovaných overlay složek pod `.local/` a čtou tracked soubory jako fallback.
- Automatické testy nadále používají SQLite fixture v paměti. Lokální SQL Server slouží k ručnímu ověření běžného SQL Server chování, ne jako náhrada Azure SQL v testech DiskANN a výkonu.
- VS Code úlohy spustí lokální databázi, backend a frontend v tomto pořadí; zvláštní úloha spouští testy v izolovaném profilu.

## Důsledky

- Vývojář potřebuje Docker Desktop nebo Rancher Desktop s Linux kontejnery a hostitelský ODBC ovladač SQL Server 17 nebo 18.
- Persistentní data zůstávají lokální i po restartu Dockeru; zastavení compose projektu data nemaže.
- Tato cesta neověřuje úplné pokrytí korpusu při vektorovém hledání, DiskANN, Azure SQL oprávnění ani kapacitní profil Basic 5 DTU.
- Azure `dev` a `prod` nadále používají stávající tenantí konfigurace.
