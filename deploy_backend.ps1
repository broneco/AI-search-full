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
if ($ClientClean -eq "ju") { $ClientClean = "jhu" }
$EnvClean = $Environment.ToLower()

# 1. Load tenant environment file if present (e.g. tenants/dolphin/.env.dev, tenants/jhu/.env.prod, or root .env.ju-prod)
$TenantEnvFile = "tenants/${ClientClean}/.env.${EnvClean}"
if (-not (Test-Path $TenantEnvFile)) {
    $TenantEnvFile = "tenants/${ClientClean}/.env"
}
if (-not (Test-Path $TenantEnvFile)) {
    $TenantEnvFile = ".env.${ClientClean}-${EnvClean}"
}
if (-not (Test-Path $TenantEnvFile)) {
    $TenantEnvFile = ".env.${ClientClean}"
}
if (Test-Path $TenantEnvFile) {
    Write-Host "[INFO] Nactena konfigurace z $TenantEnvFile" -ForegroundColor Cyan
    Get-Content $TenantEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            $cleanVal = $val.Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key.Trim(), $cleanVal)
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

if ([string]::IsNullOrWhiteSpace($azAccount)) {
    Write-Error "Nejste prihlaseni k Azure CLI. Spustte prosim 'az login' ve vasem PowerShell terminalu a zkuste to znovu."
    exit 1
}
Write-Success "Prihlaseno k Azure (Aktivni ucet / Subscription: $azAccount)"

# 4. Resolve Resource Group in current logged in Azure subscription
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    if (-not [string]::IsNullOrWhiteSpace($env:AZURE_RESOURCE_GROUP)) {
        $ResourceGroup = $env:AZURE_RESOURCE_GROUP
    } else {
        $candidates = @("ai-search-$ClientClean-rg-$EnvClean", "ai-search-rg-$EnvClean", "$ClientClean-ai-search-rg-$EnvClean")
        foreach ($cand in $candidates) {
            $check = (az group show --name $cand --query name --output tsv 2>$null)
            if (-not [string]::IsNullOrWhiteSpace($check)) {
                $ResourceGroup = $cand
                break
            }
        }
        if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
            $ResourceGroup = "ai-search-rg-$EnvClean"
        }
    }
}

# Verify access to target Resource Group
$rgAccess = (az group show --name $ResourceGroup --query name --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($rgAccess)) {
    Write-Error "Resource Group '$ResourceGroup' nebylo v prihlasenem Azure uctu '$azAccount' nalezeno. Ujistete se, ze jste prihlaseni ke spravnemu uctu a subscription pomoci 'az login'."
    exit 1
}
Write-Success "Resource Group overena: $ResourceGroup"

# 5. Resolve Container Registry Name dynamically (check env, RG first, then global)
if ([string]::IsNullOrWhiteSpace($RegistryName)) {
    if (-not [string]::IsNullOrWhiteSpace($env:AZURE_CONTAINER_REGISTRY)) {
        $RegistryName = $env:AZURE_CONTAINER_REGISTRY
    } else {
        $rgAcrs = (az acr list --resource-group $ResourceGroup --query "[].name" --output tsv 2>$null)
        if (-not [string]::IsNullOrWhiteSpace($rgAcrs)) {
            $RegistryName = ($rgAcrs -split "\s+")[0]
        } else {
            $crCandidates = @("aisearch${ClientClean}cr${EnvClean}", "${ClientClean}aisearchcr${EnvClean}", "aisearchshowcasecrdev", "craisearchdev")
            foreach ($cand in $crCandidates) {
                $testAcr = (az acr show --name $cand --query name --output tsv 2>$null)
                if (-not [string]::IsNullOrWhiteSpace($testAcr)) {
                    $RegistryName = $cand
                    break
                }
            }
            if ([string]::IsNullOrWhiteSpace($RegistryName)) {
                $RegistryName = "aisearch${ClientClean}cr${EnvClean}"
            }
        }
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

if (-not [string]::IsNullOrWhiteSpace($env:AZURE_CONTAINER_APP_NAME)) {
    $ContainerAppName = $env:AZURE_CONTAINER_APP_NAME
} else {
    $ContainerAppName = "$ClientClean-ai-search-ca-$EnvClean"
    $caCheck = (az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query name --output tsv 2>$null)
    if ([string]::IsNullOrWhiteSpace($caCheck)) {
        $altCa = "ai-search-$ClientClean-ca-$EnvClean"
        $altCheck = (az containerapp show --name $altCa --resource-group $ResourceGroup --query name --output tsv 2>$null)
        if (-not [string]::IsNullOrWhiteSpace($altCheck)) {
            $ContainerAppName = $altCa
        }
    }
}

$SqlServerHost = if (-not [string]::IsNullOrWhiteSpace($env:AZURE_SQL_HOST)) { $env:AZURE_SQL_HOST } else { "$ClientClean-ai-search-sql-$EnvClean.database.windows.net" }
$SqlDbName = if (-not [string]::IsNullOrWhiteSpace($env:AZURE_SQL_DB)) { $env:AZURE_SQL_DB } else { "$ClientClean-ai-search-sqldb-$EnvClean" }
$BlobOriginalsContainer = if (-not [string]::IsNullOrWhiteSpace($env:AZURE_BLOB_CONTAINER_ORIGINALS)) { $env:AZURE_BLOB_CONTAINER_ORIGINALS } else { "$ClientClean-originals-$EnvClean" }

# Ensure Container Registry exists in Azure
$RegistryServer = (az acr show --name $RegistryName --query loginServer --output tsv 2>$null)
if ([string]::IsNullOrWhiteSpace($RegistryServer)) {
    Write-Error "Container Registry '$RegistryName' nebylo v prihlasenem Azure uctu nalezeno. Zkontrolujte nazev ACR v Azure Portalu a pridejte ho pripadne jako parametr -RegistryName <nazev_acr>."
    exit 1
}

Write-Info "Client / Tenant:     $ClientClean"
Write-Info "Environment:         $EnvClean"
Write-Info "Resource Group:      $ResourceGroup"
Write-Info "Container Registry:  $RegistryName ($RegistryServer)"
Write-Info "Container App:       $ContainerAppName"
Write-Info "SQL Host Target:     $SqlServerHost"
Write-Info "SQL DB Target:       $SqlDbName"
Write-Info "Blob Container:      $BlobOriginalsContainer"

$AcrUser = (az acr credential show --name $RegistryName --query username --output tsv 2>$null)
$AcrPass = (az acr credential show --name $RegistryName --query "passwords[0].value" --output tsv 2>$null)

Write-Success "Found Registry Server: $RegistryServer"

# 6. Generate timestamp-based image version tag to prevent conflicts
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ImageTag = "${EnvClean}-v-${Timestamp}"
Write-Info "Generated Image Version Tag: $ImageTag"

# 7. Build Docker Image in the cloud via Azure ACR Tasks
Write-Header "[1/3] Sestavuji Docker image v cloudu pres Azure ACR Tasks..."
Write-Info "Spoustam zive sestaveni Docker obrazku v Azure ACR '$RegistryName'..."
Write-Info "Sledujte zive kroky sestavovani (Step 1/12, download vrstev, kompilace) nize:"
Write-Host ""

$BuildStartTime = Get-Date
az acr build --registry $RegistryName `
  --image "${ContainerAppName}:${ImageTag}" `
  --image "${ContainerAppName}:latest" --no-logs .

if ($LASTEXITCODE -ne 0) {
    Write-Error "ACR Build failed."
    exit 1
}
$BuildDuration = New-TimeSpan -Start $BuildStartTime -End (Get-Date)
$FormattedDuration = "{0:D2}:{1:D2}" -f $BuildDuration.Minutes, $BuildDuration.Seconds
Write-Success "Docker image successfully built in ACR: ${RegistryServer}/${ContainerAppName}:${ImageTag} (Celkovy cas sestaveni: $FormattedDuration)"

# 8. Retrieve secrets dynamically from Azure Key Vault if required
$KvName = if (-not [string]::IsNullOrWhiteSpace($env:AZURE_KEY_VAULT_NAME)) { $env:AZURE_KEY_VAULT_NAME } else { "$ClientClean-ai-search-kv-$EnvClean" }
$KvSecretSqlName = if ($env:AZURE_KEY_VAULT_SECRET_SQL_PASSWORD) { $env:AZURE_KEY_VAULT_SECRET_SQL_PASSWORD } else { "$ClientClean-ai-search-sql-sqlaccount-password-$EnvClean" }
$KvSecretOpenAiName = if ($env:AZURE_KEY_VAULT_SECRET_OPENAI_KEY) { $env:AZURE_KEY_VAULT_SECRET_OPENAI_KEY } else { "$ClientClean-ai-search-openai-api-key-$EnvClean" }
$KvSecretStorageName = if ($env:AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR) { $env:AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR } else { "$ClientClean-ai-search-storage-connection-string-$EnvClean" }
$KvSecretPostgresName = if ($env:AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD) { $env:AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD } else { "$ClientClean-ai-search-postgres-password-$EnvClean" }

if ([string]::IsNullOrWhiteSpace($env:AZURE_SQL_PASSWORD)) {
    Write-Info "Nacitam heslo pro SQL z Azure Key Vault '$KvName' (Secret: '$KvSecretSqlName')..."
    $fetchedPass = (az keyvault secret show --name $KvSecretSqlName --vault-name $KvName --query value --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($fetchedPass)) {
        $env:AZURE_SQL_PASSWORD = $fetchedPass
        Write-Success "SQL heslo bylo uspesne ziskane z Key Vault '$KvName'!"
    } else {
        Write-WarningMsg "Heslo v Key Vault '$KvName' nenalezeno nebo vyzaduje opravneni."
    }
}

$SqlPassEnv = if ($env:AZURE_SQL_PASSWORD) { $env:AZURE_SQL_PASSWORD } else { "" }
$StorageAccountEnv = if ($env:AZURE_STORAGE_ACCOUNT) { $env:AZURE_STORAGE_ACCOUNT } else { "" }
$StorageConnStrEnv = if ($env:AZURE_STORAGE_CONNECTION_STRING) { $env:AZURE_STORAGE_CONNECTION_STRING } else { "" }

if ([string]::IsNullOrWhiteSpace($StorageConnStrEnv)) {
    $fetchedStorage = (az keyvault secret show --name $KvSecretStorageName --vault-name $KvName --query value --output tsv 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($fetchedStorage)) {
        $StorageConnStrEnv = $fetchedStorage
        Write-Success "Storage connection string byl uspesne ziskan z Key Vault '$KvName'!"
    }
}

# 9. Check if Container App exists; Create if missing, Update if exists
Write-Header "[2/3] Nasazuji novou verzi a konfiguraci do Azure Container App..."

$provState = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query "properties.provisioningState" --output tsv 2>$null)
while ($provState -and $provState -ne "Succeeded" -and $provState -ne "Failed") {
    Write-Info "Cekam na dokonceni probihajici Azure operace '$provState' pro Container App '$ContainerAppName'..."
    Start-Sleep -Seconds 5
    $provState = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query "properties.provisioningState" --output tsv 2>$null)
}

$appExists = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query name --output tsv 2>$null)
$existingContainerName = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query "properties.template.containers[0].name" --output tsv 2>$null)
$existingImage = (az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query "properties.template.containers[0].image" --output tsv 2>$null)
$isQuickstart = ($existingImage -like "*quickstart*") -or ($existingContainerName -eq "simple-hello-world-container")

if ([string]::IsNullOrWhiteSpace($appExists) -or [string]::IsNullOrWhiteSpace($existingContainerName) -or $isQuickstart) {
    if (-not [string]::IsNullOrWhiteSpace($appExists)) {
        Write-Info "Container App '$ContainerAppName' vyzaduje novou inicializaci (Quickstart/Stara schranka). Odstranuji stary zdroj v Azure..."
        az containerapp delete --resource-group $ResourceGroup --name $ContainerAppName --yes 2>$null
        while (-not [string]::IsNullOrWhiteSpace((az containerapp show --resource-group $ResourceGroup --name $ContainerAppName --query name --output tsv 2>$null))) {
            Start-Sleep -Seconds 5
        }
    }
    Write-Info "Vytvarim novou Container App '$ContainerAppName' s obrazem ${RegistryServer}/${ContainerAppName}:${ImageTag}..."
    $createArgs = @(
      "--resource-group", $ResourceGroup,
      "--name", $ContainerAppName,
      "--environment", $ContainerEnvName,
      "--image", "${RegistryServer}/${ContainerAppName}:${ImageTag}",
      "--target-port", "8000",
      "--ingress", "external",
      "--min-replicas", "1",
      "--max-replicas", "3",
      "--system-assigned"
    )
    if (-not [string]::IsNullOrWhiteSpace($AcrUser) -and -not [string]::IsNullOrWhiteSpace($AcrPass)) {
        $createArgs += @("--registry-server", $RegistryServer, "--registry-username", $AcrUser, "--registry-password", $AcrPass)
    }
    az containerapp create @createArgs --env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server" "AZURE_SQL_PASSWORD=${SqlPassEnv}" "AZURE_KEY_VAULT_NAME=${KvName}" "AZURE_KEY_VAULT_SECRET_SQL_PASSWORD=${KvSecretSqlName}" "AZURE_KEY_VAULT_SECRET_OPENAI_KEY=${KvSecretOpenAiName}" "AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR=${KvSecretStorageName}" "AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD=${KvSecretPostgresName}" "AZURE_STORAGE_ACCOUNT=${StorageAccountEnv}" "AZURE_STORAGE_CONNECTION_STRING=${StorageConnStrEnv}"
} else {
    if (-not [string]::IsNullOrWhiteSpace($AcrUser) -and -not [string]::IsNullOrWhiteSpace($AcrPass)) {
        Write-Info "Registruji ACR autentizaci pro '$RegistryServer'..."
        az containerapp registry set --resource-group $ResourceGroup --name $ContainerAppName --server $RegistryServer --username $AcrUser --password $AcrPass 2>$null
    }
    az containerapp ingress update --resource-group $ResourceGroup --name $ContainerAppName --target-port 8000 --type external 2>$null
    az containerapp identity assign --resource-group $ResourceGroup --name $ContainerAppName --system-assigned 2>$null

    Write-Info "Provadim rolling update kontejneru '$existingContainerName' na novy Docker image ${RegistryServer}/${ContainerAppName}:${ImageTag}..."
    az containerapp update --resource-group $ResourceGroup --name $ContainerAppName `
      --container-name $existingContainerName `
      --image "${RegistryServer}/${ContainerAppName}:${ImageTag}" `
      --set-env-vars "APP_ENV=${EnvClean}" "AZURE_BLOB_CONTAINER_ORIGINALS=${BlobOriginalsContainer}" "TENANT_ID=${ClientClean}-${EnvClean}" "AZURE_SQL_HOST=${SqlServerHost}" "AZURE_SQL_PORT=1433" "AZURE_SQL_DB=${SqlDbName}" "AZURE_SQL_USER=sqladmin" "AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server" "AZURE_SQL_PASSWORD=${SqlPassEnv}" "AZURE_KEY_VAULT_NAME=${KvName}" "AZURE_KEY_VAULT_SECRET_SQL_PASSWORD=${KvSecretSqlName}" "AZURE_KEY_VAULT_SECRET_OPENAI_KEY=${KvSecretOpenAiName}" "AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR=${KvSecretStorageName}" "AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD=${KvSecretPostgresName}" "AZURE_STORAGE_ACCOUNT=${StorageAccountEnv}" "AZURE_STORAGE_CONNECTION_STRING=${StorageConnStrEnv}"
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
