# Testy trvalého tenantového nastavení

[tests/test_tenant_settings.py](../../tests/test_tenant_settings.py) používá diskovou SQLite databázi v izolovaném pytest workspace, bez privátního env, skutečného modelu nebo Azure zápisů.

Ověřuje správní API pro tři prompty a chunky, jednotné sync/async načtení, ignorování legacy Blob konfigurací v cloudu, výměnu image defaults/odpojení SQL/opakovaný startup při zachování účtu, hashe, konverzace, zprávy, dokumentu a chunku. Samostatně kontroluje přesné tenanty včetně aliasů/case/trailing space, fallback pouze při chybějícím řádku, bezpečnou 503 při chybějící tabulce a neplatném payloadu, read-only plán, chybné target guards, insert-only opakovaný import, úplnost exportu a rollback transakce při pozdější chybě. Lokální overlay zůstává oddělený od SQL i veřejných souborů.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tenant_settings.py tests/test_tenant_config.py tests/test_prompts_api.py tests/test_search_config.py -q
```

Testy nedokládají skutečnou Azure SQL migraci, ACA rollout ani obnovu zálohy. [Provozní postup](../development/non-destructive-updates.md).
