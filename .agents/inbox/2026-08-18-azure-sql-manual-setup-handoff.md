# Azure Deployment Handoff: Manual Provisioning of Azure SQL Database

- Status: completed
- Created: 2026-08-18
- Related task: Migration from PostgreSQL to Azure SQL Database
- Related ADR: ADR-0002-azure-sql-migration.md
- Related branch/PR: `microsoft-sql`

## 🎯 Cíl handoffu
Ruční vytvoření jednoho Azure SQL Serveru a jedné Azure SQL Databáze v Azure Portálu bez nutnosti složitých příznaků v názvech.

---

## 🛠️ Přesný návod pro založení v Azure Portálu

### Krok 1: Otevřete v Azure Portal založení nové databáze
1. V Azure Portálu klikněte na **Create a resource** -> vyhledoje **SQL Database** a klikněte **Create**.
2. **Subscription & Resource Group:** Vyberte svou subscription a resource groupu (např. `dolphin-ai-search-rg-dev` nebo existující rg).

### Krok 2: Konfigurace Databáze a Serveru
1. **Database name:** `dolphin-ai-search-sqldb`
2. **Server:** Klikněte na **Create new**:
   - **Server name:** `dolphin-ai-search-sql` *(musí být v Azure unikatní, např. `dolphin-ai-search-sql.database.windows.net`)*
   - **Location:** `West Europe`
   - **Authentication method:** *Use SQL authentication* (nebo *Use both SQL and Entra authentication*)
   - **Server admin login:**např. `sqladmin`
   - **Password:** Vaše bezpečné heslo (zaznamenejte si ho do lokálního `.env`)
   - Klikněte **OK**.

### Krok 3: Compute + storage
1. Klikněte na **Configure database**.
2. Zvolte **Service tier:** *General Purpose* -> **Compute tier:** *Serverless*.
3. Povolte **Auto-pause delay** (např. 1 hour) pro automatickou úsporu nákladů mimo vývoj.
4. **Collation (v tabu Additional settings):** `Latin1_General_100_CI_AS_SC_UTF8` (nebo ponechte standardní `SQL_Latin1_General_CP1_CI_AS`).

### Krok 4: Síťové nastavení (Networking - DŮLEŽITÉ!)
1. Přejděte na záložku **Networking**.
2. Nastavte **Connectivity method:** *Public endpoint*.
3. V sekci Firewall rules nastavte:
   - **Allow Azure services and resources to access this server:** `Yes`
   - **Add current client IP address:** `Yes` *(povolí připojení z vašeho lokálního počítače)*.

### Krok 5: Vytvořit
1. Klikněte na **Review + create** a následně **Create**.

---

## 🔑 Klíče pro konfigurační soubor `.env`

Po vytvoření doplňte do vašeho lokálního `.env` (nebo `.env.dev`) následující proměnné:

```ini
AZURE_SQL_HOST=dolphin-ai-search-sql.database.windows.net
AZURE_SQL_PORT=1433
AZURE_SQL_DB=dolphin-ai-search-sqldb
AZURE_SQL_USER=sqladmin
AZURE_SQL_PASSWORD=VašeZadanéHeslo
AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server
```

---

## 📋 Zpětná vazba pro agenta (po dokončení v Portálu)

Doplňte pouze ne-tajné údaje:

```yaml
resource_group: dolphin-ai-search-rg-dev
region: westeurope
sql_server: dolphin-ai-search-sql.database.windows.net
sql_database: dolphin-ai-search-sqldb
sql_user: sqladmin
status: completed
```

---

## 🧪 Ověření dostupnosti (PowerShell)

```powershell
Test-NetConnection -ComputerName "dolphin-ai-search-sql.database.windows.net" -Port 1433
```
