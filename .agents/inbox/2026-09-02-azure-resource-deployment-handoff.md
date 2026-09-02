# Azure Deployment Handoff: Nastavení Azure Zdrojů ve 3 Resource Groups (Dev, Prod, Showcase)

- Status: pending_human_action
- Created: 2026-09-02
- Related task: Multi-Resource Group separation, Azure SQL DTU Model, and Naming Standardization
- Related ADR: ADR-0017-azure-sql-dtu-model-and-resource-group-architecture.md

---

## 🎯 Cíl Hand-offu

Tento návod poskytuje krok-za-krokem instrukce pro ruční založení a konfiguraci Azure zdrojů v Azure Portálu (nebo přes Azure CLI skripty) v rámci vašich 3 vytvořených Resource Group:
1. `ai-search-rg-dev` (Multi-tenant Vývoj)
2. `ai-search-rg-prod` (Multi-tenant Produkce)
3. `ai-search-showcase-rg-dev` (Isolated Single-tenant Showcase)

---

## 🏛️ Přehled Jmenné Konvence Zdrojů

| Prostředí | Resource Group | Azure SQL Server | Azure SQL DB (DTU) | Storage Account | Container Apps Env | Container Registry |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEV** | `ai-search-rg-dev` | `sql-aisearch-dev` | `sqldb-dolphin-dev` | `staisearchdev` | `cae-aisearch-dev` | `craisearchdev` |
| **PROD** | `ai-search-rg-prod` | `sql-aisearch-prod` | `sqldb-dolphin-prod` | `staisearchprod` | `cae-aisearch-prod` | `craisearchprod` |
| **SHOWCASE** | `ai-search-showcase-rg-dev` | `sql-aisearch-showcase` | `sqldb-showcase` | `staisearchshowcase` | `cae-aisearch-showcase` | `craisearchshowcase` |

---

## 📦 Přesun Existujících Zdrojů (Doporučeno pro PROD a DEV)

Pokud již máte funkční PROD a DEV zdroje v jiné Resource Group (např. `DOLPHIN_DS`), **přesun je nejelegantnější a nejbezpečnější cesta**:
- **Nulová ztráta dat**: Všechny tabulky, embeddingy a nahrané PDF v kontejneru zůstanou 100% zachovány.
- **Bez nutnosti re-indexace**: Nemusíte znovu nahrávat podklady.
- **Stejná připojení**: Název SQL Serveru i klíče zůstanou identické.

### Postup přesunu v Azure Portálu (Resource Move):
1. Otevřete původní Resource Group (např. `DOLPHIN_DS`).
2. Zaškrtněte zdroje, které chcete přesunout (např. SQL Server, Storage Account, Container App, Static Web App).
3. V horním menu klikněte na **Move** -> **Move to another resource group**.
4. Jako cílovou Resource Group vyberte `ai-search-rg-prod` (pro produkční zdroje) nebo `ai-search-rg-dev` (pro vývojové zdroje).
5. Klikněte na **Next** -> Azure ověří prerekvizity a během 2–3 minut zdroje bezvýpadkově přesune.

### Přepnutí přesunuté databáze na DTU mód:
1. Po přesunu otevřete vaši Azure SQL Databázi v nové RG (`ai-search-rg-prod` nebo `ai-search-rg-dev`).
2. V levém menu vyberte **Compute + storage**.
3. Přepněte rozhraní na **DTU-based purchasing model**.
4. Zvolte požadovanou úroveň (např. **Basic (5 DTU)** pro Dev nebo **Standard S0 / S1** pro Prod) a klikněte na **Apply**.

---

## 🛠️ Postup Nastavení v Azure Portálu (Krok za krokem)

### 1. Založení Azure SQL Serveru a Databáze v DTU Módu

> [!NOTE]
> DTU model nabízí garantovaný výkon bez prodlevy při probouzení ze serverless auto-pause.
> Databázi můžete začít na **Basic (5 DTU)** a kdykoliv ji bez výpadku škálovat nahoru na **Standard S0 / S1 / S2**.

#### Postup pro DEV (`ai-search-rg-dev`):
1. V Azure Portálu klikněte na **Create a resource** -> **SQL Database** -> **Create**.
2. **Subscription & Resource Group:** Vyberte svou subscription a RG `ai-search-rg-dev`.
3. **Database Name:** `sqldb-dolphin-dev` (nebo `sqldb-{tenant}-dev`).
4. **Server:** Klikněte na **Create new**:
   - **Server name:** `sql-aisearch-dev` *(v Azure unikatní, např. `sql-aisearch-dev.database.windows.net`)*
   - **Location:** `North Europe` (nebo `West Europe`)
   - **Authentication:** *Use SQL authentication* (nebo *Use both SQL and Entra authentication*)
   - **Server admin login:** `sqladmin`
   - **Password:** Vaše bezpečné heslo
   - Klikněte **OK**.
5. **Compute + storage:**
   - Klikněte na **Configure database**.
   - Přepněte záložku na **DTU-based purchasing model**.
   - Vyberte **Basic** (5 DTU, max 2 GB) nebo **Standard** (S0: 10 DTU, max 250 GB).
   - Klikněte **Apply**.
6. **Networking (DŮLEŽITÉ):**
   - Na záložce **Networking** nastavte **Connectivity method:** *Public endpoint*.
   - **Allow Azure services and resources to access this server:** `Yes`
   - **Add current client IP address:** `Yes`
7. Klikněte **Review + create** -> **Create**.

#### Postup pro SHOWCASE (`ai-search-showcase-rg-dev`):
- Opakujte stejný postup v Resource Group `ai-search-showcase-rg-dev`:
  - **Server name:** `sql-aisearch-showcase`
  - **Database name:** `sqldb-showcase`
  - **Compute:** DTU model (Basic 5 DTU nebo Standard S0 10 DTU)

#### Postup pro PROD (`ai-search-rg-prod`):
- Opakujte v Resource Group `ai-search-rg-prod`:
  - **Server name:** `sql-aisearch-prod`
  - **Database name:** `sqldb-dolphin-prod`
  - **Compute:** DTU model (Standard S1 20 DTU nebo Standard S2 50 DTU)

---

### 2. Založení Storage Accountů a Blob Containerů

1. Přejděte do cílové Resource Group (`ai-search-rg-dev`, `ai-search-rg-prod` nebo `ai-search-showcase-rg-dev`).
2. Vytvořte **Storage Account**:
   - Dev RG: `staisearchdev`
   - Prod RG: `staisearchprod`
   - Showcase RG: `staisearchshowcase`
   - **Performance:** Standard, **Redundancy:** LRS
3. Po vytvoření otevřete Storage Account -> **Containers** -> vytvořte kontejnery:
   - Pro Dev: `dolphin-originals-dev`, `dolphin-artifacts-dev`
   - Pro Showcase: `showcase-originals`, `showcase-artifacts`
   - Pro Prod: `dolphin-originals-prod`, `dolphin-artifacts-prod`

---

### 3. Způsob Škálování DTU Databáze (Basic -> Standard -> Premium)

Pokud budete potřebovat navýšit výkon nebo kapacitu databáze (např. z 2 GB na 250 GB storage):
1. V Azure Portálu otevřete příslušnou databázi (např. `sqldb-dolphin-dev`).
2. V levém menu klikněte na **Compute + storage** (pod záložkou Settings).
3. Posuvníkem změňte úroveň z **Basic** na **Standard (S0, S1, S2)** nebo upravte počet DTU.
4. Klikněte na **Apply**. *Úprava proběhne za běhu během cca 30 sekund bez ztráty dat.*

Alternativně příkazem přes Azure CLI:
```powershell
az sql db update --resource-group ai-search-rg-dev --server sql-aisearch-dev --name sqldb-dolphin-dev --service-objective S0
```

---

## ⚡ Rychlá Alternativa: Založení Pomocí Příkazové Řádky (Azure CLI)

Pokud preferujete vytvořit zdroje jedním příkazem místo klikání v portálu, můžete spustit následující skript v PowerShellu:

```powershell
# 1. Pripojeni k Azure
az login

# 2. Vytvoreni Azure SQL Serveru a DB v DTU modu (Basic) pro DEV
az sql server create --name sql-aisearch-dev --resource-group ai-search-rg-dev --location northeurope --admin-user sqladmin --admin-password "VaseBezpecneHeslo123!"
az sql server firewall-rule create --resource-group ai-search-rg-dev --server sql-aisearch-dev --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
az sql db create --resource-group ai-search-rg-dev --server sql-aisearch-dev --name sqldb-dolphin-dev --service-objective Basic

# 3. Vytvoreni Storage Accountu a Kontejneru pro DEV
az storage account create --name staisearchdev --resource-group ai-search-rg-dev --location northeurope --sku Standard_LRS
$connStr = (az storage account show-connection-string --name staisearchdev --resource-group ai-search-rg-dev --query connectionString --output tsv)
az storage container create --name dolphin-originals-dev --connection-string $connStr
az storage container create --name dolphin-artifacts-dev --connection-string $connStr

# 4. Spusteni nasazeni Backendu z projektu
.\deploy_backend.ps1 -Client dolphin -Environment dev -ResourceGroup ai-search-rg-dev
```

---

## 📋 Zpětná vazba pro Konfiguraci Aplikace (`.env.dev` / `.env.prod`)

Po vytvoření doplňte příslušné hodnoty do vašeho `.env.dev` nebo `.env.prod`:

```ini
AZURE_SQL_HOST=sql-aisearch-dev.database.windows.net
AZURE_SQL_PORT=1433
AZURE_SQL_DB=sqldb-dolphin-dev
AZURE_SQL_USER=sqladmin
AZURE_SQL_PASSWORD=VaseZadanéHeslo
AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server
AZURE_BLOB_CONTAINER_ORIGINALS=dolphin-originals-dev
```
