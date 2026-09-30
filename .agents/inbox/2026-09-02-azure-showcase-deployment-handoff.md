# Azure Deployment Handoff: Vyhrazené Showcase Prostředí (ai-search-showcase-rg-dev)

- Status: pending_human_action
- Created: 2026-09-02
- Updated: 2026-09-03
- Related task: Dedicated Isolated Showcase Tenant Environment Setup & Non-Admin IT Provisioning Model
- Target Resource Group: `ai-search-showcase-rg-dev`
- Related ADR: ADR-0017-azure-sql-dtu-model-and-resource-group-architecture.md

---

## 🎯 Cíl Hand-offu a Model Fyzického Oddělení Ról

Tento dokument představuje **kompletní příručku pro IT Administrátory a Vývojáře**. 

Funguje na principu **oddělení správcovských práv (Non-Admin Developer Model)**:
1. **IT Administrátor klienta** (s plnými právy k Subscription) vytvoří podle tohoto návodu potřebnou infrastrukturu v Azure Portálu.
2. **Vývojář / Operátor** (s běžnými Contributor/Deployer právy) pak spouští pouze skripty `deploy_backend.ps1` a `deploy_frontend.ps1`, které aktualizují kód a image bez nutnosti mít zakládací administrátorská práva v Azure.

---

## 📋 Přehled Všech Zdroje Potřebných pro Provoz Showcase

Pro provoz vyhledávače v prostředí **`ai-search-showcase-rg-dev`** založte **těchto 8 zdrojů**:

| Typ zdroje pro aplikaci | Klíč | Název zdroje pro Showcase | Účel zdroje |
| :--- | :--- | :--- | :--- |
| **Resource Group** | `rg` | `ai-search-showcase-rg-dev` | Kontejner pro Showcase zdroje |
| **Azure SQL Database Server** | `sql` | `ai-search-showcase-sql-dev` | Databázový server MS SQL |
| **Azure SQL Database (DTU)** | `sqldb` | `ai-search-showcase-sqldb-dev` | Databáze pasáží, vektorů a relací |
| **Storage Account** | `st` | `aisearchshowcasestdev` *(bez pomlček)* | Úložiště pro nahrávaná PDF a mezipaměť |
| **Azure Container Registry** | `cr` | `aisearchshowcasecrdev` *(bez pomlček)* | Úložiště pro Docker image backendu |
| **Azure AI Foundry Project** | `aif` / `oai` | `ai-search-showcase-aif-dev` | LLM modely (GPT-5.4-mini & Embeddings) |
| **Container Apps Environment** | `cae` | `ai-search-showcase-cae-dev` | Běhové prostředí pro backend kontajner |
| **Container App (Backend)** | `ca` | `ai-search-showcase-ca-dev` | FastAPI RAG backend aplikace |
| **Static Web App (User)** | `swa` | `ai-search-showcase-swa-user-dev` | Uživatelský vyhledávací frontend |
| **Static Web App (Admin)** | `swa` | `ai-search-showcase-swa-admin-dev` | Administrační frontend konzole |

---

## 🛠️ Postup Ručního Založení v Azure Portálu (Pro IT Admina)

### 1. Vytvoření Azure SQL Serveru a Databáze (DTU Mód)
1. V Azure Portálu vytvořte **SQL Database** v RG `ai-search-showcase-rg-dev`.
2. **Database Name:** `ai-search-showcase-sqldb-dev`.
3. **Server:** Nový `ai-search-showcase-sql-dev` (`sqladmin` + heslo, volitelně povolit Entra ID).
4. **Compute + storage:** Zvolte **DTU-based purchasing model** -> **Basic (5 DTU)** nebo **Standard S0 (10 DTU)**.
5. **Networking:** Nastavte **Public endpoint**, **Allow Azure services:** `Yes`, **Add current client IP:** `Yes`.

---

### 2. Vytvoření Storage Accountu a Kontejnerů
1. V `ai-search-showcase-rg-dev` vytvořte **Storage Account**: `aisearchshowcasestdev` (Standard, LRS).
2. Otevřete `aisearchshowcasestdev` -> **Containers** -> vytvořte dva kontejnery:
   - `showcase-originals-dev` (pro nahrávaná PDF)
   - `showcase-artifacts-dev` (pro mezipaměť a výstupy)

---

### 3. Vytvoření Azure Container Registry (ACR)
1. V `ai-search-showcase-rg-dev` vytvořte **Container Registry**: `aisearchshowcasecrdev` (Basic).
2. Otevřete `aisearchshowcasecrdev` -> **Access keys** -> přepněte **Admin user** na `Enabled`.

---

### 4. Vytvoření Azure AI Foundry Project a Nasazení Modelů (`aif`)
1. V Azure Portálu vyhledejte **Azure AI Foundry** (nebo Azure AI Services).
2. Vytvořte nový **Azure AI Foundry Hub / Project**:
   - **Project Name:** `ai-search-showcase-aif-dev`
   - **Resource Group:** `ai-search-showcase-rg-dev`
   - **Region:** `Swedencentral` / `Northeurope` / `Westeurope`
3. Otevřete AI Foundry Portal -> **Deployments** -> vytvořte 2 nasazení (Model Deployments):
   - **Chat Model Deployment**: Název = `gpt-5.4-mini` (nebo `gpt-4o-mini`), Model = `gpt-4o-mini` / `gpt-5.4-mini`
   - **Embedding Model Deployment**: Název = `text-embedding-3-large`, Model = `text-embedding-3-large`
4. Zkopírujte **Endpoint URL** a **API Key** pro konfigurační soubor `.env.dev`.

---

### 5. Vytvoření Container Apps Environment a Placeholderu Backendu (`cae` & `ca`)
1. Vyhledejte v Azure **Container Apps Environment** -> **Create**:
   - **Environment Name:** `ai-search-showcase-cae-dev`
   - **Resource Group:** `ai-search-showcase-rg-dev`
2. Vytvořte **Container App**:
   - **Container App Name:** `ai-search-showcase-ca-dev`
   - **Environment:** `ai-search-showcase-cae-dev`
   - **Ingress:** Enabled, External access, Target port: `8000`.

---

### 6. Vytvoření Static Web Apps (`swa`)
1. Vyhledejte v Azure **Static Web Apps** -> **Create**:
   - **Name pro uživatele:** `ai-search-showcase-swa-user-dev` (Plan: Free, Region: West Europe).
2. Vytvořte druhou Static Web App:
   - **Name pro administraci:** `ai-search-showcase-swa-admin-dev` (Plan: Free, Region: West Europe).

---

## ⚡ Příkaz pro Jednorázové Založení Kompletní Infrastruktury v Azure CLI

Pokud má zakládající správce přístup k Azure CLI, může kompletní sadu zdrojů vytvořit spuštěním:

```powershell
az login

# 1. Resource Group
az group create --name ai-search-showcase-rg-dev --location northeurope

# 2. Azure SQL Server + DB v DTU modu
az sql server create --name ai-search-showcase-sql-dev --resource-group ai-search-showcase-rg-dev --location northeurope --admin-user sqladmin --admin-password "VaseBezpecneHeslo123!"
az sql server firewall-rule create --resource-group ai-search-showcase-rg-dev --server ai-search-showcase-sql-dev --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
az sql db create --resource-group ai-search-showcase-rg-dev --server ai-search-showcase-sql-dev --name ai-search-showcase-sqldb-dev --service-objective Basic

# 3. Storage Account & Blob Kontejnery
az storage account create --name aisearchshowcasestdev --resource-group ai-search-showcase-rg-dev --location northeurope --sku Standard_LRS
$connStr = (az storage account show-connection-string --name aisearchshowcasestdev --resource-group ai-search-showcase-rg-dev --query connectionString --output tsv)
az storage container create --name showcase-originals-dev --connection-string $connStr
az storage container create --name showcase-artifacts-dev --connection-string $connStr

# 4. Container Registry (ACR)
az acr create --name aisearchshowcasecrdev --resource-group ai-search-showcase-rg-dev --sku Basic --admin-enabled true

# 5. Azure AI Foundry Project
az cognitiveservices account create --name ai-search-showcase-aif-dev --resource-group ai-search-showcase-rg-dev --location swedencentral --kind OpenAI --sku S0

# 6. Container Apps Environment & App Placeholder
az containerapp env create --name ai-search-showcase-cae-dev --resource-group ai-search-showcase-rg-dev --location northeurope
az containerapp create --name ai-search-showcase-ca-dev --resource-group ai-search-showcase-rg-dev --environment ai-search-showcase-cae-dev --image mcr.microsoft.com/azuredocs/aci-helloworld --target-port 8000 --ingress external

# 7. Static Web Apps (User & Admin)
az staticwebapp create --name ai-search-showcase-swa-user-dev --resource-group ai-search-showcase-rg-dev --location westeurope --sku Free
az staticwebapp create --name ai-search-showcase-swa-admin-dev --resource-group ai-search-showcase-rg-dev --location westeurope --sku Free
```

---

## 🚀 Nasazení Kódu Vývojářem (Non-Admin Model)

Jakmile jsou zdroje v Azure vytvořeny, vývojář (bez nutnosti mít admin práva v Azure) spouští ze svého počítače běžné nasazovací skripty:

```powershell
# Nasazeni Backendu (Sestaveni Docker image v cloudu pres ACR a aktualizace Container App)
.\deploy_backend.ps1 -Client showcase -Environment dev

# Nasazeni Uzivatelskeho Frontendu (SWA v0.1.1)
.\deploy_frontend.ps1 -Client showcase -Environment dev -AppType user

# Nasazeni Administracniho Frontendu (SWA v0.1.1)
.\deploy_frontend.ps1 -Client showcase -Environment dev -AppType admin
```

---

## 🔑 Klíče pro Konfigurační Soubor Aplikace (`.env.dev`)

```ini
APP_ENV=dev
TENANT_ID=showcase-dev
AZURE_SQL_HOST=ai-search-showcase-sql-dev.database.windows.net
AZURE_SQL_PORT=1433
AZURE_SQL_DB=ai-search-showcase-sqldb-dev
AZURE_SQL_USER=sqladmin
AZURE_SQL_PASSWORD=VaseZadaneHeslo123!
AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server
AZURE_STORAGE_ACCOUNT=aisearchshowcasestdev
AZURE_BLOB_CONTAINER_ORIGINALS=showcase-originals-dev
AZURE_OPENAI_ENDPOINT=https://ai-search-showcase-aif-dev.openai.azure.com/
AZURE_OPENAI_API_KEY=VášKlíčZFoundry
AZURE_OPENAI_FLASH_DEPLOYMENT=gpt-5.4-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```
