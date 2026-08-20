# Azure Automated Deployment Script for Frontend Applications
# Usage:
#   .\deploy_frontend.ps1 -Client dolphin -Environment dev -AppType user
#   .\deploy_frontend.ps1 -Client dolphin -Environment prod -AppType user -ClientTheme dolphin
#   .\deploy_frontend.ps1 -Client alzbeta -Environment prod -AppType user -ClientTheme alzbeta

param (
    [string]$Client = "dolphin",
    [string]$Environment = "dev",
    [string]$AppType = "user", # 'user' or 'admin'
    [string]$ClientTheme = "", # 'alzbeta' or 'dolphin' (defaults to $Client)
    [string]$ResourceGroup = "DOLPHIN_DS",
    [string]$BackendUrl = ""
)

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()
if ([string]::IsNullOrWhiteSpace($ClientTheme)) {
    $ClientTheme = $ClientClean
}
$ContainerAppName = "$ClientClean-ai-search-backend-$EnvClean"
$SwaName = if ($AppType -eq "admin") { "swa-$ClientClean-admin-$EnvClean" } else { "swa-$ClientClean-$EnvClean" }
$AppDir = if ($AppType -eq "admin") { "frontend-admin" } else { "frontend-user" }

# Determine Backend URL dynamically from Azure Container App if not specified
if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
    try {
        Write-Host "[INFO] Zistuji FQDN pro backend container '$ContainerAppName' v Azure..." -ForegroundColor White
        $Fqdn = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query properties.configuration.ingress.fqdn --output tsv 2>$null)
        if (-not [string]::IsNullOrWhiteSpace($Fqdn)) {
            $BackendUrl = "https://$Fqdn"
        }
    } catch {
        # Fallback to local or default if lookup fails
    }

    if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
        if ($EnvClean -eq "dev") {
            $BackendUrl = "http://localhost:8000"
        } else {
            $BackendUrl = "https://dolphin-ai-search-backend-dev.graysand-c9254ce4.northeurope.azurecontainerapps.io"
        }
    }
}

Write-Host ""
Write-Host "==== AI Search - Frontend Build & Deploy ($AppDir) ====" -ForegroundColor Cyan
Write-Host "[INFO] Client:       $ClientClean" -ForegroundColor White
Write-Host "[INFO] Environment:  $EnvClean" -ForegroundColor White
Write-Host "[INFO] App Type:     $AppType" -ForegroundColor White
Write-Host "[INFO] Client Theme: $ClientTheme" -ForegroundColor White
Write-Host "[INFO] Backend URL:  $BackendUrl" -ForegroundColor White
Write-Host "[INFO] SWA Target:   $SwaName" -ForegroundColor White

# Set environment variables for Next.js build
$env:NEXT_PUBLIC_BACKEND_URL = $BackendUrl
$env:NEXT_PUBLIC_CLIENT_THEME = $ClientTheme

Set-Location $AppDir

Write-Host "[1/2] Sestavuji produkcni build pro $AppDir ($ClientClean / $EnvClean)..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend build failed for $AppDir."
    Set-Location ..
    exit 1
}

Write-Host "[OK] Build uspesne dokoncen!" -ForegroundColor Green

# Retrieve deployment token from Azure Static Web App or create SWA if missing
Write-Host "[INFO] Zistuji deployment token pro Static Web App '$SwaName'..." -ForegroundColor White
$DeploymentToken = (az staticwebapp secrets list --name $SwaName --resource-group $ResourceGroup --query properties.apiKey --output tsv 2>$null)

if ([string]::IsNullOrWhiteSpace($DeploymentToken)) {
    Write-Host "[INFO] Static Web App '$SwaName' neexistuje, vytvarim v Azure..." -ForegroundColor Yellow
    az staticwebapp create --name $SwaName --resource-group $ResourceGroup --location westeurope --sku Free
    $DeploymentToken = (az staticwebapp secrets list --name $SwaName --resource-group $ResourceGroup --query properties.apiKey --output tsv 2>$null)
}

if (-not [string]::IsNullOrWhiteSpace($DeploymentToken)) {
    Write-Host "[2/2] Nasazuji frontend do Azure Static Web App ($SwaName)..." -ForegroundColor Yellow
    npx -y @azure/static-web-apps-cli deploy ./out --deployment-token $DeploymentToken --env production
    
    $SwaUrl = (az staticwebapp show --name $SwaName --resource-group $ResourceGroup --query defaultHostname --output tsv 2>$null)
    Write-Host ""
    Write-Host "[OK] Nasazeni frontendu dokonceno!" -ForegroundColor Green
    Write-Host "[OK] Frontend bezi na adrese: https://$SwaUrl" -ForegroundColor Green
} else {
    Write-Host "[2/2] Staticky build ulozen v $AppDir/out" -ForegroundColor Green
}

Set-Location ..
