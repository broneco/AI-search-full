# Azure Container Apps Automated Deployment Script for Backend
# Usage: powershell -ExecutionPolicy Bypass -File .\deploy_backend.ps1

param (
    [string]$ResourceGroup = "DOLPHIN_DS",
    [string]$RegistryName = "dolphinds",
    [string]$ContainerAppName = "dolphin-ai-search-backend",
    [string]$Location = "northeurope"
)

$ErrorActionPreference = "Stop"

# Write colored messages helper
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

Write-Header "Dolphin AI Search - Automated Backend Deployment"
Write-Info "Resource Group:      $ResourceGroup"
Write-Info "Container Registry:  $RegistryName"
Write-Info "Container App:       $ContainerAppName"

# 1. Verify Azure CLI is installed
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Error "Azure CLI (az) was not found on your system. Please install it from https://aka.ms/installazurecliwindows first."
}

# 2. Check if logged in to Azure
Write-Info "Checking Azure login status..."
$azAccount = az account show --query name --output tsv 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($azAccount)) {
    Write-WarningMsg "You are not logged in to Azure CLI or your token expired. Launching login screen..."
    az login
    $azAccount = az account show --query name --output tsv
}
Write-Success "Logged in to Azure. Active Subscription: $azAccount"

# 3. Retrieve ACR Login Server dynamically
Write-Info "Querying Container Registry server URL..."
$RegistryServer = az acr show --name $RegistryName --resource-group $ResourceGroup --query loginServer --output tsv
if ([string]::IsNullOrEmpty($RegistryServer)) {
    Write-Error "Failed to retrieve Login Server for registry: $RegistryName in resource group $ResourceGroup"
}
Write-Success "Found Registry Server: $RegistryServer"

# 4. Generate timestamp-based image version tag to prevent conflicts
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ImageTag = "v-$Timestamp"
Write-Info "Generated Image Version Tag: $ImageTag"

# 5. Build Docker Image in the cloud via Azure ACR Tasks
# This uploads source code to ACR and builds it on Azure, bypassing local Docker Desktop dependencies.
Write-Header "[1/3] Sestavuji Docker image v cloudu pres Azure ACR Tasks..."
Write-Info "Zahajuji cloud build. Zdrojove soubory se zabali a odeslou na Azure..."

az acr build --registry $RegistryName --resource-group $ResourceGroup `
  --image "${ContainerAppName}:${ImageTag}" `
  --image "${ContainerAppName}:latest" .

if ($LASTEXITCODE -ne 0) {
    Write-Error "ACR Build failed."
}
Write-Success "Docker image successfully built in ACR: ${RegistryServer}/${ContainerAppName}:${ImageTag}"

# 6. Update Container App to pull the new version
Write-Header "[2/3] Nasazuji novou verzi do Azure Container App..."
Write-Info "Provadim rolling update Container App '$ContainerAppName'..."

az containerapp update --resource-group $ResourceGroup --name $ContainerAppName `
  --image "${RegistryServer}/${ContainerAppName}:${ImageTag}"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container App update failed."
}
Write-Success "Container App updated successfully!"

# 7. Configure CORS to allow any origin (required for frontend SWA/local connections)
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
Write-Header "Nasazeni backendu dokoncelo!"
Write-Success "Aplikace bezi na adrese: https://$AppUrl"
Write-Info "Pro sledovani zivych logu v realnem case spust:"
Write-Host "az containerapp logs show --resource-group $ResourceGroup --name $ContainerAppName --follow" -ForegroundColor DarkCyan
Write-Host ""
