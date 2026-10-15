# Parameterized Azure CLI Infrastructure Provisioning Script
# Usage:
#   Set AZURE_SQL_PASSWORD securely, then run .\infra\create_azure_resources.ps1 -Client showcase -Environment dev -Location northeurope

param (
    [string]$Client = "showcase",
    [string]$Environment = "dev",
    [string]$Location = "northeurope",
    [string]$SqlAdminUser = "sqladmin",
    [string]$SqlPassword = $env:AZURE_SQL_PASSWORD
)

if ([string]::IsNullOrWhiteSpace($SqlPassword)) {
    throw "Provide -SqlPassword or set AZURE_SQL_PASSWORD securely before provisioning."
}

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()

# Map default Naming Conventions
$ResourceGroup = "ai-search-$ClientClean-rg-$EnvClean"
$SqlServerName = "ai-search-$ClientClean-sql-$EnvClean"
$SqlDbName = "ai-search-$ClientClean-sqldb-$EnvClean"
$StorageAccountName = "aisearch${ClientClean}st${EnvClean}"
$AcrName = "aisearch${ClientClean}cr${EnvClean}"
$AiFoundryName = "ai-search-$ClientClean-aif-$EnvClean"
$ContainerEnvName = "ai-search-$ClientClean-cae-$EnvClean"
$ContainerAppName = "ai-search-$ClientClean-ca-$EnvClean"
$SwaUser = "ai-search-$ClientClean-swa-user-$EnvClean"
$SwaAdmin = "ai-search-$ClientClean-swa-admin-$EnvClean"
$OriginalsContainer = "$ClientClean-originals-$EnvClean"
$ArtifactsContainer = "$ClientClean-artifacts-$EnvClean"

function Write-Header ($msg) {
    Write-Host ""
    Write-Host "==== $msg ====" -ForegroundColor Cyan
}

function Write-Success ($msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Write-Info ($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor White
}

function Write-WarningMsg ($msg) {
    Write-Host "[WARNING] $msg" -ForegroundColor Yellow
}

Write-Header "AI Search - Automated Azure Resource Provisioning CLI"
Write-Info "Client / Tenant:         $ClientClean"
Write-Info "Environment:             $EnvClean"
Write-Info "Location:                $Location"
Write-Info "Resource Group:          $ResourceGroup"
Write-Info "Azure SQL Server:        $SqlServerName"
Write-Info "Azure SQL Database:      $SqlDbName"
Write-Info "Storage Account:         $StorageAccountName"
Write-Info "Container Registry:      $AcrName"
Write-Info "Azure AI Foundry:        $AiFoundryName"
Write-Info "Container Apps Env:      $ContainerEnvName"
Write-Info "Container App:           $ContainerAppName"
Write-Info "Static Web App (User):   $SwaUser"
Write-Info "Static Web App (Admin):  $SwaAdmin"

# 1. Check Azure Login
Write-Header "[1/7] Kontrola prihlaseni k Azure CLI..."
$azAccount = (az account show --query name --output tsv 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($azAccount)) {
    Write-WarningMsg "Nejste prihlaseni k Azure CLI. Spoustam az login..."
    az login
    $azAccount = (az account show --query name --output tsv)
}
Write-Success "Prihlaseno k Azure. Aktivni Subscription: $azAccount"

# 2. Create Resource Group
Write-Header "[2/7] Vytvarim Resource Group '$ResourceGroup'..."
az group create --name $ResourceGroup --location $Location --output table
Write-Success "Resource Group '$ResourceGroup' vytvorena."

# 3. Create Azure SQL Server and Database in DTU Mode (Basic 5 DTU)
Write-Header "[3/7] Vytvarim Azure SQL Server a Databazi v DTU modu..."
az sql server create --name $SqlServerName --resource-group $ResourceGroup --location $Location --admin-user $SqlAdminUser --admin-password $SqlPassword --output table
az sql server firewall-rule create --resource-group $ResourceGroup --server $SqlServerName --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output table
az sql db create --resource-group $ResourceGroup --server $SqlServerName --name $SqlDbName --service-objective Basic --output table
Write-Success "Azure SQL DB '$SqlDbName' (Basic DTU) vytvorena."

# 4. Create Storage Account and Blob Containers
Write-Header "[4/7] Vytvarim Storage Account '$StorageAccountName' a kontejnery..."
az storage account create --name $StorageAccountName --resource-group $ResourceGroup --location $Location --sku Standard_LRS --output table
$connStr = (az storage account show-connection-string --name $StorageAccountName --resource-group $ResourceGroup --query connectionString --output tsv)
az storage container create --name $OriginalsContainer --connection-string $connStr --output table
az storage container create --name $ArtifactsContainer --connection-string $connStr --output table
Write-Success "Storage Account '$StorageAccountName' a kontejnery byly vytvoreny."

# 5. Create Azure Container Registry (ACR)
Write-Header "[5/7] Vytvarim Azure Container Registry '$AcrName'..."
az acr create --name $AcrName --resource-group $ResourceGroup --sku Basic --admin-enabled true --output table
Write-Success "Azure Container Registry '$AcrName' s admin pravy vytvorena."

# 6. Create Azure AI Foundry Project
Write-Header "[6/7] Vytvarim Azure AI Foundry Project '$AiFoundryName'..."
az cognitiveservices account create --name $AiFoundryName --resource-group $ResourceGroup --location $Location --kind OpenAI --sku S0 --output table
Write-Success "Azure AI Foundry Project '$AiFoundryName' vytvoren."

# 7. Create Container Apps Environment & App Placeholder, and Static Web Apps
Write-Header "[7/7] Vytvarim Container Apps Environment, App placeholder a Static Web Apps..."
az containerapp env create --name $ContainerEnvName --resource-group $ResourceGroup --location $Location --output table

$AcrServer = (az acr show --name $AcrName --resource-group $ResourceGroup --query loginServer --output tsv)
$AcrUser = (az acr credential show --name $AcrName --query username --output tsv)
$AcrPass = (az acr credential show --name $AcrName --query "passwords[0].value" --output tsv)

az containerapp create `
  --resource-group $ResourceGroup `
  --name $ContainerAppName `
  --environment $ContainerEnvName `
  --image mcr.microsoft.com/azuredocs/aci-helloworld `
  --target-port 8000 `
  --ingress external `
  --registry-server $AcrServer `
  --registry-username $AcrUser `
  --registry-password $AcrPass `
  --output table

az staticwebapp create --name $SwaUser --resource-group $ResourceGroup --location westeurope --sku Free --output table
az staticwebapp create --name $SwaAdmin --resource-group $ResourceGroup --location westeurope --sku Free --output table

Write-Header "PROVISIONING DOKONCEN PRO TENANT '$ClientClean' ($EnvClean)!"
Write-Success "Vsechny Azure zdroje v '$ResourceGroup' byly uspesne zalozeny."
Write-Info "Nyni muzete spustit nasazeni kodu pomoci:"
Write-Host ".\deploy_all.ps1 -Client $ClientClean -Environment $EnvClean" -ForegroundColor DarkCyan
