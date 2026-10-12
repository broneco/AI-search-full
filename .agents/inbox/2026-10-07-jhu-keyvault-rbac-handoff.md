# Azure Deployment Handoff: JHU Tenant PROD Key Vault RBAC Role Assignment & Secrets Setup

- Status: waiting-for-human
- Created: 2026-10-07
- Related task: Azure Container App deployment & Key Vault Managed Identity RBAC setup for JHU (PROD)
- Related tenant: `ju` (PROD)
- Container App: `ju-ai-search-ca-prod`
- Container App Managed Identity Object ID: `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`
- Key Vault Name: `ju-ai-search-kv-prod` (or `ju-ais-kv-prod`)

## Summary of Completed Deployment

1. **Docker Container Image**: Succeeded and built in Azure Container Registry (`juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod:latest`).
2. **Container App Created & Live**: App `ju-ai-search-ca-prod` is fully provisioned and running at:
   `https://ju-ai-search-ca-prod.mangosky-3e5a7049.swedencentral.azurecontainerapps.io`
3. **System-Assigned Managed Identity**: Successfully enabled for `ju-ai-search-ca-prod`.
   - **Identity Type**: `SystemAssigned`
   - **Principal ID (Object ID)**: `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`

---

## Action Required by Azure Administrator / Owner

Because user accounts with `Contributor` permissions cannot assign Azure RBAC roles (`Microsoft.Authorization/roleAssignments/write`), an Azure Administrator or Owner of the Key Vault must perform the following two steps.

### Step 1: Assign `Key Vault Secrets User` Role in Azure Portal

#### Czech Interface (České rozhraní):
1. Otevřete [Azure Portal](https://portal.azure.com/) a přejděte do vaší **Resource Group**: `ju-ai-search-rg-prod`.
2. Otevřete váš **Trezor klíčů (Key Vault)**: `ju-ai-search-kv-prod`.
3. V levé nabídce klikněte na **Řízení přístupu (IAM)**.
4. Klikněte na tlačítko **+ Přidat** -> **Přidat přiřazení role**.
5. Vyberte roli: **Uživatel secretů trezoru klíčů** (*Key Vault Secrets User*).
6. Na záložce *Členové* vyberte: **Přiřadit přístup pro -> Spravovaná identita**.
7. Klikněte na **+ Vybrat členy**, v rozevírací nabídce *Spravovaná identita* zvolte **Aplikace služeb Container App** a vyberte `ju-ai-search-ca-prod` (Object ID: `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`).
8. Klikněte na **Kontrola a přiřazení** pro uložení.

#### English Interface:
1. Open [Azure Portal](https://portal.azure.com/) and navigate to **Resource Group**: `ju-ai-search-rg-prod`.
2. Open your **Key Vault**: `ju-ai-search-kv-prod`.
3. Select **Access control (IAM)** from the left menu.
4. Click **+ Add** -> **Add role assignment**.
5. Select role: **Key Vault Secrets User**.
6. On the *Members* tab, select **Assign access to -> Managed identity**.
7. Click **+ Select members**, choose **Container App** managed identity type, and select `ju-ai-search-ca-prod` (Object ID: `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`).
8. Click **Review + assign**.

#### CLI Alternative (if run by an Azure Subscription Owner):
```powershell
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee-object-id "ccacbf26-dcd6-4f7b-af7b-e3e769137de8" `
  --assignee-principal-type ServicePrincipal `
  --scope "/subscriptions/24e4a9a6-bab0-43f7-ba20-3b774704fade/resourceGroups/ju-ai-search-rg-prod/providers/Microsoft.KeyVault/vaults/ju-ai-search-kv-prod"
```

---

### Step 2: Populate Required Secrets in Key Vault (`ju-ai-search-kv-prod`)

Please ensure the following secrets are created in `ju-ai-search-kv-prod`:

| Secret Name in Key Vault | Secret Purpose | Value to Store |
|---|---|---|
| `ju-ai-search-sql-sqlaccount-password-prod` | Azure SQL Admin Password | Password for `ju-ai-search-sql-prod.database.windows.net` |
| `ju-ai-search-openai-api-key-prod` | Azure OpenAI / AI Foundry API Key | API Key for `ju-ai-search-aif-prod` |
| `ju-ai-search-storage-connection-string-prod` | Azure Blob Storage Connection String | Connection string for storage account `juaisearchstprod` |
| `ju-ai-search-postgres-password-prod` | Azure PostgreSQL Password | Password for PostgreSQL Flexible Server |

---

## Verification Command

After assigning the role and setting secret values, verify in Azure CLI or Container App logs:

```powershell
# Show active Container App live logs
az containerapp logs show --resource-group ju-ai-search-rg-prod --name ju-ai-search-ca-prod --follow
```
