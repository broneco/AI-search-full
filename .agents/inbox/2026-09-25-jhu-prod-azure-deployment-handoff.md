# Azure Resource & Deployment Handoff: JHU Produkční Prostředí (ju-ai-search-rg-prod)

- Status: completed
- Created: 2026-09-25
- Tenant: `ju` (JHU Client)
- Environment: `prod`
- Target Resource Group: `ju-ai-search-rg-prod`

---

## 🎯 Architektura a Odpojení Konfigurace od Kódu

Aplikace je navržena podle principu **strict multi-tenant separation**:
- Kód v repozitáři je **100% agnostický** (stejný kód běží pro všechny klienty).
- Specifická konfigurace a klíče pro JHU Produkci jsou uloženy v vyhrazeném souboru **`.env.ju-prod`**.
- Skripty pro nasazení (`deploy_all.ps1`, `deploy_backend.ps1`, `deploy_frontend.ps1`) dynamicky zohledňují parametry `-Client ju -Environment prod`.

---

## 📋 Přehled Založených Zdrojů v Azure pro JHU Produkci

Všechny zdroje byly v Azure Portálu úspěšně vytvořeny v Resource Group `ju-ai-search-rg-prod`:

| Typ zdroje pro aplikaci | Název Zdroje pro JHU | Účel zdroje |
| :--- | :--- | :--- |
| **Resource Group** | `ju-ai-search-rg-prod` | Kontejner pro JHU produkční zdroje |
| **Azure SQL Database Server** | `ju-ai-search-sql-prod` | Produkční databázový server MS SQL |
| **Azure SQL Database** | `ju-ai-search-sqldb-prod` | Produkční databáze pasáží, vektorů a relací |
| **Storage Account** | `juaisearchstprod` | Úložiště pro nahrávaná PDF a mezipaměť |
| **Azure Container Registry** | `juaisearchcrprod` | Úložiště pro Docker image backendu |
| **Container Apps Environment** | `ju-ai-search-cae2-prod` | Běhové prostředí pro backend kontajner |
| **Container App (Backend)** | `ju-ai-search-ca-prod` | FastAPI RAG backend aplikace |
| **Static Web App (User)** | `ju-ai-search-swa-user-prod` | Uživatelský vyhledávací frontend pro JHU |
| **Static Web App (Admin)** | `ju-ai-search-swa-admin-prod` | Administrační frontend konzole pro JHU |
| **Azure AI Foundry Project** | `ju-ai-search-aif-prod` / `ju-proj-default-prod` | Azure AI Foundry (LLM GPT-5.4-mini & Embeddings) |
| **Key Vault** | `ju-ai-search-kv-prod` | Trezor klíčů a certifikátů |
| **Log Analytics Workspace** | `workspacejuaisearchrgproda964` | Observabilita a logování |

---

## 🚀 Nasazení Aplikace pro JHU Produkci (1 Příkaz)

Pro kompletní sestavení a nasazení backendu i obou frontendů pro JHU Produkci stačí spustit z PowerShellu:

```powershell
.\deploy_all.ps1 -Client ju -Environment prod
```

### Nebo po jednotlivých částech:

```powershell
# 1. Nasazení Backendu do ju-ai-search-ca-prod a naplnění DB
.\deploy_backend.ps1 -Client ju -Environment prod

# 2. Nasazení Uživatelského Frontendu do ju-ai-search-swa-user-prod
.\deploy_frontend.ps1 -Client ju -Environment prod -AppType user

# 3. Nasazení Administračního Frontendu do ju-ai-search-swa-admin-prod
.\deploy_frontend.ps1 -Client ju -Environment prod -AppType admin
```

---

## 🔄 Postup Přenesení Repozitáře na Interní Git Server

Až budete přenášet repozitář na interní Git server (např. Azure DevOps / GitLab / Bitbucket):

1. **Práce s Git Remotes**:
   Nechte stávající kód čistý bez secrets a přidejte novou vzdálenou adresu interního serveru:
   ```bash
   git remote add internal https://vashost.internal/ai-search-full.git
   git push internal --all
   git push internal --tags
   ```

2. **Ochrana Tajných Klíčů (Secrets)**:
   - Soubor `.env.ju-prod` obsahuje produkční přístupová hesla a API klíče.
   - Soubory `.env.*` jsou v `.gitignore` a zůstávají bezpečně uloženy mimo veřejný Git.
   - V interním Git CI/CD (Azure Pipelines / GitLab CI) se tyto proměnné nastaví v konfiguračních proměnných pipeline (Variable Groups / Secrets).
