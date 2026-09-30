# Azure Automated Deployment Script for Frontend Applications
# Usage:
#   .\deploy_frontend.ps1 -Client ju -Environment prod -AppType user
#   .\deploy_frontend.ps1 -Client ju -Environment prod -AppType admin

param (
    [string]$Client = "showcase",
    [string]$Environment = "dev",
    [string]$AppType = "user", # 'user' or 'admin'
    [string]$ClientTheme = "", # 'alzbeta' or 'dolphin' or 'showcase' or 'ju'
    [string]$ResourceGroup = "",
    [string]$BackendUrl = ""
)

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()
if ([string]::IsNullOrWhiteSpace($ClientTheme)) {
    $ClientTheme = $ClientClean
}

# 1. Load tenant environment file if present (e.g. .env.ju-prod)
$TenantEnvFile = ".env.${ClientClean}-${EnvClean}"
if (-not (Test-Path $TenantEnvFile)) {
    $TenantEnvFile = ".env.${ClientClean}"
}
if (Test-Path $TenantEnvFile) {
    Get-Content $TenantEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            [Environment]::SetEnvironmentVariable($key.Trim(), $val.Trim())
        }
    }
}

# 2. Resolve Resource Group dynamically
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    $rgCand1 = "$ClientClean-ai-search-rg-$EnvClean"
    $rgCand2 = "ai-search-$ClientClean-rg-$EnvClean"
    
    $check1 = (az group show --name $rgCand1 --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($check1)) {
        $ResourceGroup = $rgCand1
    } else {
        $check2 = (az group show --name $rgCand2 --query name --output tsv 2>$null)
        if (-not [string]::IsNullOrWhiteSpace($check2)) {
            $ResourceGroup = $rgCand2
        } else {
            $ResourceGroup = $rgCand1
        }
    }
}

# Resolve Container App Name
$ContainerAppName = "$ClientClean-ai-search-ca-$EnvClean"
$caCheck = (az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query name --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($caCheck)) {
    $altCa = "ai-search-$ClientClean-ca-$EnvClean"
    $altCheck = (az containerapp show --name $altCa --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($altCheck)) {
        $ContainerAppName = $altCa
    }
}

# Resolve Static Web App Name
$SwaName = if ($AppType -eq "admin") { "$ClientClean-ai-search-swa-admin-$EnvClean" } else { "$ClientClean-ai-search-swa-user-$EnvClean" }
$swaCheck = (az staticwebapp show --name $SwaName --resource-group $ResourceGroup --query name --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($swaCheck)) {
    $altSwa = if ($AppType -eq "admin") { "ai-search-$ClientClean-swa-admin-$EnvClean" } else { "ai-search-$ClientClean-swa-user-$EnvClean" }
    $altSwaCheck = (az staticwebapp show --name $altSwa --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($altSwaCheck)) {
        $SwaName = $altSwa
    }
}

$AppDir = if ($AppType -eq "admin") { "frontend-admin" } else { "frontend-user" }

# Determine Backend URL dynamically from Azure Container App if not specified
if ([string]::IsNullOrWhiteSpace($BackendUrl)) {
    try {
        Write-Host "[INFO] Zistuji FQDN pro backend container '$ContainerAppName' v RG '$ResourceGroup'..." -ForegroundColor White
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
            $BackendUrl = "https://ai-search-dolphin-ca-prod.graysand-c9254ce4.northeurope.azurecontainerapps.io"
        }
    }
}

Write-Host ""
Write-Host "==== AI Search - Frontend Build & Deploy ($AppDir) ====" -ForegroundColor Cyan
Write-Host "[INFO] Client:         $ClientClean" -ForegroundColor White
Write-Host "[INFO] Environment:    $EnvClean" -ForegroundColor White
Write-Host "[INFO] App Type:       $AppType" -ForegroundColor White
Write-Host "[INFO] Client Theme:   $ClientTheme" -ForegroundColor White
Write-Host "[INFO] Backend URL:    $BackendUrl" -ForegroundColor White
Write-Host "[INFO] Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "[INFO] SWA Target:     $SwaName" -ForegroundColor White

# Set environment variables for Next.js build
$env:NEXT_PUBLIC_BACKEND_URL = $BackendUrl
$env:NEXT_PUBLIC_CLIENT_THEME = $ClientTheme

Set-Location $AppDir

Write-Host "[1/2] Sestavuji produkcni build pro $AppDir ($ClientClean / $EnvClean)..." -ForegroundColor Yellow
$npmCmd = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
& $npmCmd run build

if ($LASTEXITCODE -ne 0) {
    Set-Location ..
    Write-Error "Frontend build for $AppDir failed."
    exit 1
}

Write-Host "[OK] Build uspesne dokoncen!" -ForegroundColor Green

# Deploy to Azure Static Web Apps via SWA CLI or Azure CLI deployment token
Write-Host "[INFO] Zistuji deployment token pro Static Web App '$SwaName'..." -ForegroundColor White
$DeploymentToken = (az staticwebapp secrets list --name $SwaName --resource-group $ResourceGroup --query properties.apiKey --output tsv 2>$null)

if ([string]::IsNullOrWhiteSpace($DeploymentToken)) {
    Write-Host "[INFO] Static Web App '$SwaName' neexistuje v '$ResourceGroup', vytvarim v Azure..." -ForegroundColor Yellow
    az staticwebapp create --name $SwaName --resource-group $ResourceGroup --location westeurope --sku Free --output table 2>$null
    $DeploymentToken = (az staticwebapp secrets list --name $SwaName --resource-group $ResourceGroup --query properties.apiKey --output tsv 2>$null)
}

if (-not [string]::IsNullOrWhiteSpace($DeploymentToken)) {
    Write-Host "[2/2] Nasazuji sestaveny frontend do Azure Static Web App '$SwaName'..." -ForegroundColor Yellow
    $npxCmd = if (Get-Command npx.cmd -ErrorAction SilentlyContinue) { "npx.cmd" } else { "npx" }
    & $npxCmd @azure/static-web-apps-cli deploy ./out --deployment-token $DeploymentToken --env production
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Frontend $AppDir byl uspesne nasazen do Azure Static Web App!" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] SWA CLI deployment nebylo mozne provest automaticky. Staticky build je ulozen v $AppDir/out." -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARNING] Nepodarilo se ziskat deployment token pro $SwaName. Staticky build je ulozen v $AppDir/out." -ForegroundColor Yellow
}

Set-Location ..
