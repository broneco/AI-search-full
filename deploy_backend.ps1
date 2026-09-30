# Azure Container Apps Automated Deployment Script for Backend
# Usage:
#   .\deploy_backend.ps1 -Client ju -Environment prod
#   .\deploy_backend.ps1 -Client showcase -Environment dev -ForceLogin

param (
    [string]$Client = "showcase",
    [string]$Environment = "dev",
    [string]$ResourceGroup = "",
    [string]$RegistryName = "",
    [string]$ContainerEnvName = "",
    [string]$Location = "northeurope",
    [switch]$ForceLogin
)

$ErrorActionPreference = "Continue"
$env:AZURE_CORE_ONLY_SHOW_ERRORS = "true"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()

# 1. Load tenant environment file if present (e.g. .env.ju-prod, .env.showcase)
$TenantEnvFile = ".env.${ClientClean}-${EnvClean}"
if (-not (Test-Path $TenantEnvFile)) {
    $TenantEnvFile = ".env.${ClientClean}"
}
if (Test-Path $TenantEnvFile) {
    Write-Host "[INFO] Nactena konfigurace z $TenantEnvFile" -ForegroundColor Cyan
    Get-Content $TenantEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            [Environment]::SetEnvironmentVariable($key.Trim(), $val.Trim())
        }
    }
}

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

Write-Header "AI Search - Automated Backend Deployment"

# 2. Verify Azure CLI is installed
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Error "Azure CLI (az) was not found on your system. Please install it from https://aka.ms/installazurecliwindows first."
    exit 1
}

# 3. Perform Azure Login / Active Account verification
Write-Info "Overuji prihlaseni k Azure CLI..."
$azAccount = (az account show --query name --output tsv 2>$null)

if ($ForceLogin -or [string]::IsNullOrWhiteSpace($azAccount)) {
    if ($ForceLogin) {
        Write-WarningMsg "Pouzit parametr -ForceLogin. Otviram Azure prihlasovaci obrazovku..."
    } else {
        Write-WarningMsg "Nejste prihlaseni k Azure CLI. Spoustam 'az login'..."
    }
    az login
    $azAccount = (az account show --query name --output tsv 2>$null)
}
Write-Success "Prihlaseno k Azure (Aktivni ucet / Subscription: $azAccount)"

# 4. Resolve Resource Group dynamically AFTER Azure Login
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

# Verify access to target Resource Group
$rgAccess = (az group show --name $ResourceGroup --query name --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($rgAccess)) {
    Write-WarningMsg "Resource Group '$ResourceGroup' nebylo v prihlasenem uctu nalezeno. Spoustam 'az login' pro vyber spravneho uctu..."
    az login
    $azAccount = (az account show --query name --output tsv 2>$null)
    $rgAccess = (az group show --name $ResourceGroup --query name --output tsv 2>$null)
    if ([string]::IsNullOrWhiteSpace($rgAccess)) {
        Write-Error "Prihlaseny Azure ucet nema pristup k Resource Group '$ResourceGroup' ani '$ClientClean-ai-search-rg-$EnvClean'. Zkontrolujte tenant a subscription."
        exit 1
    }
}
Write-Success "Resource Group overena: $ResourceGroup"

if ([string]::IsNullOrWhiteSpace($RegistryName)) {
    $crCand1 = "${ClientClean}aisearchcr${EnvClean}"
    $crCand2 = "aisearch${ClientClean}cr${EnvClean}"
    $checkCr1 = (az acr show --name $crCand1 --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($checkCr1)) {
        $RegistryName = $crCand1
    } else {
        $RegistryName = $crCand2
    }
}

if ([string]::IsNullOrWhiteSpace($ContainerEnvName)) {
    $caeCand1 = "$ClientClean-ai-search-cae2-$EnvClean"
    $caeCand2 = "$ClientClean-ai-search-cae-$EnvClean"
    $caeCand3 = "ai-search-$ClientClean-cae-$EnvClean"
    $checkCae1 = (az containerapp env show --name $caeCand1 --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($checkCae1)) {
        $ContainerEnvName = $caeCand1
    } else {
        $ContainerEnvName = $caeCand2
    }
}

$ContainerAppName = "$ClientClean-ai-search-ca-$EnvClean"
$caCheck = (az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query name --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($caCheck)) {
    $altCa = "ai-search-$ClientClean-ca-$EnvClean"
    $altCheck = (az containerapp show --name $altCa --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($altCheck)) {
        $ContainerAppName = $altCa
    }
}

$SqlDbName = "$ClientClean-ai-search-sqldb-$EnvClean"
$SqlServerHost = "$ClientClean-ai-search-sql-$EnvClean.database.windows.net"
$BlobOriginalsContainer = "$ClientClean-originals-$EnvClean"

Write-Info "Client / Tenant:     $ClientClean"
Write-Info "Environment:         $EnvClean"
Write-Info "Resource Group:      $ResourceGroup"
Write-Info "Container Registry:  $RegistryName"
Write-Info "Container App:       $ContainerAppName"
Write-Info "SQL Host Target:     $SqlServerHost"
Write-Info "SQL DB Target:       $SqlDbName"
Write-Info "Blob Container:      $BlobOriginalsContainer"

# 5. Retrieve ACR Login Server and Credentials dynamically
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

# 6. Generate timestamp-based image version tag to prevent conflicts
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ImageTag = "${EnvClean}-v-${Timestamp}"
Write-Info "Generated Image Version Tag: $ImageTag"

# 7. Build Docker Image in the cloud via Azure ACR Tasks
Write-Header "[1/3] Sestavuji Docker image v cloudu pres Azure ACR Tasks..."
az acr build --registry $RegistryName `
  --image "${ContainerAppName}:${ImageTag}" `
  --image "${ContainerAppName}:latest" . --no-logs

if ($LASTEXITCODE -ne 0) {
    Write-Error "ACR Build failed."
    exit 1
}
Write-Success "Docker image successfully built in ACR: ${RegistryServer}/${ContainerAppName}:${ImageTag}"

# 8. Retrieve SQL Password dynamically from Azure Key Vault if required
$KvName = if ($env:AZURE_KEY_VAULT_NAME) { $env:AZURE_KEY_VAULT_NAME } else { "$ClientClean-ai-search-kv-$EnvClean" }
$KvSecretName = if ($env:AZURE_KEY_VAULT_SECRET_SQL_PASSWORD) { $env:AZURE_KEY_VAULT_SECRET_SQL_PASSWORD } else { "$ClientClean-ai-search-sql-sqlaccount-password-$EnvClean" }

if ([string]::IsNullOrWhiteSpace($env:AZURE_SQL_PASSWORD)) {
    Write-Info "Nacitam heslo pro SQL z Azure Key Vault '$KvName' (Secret: '$KvSecretName')..."
    $fetchedPass = (az keyvault secret show --name $KvSecretName --vault-name $KvName --query value --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($fetchedPass)) {
        $env:AZURE_SQL_PASSWORD = $fetchedPass
        Write-Success "SQL heslo bylo uspesne ziskane z Key Vault '$KvName'!"
    } else {
        Write-WarningMsg "Heslo v Key Vault '$KvName' nenalezeno nebo vyzaduje opravneni."
    }
}

$SqlPassEnv = if ($env:AZURE_SQL_PASSWORD) { $env:AZURE_SQL_PASSWORD } else { "" }

# 9. Check if Container App exists; Create if missing, Update if exists
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
      --env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server" "AZURE_SQL_PASSWORD=${SqlPassEnv}" "AZURE_KEY_VAULT_NAME=${KvName}" "AZURE_KEY_VAULT_SECRET_SQL_PASSWORD=${KvSecretName}"
} else {
    Write-Info "Container App '$ContainerAppName' jiz existuje. Registruji ACR autentizaci pro '$RegistryServer'..."
    az containerapp registry set --resource-group $ResourceGroup --name $ContainerAppName --server $RegistryServer --username $AcrUser --password $AcrPass
    az containerapp ingress update --resource-group $ResourceGroup --name $ContainerAppName --target-port 8000 --type external
    
    $existingContainerName = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query "properties.template.containers[0].name" --output tsv 2>$null)
    if ([string]::IsNullOrWhiteSpace($existingContainerName)) {
        $existingContainerName = $ContainerAppName
    }

    Write-Info "Provadim rolling update kontejneru '$existingContainerName' na novy Docker image ${RegistryServer}/${ContainerAppName}:${ImageTag}..."
    az containerapp update --resource-group $ResourceGroup --name $ContainerAppName `
      --container-name $existingContainerName `
      --image "${RegistryServer}/${ContainerAppName}:${ImageTag}" `
      --registry-server $RegistryServer `
      --registry-username $AcrUser `
      --registry-password $AcrPass `
      --set-env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server" "AZURE_SQL_PASSWORD=${SqlPassEnv}" "AZURE_KEY_VAULT_NAME=${KvName}" "AZURE_KEY_VAULT_SECRET_SQL_PASSWORD=${KvSecretName}"
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container App creation/update failed."
    exit 1
}
Write-Success "Container App updated successfully!"

# 10. Configure CORS to allow any origin
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

# 11. Retrieve FQDN and print summary
$AppUrl = az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query properties.configuration.ingress.fqdn --output tsv
Write-Header "Nasazeni backendu ($ClientClean / $EnvClean) dokonceno!"
Write-Success "Aplikace bezi na adrese: https://$AppUrl"

# 12. Optional Full Refresh Document Ingestion for Client Tenant
Write-Header "[4/4] Spusteni Full Refresh Ingestu pro tenant '$ClientClean' do databaze $SqlDbName..."
try {
    $IngestScript = "full_refresh_ingest.py"
    if (Test-Path $IngestScript) {
        Write-Info "Spustam ingestacni skript full_refresh_ingest.py pro tenant '$ClientClean' v databazi '$SqlDbName'..."
        $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
        
        $env:APP_ENV = $EnvClean
        $env:TENANT_ID = $ClientClean
        $env:AZURE_SQL_HOST = $SqlServerHost
        $env:AZURE_SQL_DB = $SqlDbName
        $env:AZURE_SQL_USER = "sqladmin"
        $env:AZURE_BLOB_CONTAINER_ORIGINALS = $BlobOriginalsContainer
        $env:AZURE_KEY_VAULT_NAME = $KvName
        $env:AZURE_KEY_VAULT_SECRET_SQL_PASSWORD = $KvSecretName

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
