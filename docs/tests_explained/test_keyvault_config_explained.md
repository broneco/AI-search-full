# Vysvětlení testu `test_keyvault_config.py`

Tento dokument popisuje účel, strukturu a technické detaily testovacího souboru [`tests/test_keyvault_config.py`](file:///c:/Users/ondrej.bronec/OneDrive%20-%20dolphinconsulting.cz/Documents/Projekty/WIP%20-%20AI%20Search%20Full/tests/test_keyvault_config.py).

---

## High-Level Popis (Manažerský a architektonický přehled)

Testovací modul `test_keyvault_config.py` zajišťuje dvě klíčové bezpečnostní a konfigurativní záruky aplikace:

1. **Dynamické načítání tajných údajů z Azure Key Vault**: Ověřuje, že pokud aplikace nemá v lokálních `.env` souborech zadané citlivé údaje (hesla k SQL/PostgreSQL, klíče k Azure OpenAI nebo Connection String k Blob Storage), dokáže si je v produkčním i vývojovém prostředí bezpečně stáhnout z připojené služby Azure Key Vault přes spravovanou identitu (`DefaultAzureCredential`).
2. **100% Strukturální parita klíčů v tenant `.env` souborech**: Garantuje, že všech 10 tenant souborů v adresáři `tenants/` (`alzbeta`, `default`, `dolphin`, `jhu`, `showcase` pro vývojové i produkční prostředí) obsahuje 100% shodné konfigurační klíče a žádný tenant nepostrádá žádný klíč.

---

## Low-Level Popis (Technický detail pro vývojáře)

Test se skládá ze dvou hlavních testovacích funkcí:

### 1. `test_tenant_env_structural_key_parity()`
* Prochází kořenový adresář `tenants/` a vyhledává všechny konfigurační `.env` soubory.
* Ověřuje, že bylo nalezeno přesně 10 konfiguračních `.env` souborů (5 tenantů × 2 prostředí `dev`/`prod`).
* Parsuje unikátní názvy klíčů (ignoruje komentáře a prázdné řádky) a porovnává je s celkovou množinou klíčů.
* Při jakékoliv nekonzistenci (chybějící klíč v libovolném `.env` souboru) test selže s přesným výpisem chybějících klíčů.

### 2. `test_keyvault_dynamic_secret_fetching()`
* Využívá `sys.modules` k simulaci modulů `azure.identity` a `azure.keyvault.secrets`, což umožňuje běh unit testů i v prostředí bez instalovaných Azure SDK balíčků nebo bez aktivního Azure přihlášení.
* Vytváří instanci `Settings` s nastaveným `AZURE_KEY_VAULT_NAME` a předanými názvy secretů (`AZURE_KEY_VAULT_SECRET_SQL_PASSWORD`, `AZURE_KEY_VAULT_SECRET_OPENAI_KEY` atd.), ale s nulovými hodnotami samotných secretů (`None`).
* Ověřuje, že `model_validator` v class `Settings` v `app/core/config.py` správně zavolá `SecretClient.get_secret(...)` a doplní hodnoty secretů z Key Vaultu.
