# Testy Key Vault konfigurace

## Jednoduše

Testy nahrazují Azure SDK falešným klientem. Kontrolují správné načtení klíčů, oddělení JWT a starého heslového klíče, bezpečné zamítnutí chybějícího secretu a to, že local/test nikdy do Key Vaultu nevolá. Strukturální kontrola soukromých env potřebuje alespoň jeden vyplněný tenant, ignoruje placeholdery a nevyžaduje pevný počet deseti souborů. Vyplněný cíl zde znamená APP_ENV dev/prod, TENANT_ID a SQL/PostgreSQL host+DB; tato kontrola neověřuje platnost credentials. Bez soukromých env přeskočí pouze volitelnou kontrolu, zatímco syntetický jednotenantový scénář běží vždy.

## Technicky

`tests/test_keyvault_config.py` používá monkeypatch skutečných SDK constructorů, který pytest po každém testu obnoví. Nedochází k původnímu trvalému přepisu sys.modules. Settings se vytváří s `_env_file=None` a explicitními syntetickými hodnotami. Testuje se SQL/OpenAI/Storage/Postgres resolution, JWT empty/default → KV, pin version ID, jiný legacy secret, precedence explicitního privátního runtime klíče a repr/model_dump bez JWT/legacy hodnot. Denied/empty/default secret nesmí převzít legacy klíč pro podepisování; `_signing_key` vrací503 a provider error se nevypíše.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_keyvault_config.py -q --tb=short
```

Vše probíhá lokálně bez síťových volání, hodnot skutečných secrets a bez role assignmentu. RBAC/native runtime přístup potvrzuje jiná, explicitně schvalovaná kontrola.
