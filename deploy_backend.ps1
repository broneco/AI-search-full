# Azure Container Apps Automated Deployment Script for Backend
# Usage:
#   .\deploy_backend.ps1 -Client dolphin -Environment dev
#   .\deploy_backend.ps1 -Client dolphin -Environment prod
#   .\deploy_backend.ps1 -Client showcase -Environment dev -ResourceGroup "ai-search-showcase-rg-dev"

param (
    [string]$Client = "dolphin",
    [string]$Environment = "dev",
    [string]$ResourceGroup = "",
    [string]$RegistryName = "",
    [string]$ContainerEnvName = "",
    [string]$Location = "northeurope"
)

$ErrorActionPreference = "Continue"
$env:AZURE_CORE_ONLY_SHOW_ERRORS = "true"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()

# Map default Resource Group if not provided
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    if ($ClientClean -eq "showcase") {
        $ResourceGroup = "ai-search-showcase-rg-dev"
    } elseif ($EnvClean -eq "prod") {
        $ResourceGroup = "ai-search-rg-prod"
    } else {
        $ResourceGroup = "ai-search-rg-dev"
    }
}

if ([string]::IsNullOrWhiteSpace($RegistryName)) {
    $RegistryName = "craisearch$EnvClean"
}

if ([string]::IsNullOrWhiteSpace($ContainerEnvName)) {
    $ContainerEnvName = "cae-aisearch-$EnvClean"
}

$ContainerAppName = "ca-aisearch-$ClientClean-$EnvClean"
$SqlDbName = "sqldb-$ClientClean-$EnvClean"
$SqlServerHost = "sql-aisearch-$EnvClean.database.windows.net"
$BlobOriginalsContainer = "$ClientClean-originals-$EnvClean"

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

Write-Header "AI Search - Automated Multi-Environment Backend Deployment"
Write-Info "Client:              $ClientClean"
Write-Info "Environment:         $EnvClean"
Write-Info "Container App:       $ContainerAppName"
Write-Info "SQL Host Target:     $SqlServerHost"
Write-Info "SQL DB Target:       $SqlDbName"
Write-Info "Blob Container:      $BlobOriginalsContainer"
Write-Info "Resource Group:      $ResourceGroup"

# 1. Verify Azure CLI is installed
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Error "Azure CLI (az) was not found on your system. Please install it from https://aka.ms/installazurecliwindows first."
    exit 1
}

# 2. Check if logged in to Azure
Write-Info "Checking Azure login status..."
$azAccount = (az account show --query name --output tsv 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($azAccount)) {
    Write-WarningMsg "You are not logged in to Azure CLI or your token expired. Launching login screen..."
    az login
    $azAccount = (az account show --query name --output tsv)
}
Write-Success "Logged in to Azure. Active Subscription: $azAccount"

# 3. Retrieve ACR Login Server and Credentials dynamically
Write-Info "Querying Container Registry server URL and credentials..."
$RegistryServer = (az acr show --name $RegistryName --resource-group $ResourceGroup --query loginServer --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($RegistryServer)) {
    Write-WarningMsg "Registry $RegistryName not found in $ResourceGroup. Attempting global search..."
    $RegistryServer = (az acr show --name $RegistryName --query loginServer --output tsv 2>$null)
}

if ([string]::IsNullOrWhiteSpace($RegistryServer)) {
    Write-Error "Failed to retrieve Login Server for registry: $RegistryName"
    exit 1
}

$AcrUser = (az acr credential show --name $RegistryName --query username --output tsv 2>$null)
$AcrPass = (az acr credential show --name $RegistryName --query "passwords[0].value" --output tsv 2>$null)

Write-Success "Found Registry Server: $RegistryServer"

# 4. Generate timestamp-based image version tag to prevent conflicts
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ImageTag = "${EnvClean}-v-${Timestamp}"
Write-Info "Generated Image Version Tag: $ImageTag"

# 5. Build Docker Image in the cloud via Azure ACR Tasks
Write-Header "[1/3] Sestavuji Docker image v cloudu pres Azure ACR Tasks..."
az acr build --registry $RegistryName `
  --image "${ContainerAppName}:${ImageTag}" `
  --image "${ContainerAppName}:latest" . --no-logs

if ($LASTEXITCODE -ne 0) {
    Write-Error "ACR Build failed."
}
Write-Success "Docker image successfully built in ACR: ${RegistryServer}/${ContainerAppName}:${ImageTag}"

# 6. Check if Container App exists; Create if missing, Update if exists
Write-Header "[2/3] Nasazuji novou verzi a konfiguraci do Azure Container App..."
$appExists = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query name --output tsv 2>$null)

if ([string]::IsNullOrWhiteSpace($appExists)) {
    Write-Info "Container App '$ContainerAppName' dosud neexistuje. Vytvarim novou Container App..."
    az containerapp create `
      --resource-group $ResourceGroup `
      --name $ContainerAppName `
      --environment $ContainerEnvName `
      --image "${RegistryServer}/${ContainerAppName}:${ImageTag}" `
      --target-port 8000 `
      --ingress external `
      --min-replicas 1 `
      --max-replicas 3 `
      --registry-server $RegistryServer `
      --registry-username $AcrUser `
      --registry-password $AcrPass `
      --env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server"
} else {
    Write-Info "Container App '$ContainerAppName' jiz existuje. Provadim rolling update..."
    az containerapp update --resource-group $ResourceGroup --name $ContainerAppName `
      --image "${RegistryServer}/${ContainerAppName}:${ImageTag}" `
      --set-env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server"
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container App creation/update failed."
}
Write-Success "Container App updated successfully!"

# 7. Configure CORS to allow any origin
Write-Header "[3/3] Nastavuji CORS pravidla pro bezpecny pristup z frontendu..."
az containerapp ingress cors update `
  --resource-group $ResourceGroup `
  --name $ContainerAppName `
  --allowed-origins "*" `
  --allowed-methods "GET,POST,OPTIONS" `
  --allowed-headers "*" `
  --allow-credentials true

if ($LASTEXITCODE -ne 0) {
    Write-WarningMsg "CORS settings update encountered warnings."
} else {
    Write-Success "CORS allowed origins updated to '*'"
}

# 8. Retrieve FQDN and print summary
$AppUrl = az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query properties.configuration.ingress.fqdn --output tsv
Write-Header "Nasazeni backendu ($ClientClean / $EnvClean) dokonceno!"
Write-Success "Aplikace bezi na adrese: https://$AppUrl"

# 9. Optional Full Refresh Document Ingestion for Client Tenant
Write-Header "[4/4] Spusteni Full Refresh Ingestu pro tenant '$ClientClean' (pokud existuji podklady)..."
try {
    $IngestScript = "full_refresh_ingest.py"
    if (Test-Path $IngestScript) {
        Write-Info "Spustam ingestacni skript full_refresh_ingest.py pro tenant '$ClientClean'..."
        $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
        & $pythonCmd $IngestScript --tenant $ClientClean
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Full refresh ingest dokoncene uspesne pro tenant '$ClientClean'."
        } else {
            Write-WarningMsg "Ingestacni skript skoncil s kodem $LASTEXITCODE. Nasazeni aplikace pokracuje bez preruseni."
        }
    } else {
        Write-Info "Ingestacni skript $IngestScript nenalezen. Preskakuji automaticky ingest."
    }
} catch {
    Write-WarningMsg "Pri provadeni automatickeho ingestu doslo k vyjimce: $_. Nasazeni aplikace pokracuje bez preruseni."
}

Write-Info "Pro sledovani zivych logu v realnem case spust:"
Write-Host "az containerapp logs show --resource-group $ResourceGroup --name $ContainerAppName --follow" -ForegroundColor DarkCyan
Write-Host ""
