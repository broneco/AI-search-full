# Společné pytest fixtures

## Jednoduše

Testy používají vlastní databázi a vlastní dočasné konfigurace. Administrátorské API testy dostanou opravdový podepsaný token testovacího správce, aby neobcházely kontrolu oprávnění pomocí falešných hlaviček.

## Technicky

`tests/conftest.py` nastaví APP_ENV=test před importem aplikace, přesměruje engine/SessionLocal na in-memory SQLite se StaticPool a zapne PRAGMA foreign_keys. Tím se testují také nové ACL cascade vazby. Autouse fixture vytváří schéma; starší moduly dál vlastní svůj životní cyklus dat. Session fixture isolated_tenant_overlay přesměruje tenant JSON zápisy do tmp_path_factory adresáře konkrétního běhu a nečte staré `.local/test` overlay. manager_headers vytvoří skutečný DBUser pro aktuální tenant se serverovou Management skupinou a vrací jeho bearer token. Produkční DB ani tenantí konfigurace se neupdatují.
