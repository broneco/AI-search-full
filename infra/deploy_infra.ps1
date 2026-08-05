# One-Command Client Infrastructure Provisioning Script (Azure Bicep)
# Usage:
#   .\infra\deploy_infra.ps1 -Client dolphin -Environment dev
#   .\infra\deploy_infra.ps1 -Client university -Environment prod -ResourceGroup "UNIVERSITY_RG"

param (
    [string]$Client = "dolphin",
    [string]$Environment = "dev",
    [string]$ResourceGroup = "DOLPHIN_DS",
    [string]$Location = "northeurope",
    [string]$ParameterFile = "infra/main.bicepparam"
)

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()

Write-Host ""
Write-Host "==== Dolphin AI Search - Client Infrastructure Provisioning ====" -ForegroundColor Cyan
Write-Host "[INFO] Client:          $ClientClean" -ForegroundColor White
Write-Host "[INFO] Environment:     $EnvClean" -ForegroundColor White
Write-Host "[INFO] Resource Group:  $ResourceGroup" -ForegroundColor White
Write-Host "[INFO] Bicep Template:  infra/main.bicep" -ForegroundColor White

# 1. Verify Azure CLI is installed
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Error "Azure CLI (az) was not found on your system. Please install it from https://aka.ms/installazurecliwindows first."
    exit 1
}

# 2. Check if logged in to Azure
Write-Host "[INFO] Checking Azure login status..." -ForegroundColor White
$azAccount = (az account show --query name --output tsv 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($azAccount)) {
    Write-Host "[WARNING] You are not logged in to Azure CLI. Launching login..." -ForegroundColor Yellow
    az login
    $azAccount = (az account show --query name --output tsv)
}
Write-Host "[OK] Logged in to Azure. Subscription: $azAccount" -ForegroundColor Green

# 3. Create Resource Group if it doesn't exist
Write-Host "[1/2] Overuju existenci Resource Group '$ResourceGroup'..." -ForegroundColor Yellow
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Host "[INFO] Vytvarim novou Resource Group '$ResourceGroup' v regionu '$Location'..." -ForegroundColor White
    az group create --name $ResourceGroup --location $Location
}

# 4. Execute Bicep Infrastructure Deployment
$DeploymentName = "deploy-${ClientClean}-${EnvClean}-$(Get-Date -Format 'yyyyMMdd-HHmm')"
Write-Host "[2/2] Spoustim Bicep nasazeni '$DeploymentName'..." -ForegroundColor Yellow

az deployment group create `
  --name $DeploymentName `
  --resource-group $ResourceGroup `
  --template-file infra/main.bicep `
  --parameters clientName=$ClientClean environment=$EnvClean location=$Location

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==== Nasazeni infrastruktury pro klienta $ClientClean ($EnvClean) dokoncelo! ====" -ForegroundColor Green
} else {
    Write-Error "Nasazeni infrastruktury selhalo. Zkontrolujte vystup Azure CLI."
}
