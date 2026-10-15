# Existing-app release only. Default: read-only plan; -Apply requires a reviewed target.
# Database migrations, runtime secret provisioning and frontend releases are separate steps.
[CmdletBinding()]
param (
    [string]$Client = "showcase",
    [ValidateSet("dev", "prod")][string]$Environment = "dev",
    [string]$ResourceGroup = "",
    [string]$RegistryName = "",
    [string]$ExpectedSubscriptionId = "",
    [string]$ExpectedAzureTenantId = "",
    [string]$ExpectedCurrentImage = "",
    [switch]$MigrationConfirmed,
    [switch]$JwtMigrationConfirmed,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Azure {
    param([string[]]$Arguments)
    # Windows PowerShell 5.1 can raise on native stderr despite exit code 0.
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $result = & az @Arguments --only-show-errors --output json 2>$null
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) {
        # ARM responses may contain inline environment secrets: do not echo them.
        throw "Azure CLI failed (exit $code). No further release steps executed."
    }
    if ($result) { return ($result -join "`n" | ConvertFrom-Json) }
}

$null = Get-Command az -ErrorAction Stop
$ClientClean = $Client.Trim().ToLowerInvariant()
if ($ClientClean -eq "ju") { $ClientClean = "jhu" }
if ($ClientClean -notmatch '^[a-z0-9]+$') { throw "Invalid tenant directory name." }
$EnvClean = $Environment.ToLowerInvariant()
$TenantEnvFile = Join-Path $PSScriptRoot "tenants/$ClientClean/.env.$EnvClean"
if (-not (Test-Path -LiteralPath $TenantEnvFile)) {
    throw "Explicit tenant environment file required: tenants/$ClientClean/.env.$EnvClean"
}
# Do not export tenant secrets into the caller's process.
$config = @{}
foreach ($line in Get-Content -LiteralPath $TenantEnvFile) {
    $entry = $line.Trim()
    if ($entry -and -not $entry.StartsWith("#") -and $entry.Contains("=")) {
        $key, $value = $entry.Split("=", 2)
        $config[$key.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
}
foreach ($key in @("TENANT_ID", "AZURE_CONTAINER_APP_NAME", "AZURE_SQL_HOST", "AZURE_SQL_DB")) {
    if (-not $config[$key]) { throw "Tenant configuration requires $key." }
}
if (-not $ResourceGroup) { $ResourceGroup = $config["AZURE_RESOURCE_GROUP"] }
if (-not $RegistryName) { $RegistryName = $config["AZURE_CONTAINER_REGISTRY"] }
if (-not $ResourceGroup -or -not $RegistryName) { throw "Explicit resource group and registry required." }
if ($config["APP_ENV"] -cne $EnvClean) { throw "Tenant APP_ENV does not match the selected environment." }

$account = Invoke-Azure -Arguments @("account", "show")
if ($ExpectedSubscriptionId -and $account.id -cne $ExpectedSubscriptionId) {
    throw "Active subscription does not match ExpectedSubscriptionId."
}
if ($ExpectedAzureTenantId -and $account.tenantId -cne $ExpectedAzureTenantId) {
    throw "Active Azure tenant does not match ExpectedAzureTenantId."
}
$scope = @("--subscription", $account.id)
$appName = $config["AZURE_CONTAINER_APP_NAME"]
$app = Invoke-Azure -Arguments (@("containerapp", "show", "--resource-group", $ResourceGroup, "--name", $appName) + $scope)
$containers = @($app.properties.template.containers)
if ($containers.Count -ne 1) { throw "Release requires a reviewed single-container application." }
$container = $containers[0]
$runtime = @{}
foreach ($item in $container.env) { $runtime[$item.name] = $item }
$secretNames = @($app.properties.configuration.secrets | ForEach-Object { $_.name })
function Get-RuntimeValue([string]$Name) {
    if ($runtime.ContainsKey($Name) -and $runtime[$Name].PSObject.Properties["value"]) {
        return [string]$runtime[$Name].value
    }
    return ""
}
function Test-RuntimeSecret([string]$Name) {
    if (Get-RuntimeValue $Name) { return $true }
    if ($runtime.ContainsKey($Name) -and $runtime[$Name].PSObject.Properties["secretRef"]) {
        return $secretNames -ccontains $runtime[$Name].secretRef
    }
    return $false
}
$blockers = [System.Collections.Generic.List[string]]::new()
foreach ($key in @("TENANT_ID", "AZURE_SQL_HOST", "AZURE_SQL_DB")) {
    if ((Get-RuntimeValue $key) -cne $config[$key]) { $blockers.Add("Runtime target mismatch: $key") }
}
if ((Get-RuntimeValue "APP_ENV") -cne $EnvClean) { $blockers.Add("Runtime APP_ENV mismatch") }
foreach ($key in @(
    "AZURE_SQL_USER", "AZURE_SQL_DRIVER", "AZURE_BLOB_CONTAINER_ORIGINALS",
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_FLASH_DEPLOYMENT", "AZURE_OPENAI_THINKING_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "AZURE_OPENAI_EMBEDDING_MODEL",
    "AZURE_OPENAI_EMBEDDING_MODEL_REVISION", "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
    "EMBEDDING_PROVIDER", "LLM_PROVIDER"
)) {
    if (-not (Get-RuntimeValue $key)) { $blockers.Add("Explicit runtime setting required: $key") }
}
foreach ($key in @("AZURE_OPENAI_EMBEDDING_QUERY_PREFIX", "AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX")) {
    if (-not $runtime.ContainsKey($key)) { $blockers.Add("Explicit runtime setting required (may be empty): $key") }
}
$jwtFromVault = (Get-RuntimeValue "AZURE_KEY_VAULT_NAME") -and (Get-RuntimeValue "AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY")
if (-not (Test-RuntimeSecret "JWT_SECRET") -and -not $jwtFromVault) {
    $blockers.Add("Private runtime JWT_SECRET or configured Key Vault JWT source required")
}
if ((Get-RuntimeValue "JWT_SECRET") -ceq "dolphin-ai-search-secret-key-2026" -and -not $jwtFromVault) {
    $blockers.Add("Known default JWT_SECRET is forbidden in Azure")
}
foreach ($pair in @(
    @("AZURE_SQL_PASSWORD", "AZURE_KEY_VAULT_SECRET_SQL_PASSWORD"),
    @("AZURE_OPENAI_API_KEY", "AZURE_KEY_VAULT_SECRET_OPENAI_KEY"),
    @("AZURE_STORAGE_CONNECTION_STRING", "AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR")
)) {
    if (-not (Test-RuntimeSecret $pair[0]) -and -not (
        (Get-RuntimeValue "AZURE_KEY_VAULT_NAME") -and (Get-RuntimeValue $pair[1])
    )) { $blockers.Add("Runtime credential or existing Key Vault configuration required: $($pair[0])") }
}
$registry = Invoke-Azure -Arguments (@("acr", "show", "--name", $RegistryName) + $scope)
if (-not $container.image.StartsWith("$($registry.loginServer)/", [StringComparison]::OrdinalIgnoreCase)) {
    $blockers.Add("Existing image does not use the selected registry")
}
if ($ExpectedCurrentImage -and $container.image -cne $ExpectedCurrentImage) {
    $blockers.Add("Current image changed since review")
}
$plan = [ordered]@{
    mode = if ($Apply) { "apply" } else { "plan" }
    subscription = $account.id; azure_tenant = $account.tenantId
    resource_group = $ResourceGroup; app = $appName; tenant = $config["TENANT_ID"]
    sql_host = $config["AZURE_SQL_HOST"]; sql_database = $config["AZURE_SQL_DB"]
    previous_image = $container.image; previous_revision = $app.properties.latestReadyRevisionName
    actions = @("Build one timestamp-tagged image", "Update existing container image only")
    blockers = @($blockers.ToArray())
    operator_checks = @("Schema/ACL/Unicode/tenant/profile migration accepted", "JWT/login migration accepted", "Matching frontend release reviewed")
}
$plan | ConvertTo-Json -Depth 5
if (-not $Apply) { return }
if (-not $ExpectedSubscriptionId -or -not $ExpectedAzureTenantId -or -not $ExpectedCurrentImage) {
    throw "Apply requires ExpectedSubscriptionId, ExpectedAzureTenantId and ExpectedCurrentImage."
}
if (-not $MigrationConfirmed -or -not $JwtMigrationConfirmed) {
    throw "Apply requires reviewed database migration and JWT/login migration confirmations."
}
if ($blockers.Count) { throw "Resolve all plan blockers before applying this release." }

# Preserve resources, secrets, identity, ingress, scale and tenant configuration.
# No database migration, latest tag or document ingestion is part of this script.
$tag = "$EnvClean-v-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$image = "$($registry.loginServer)/${appName}:$tag"
Push-Location $PSScriptRoot
try {
    $null = Invoke-Azure -Arguments (@("acr", "build", "--registry", $RegistryName, "--image", "${appName}:$tag", "--no-logs", ".") + $scope)
    # Refuse a concurrent release/configuration change detected after the build.
    $current = Invoke-Azure -Arguments (@("containerapp", "show", "--resource-group", $ResourceGroup, "--name", $appName) + $scope)
    if (($current.properties.template | ConvertTo-Json -Depth 40 -Compress) -cne (
        $app.properties.template | ConvertTo-Json -Depth 40 -Compress
    ) -or ($current.properties.configuration | ConvertTo-Json -Depth 40 -Compress) -cne (
        $app.properties.configuration | ConvertTo-Json -Depth 40 -Compress
    )) { throw "Application changed during build; image retained, no runtime update performed." }
    $null = Invoke-Azure -Arguments (@("containerapp", "update", "--resource-group", $ResourceGroup, "--name", $appName,
        "--container-name", $container.name, "--image", $image) + $scope)
} finally { Pop-Location }
Write-Output "Image update requested: $image"
Write-Output "Previous image: $($container.image). Run authenticated API/PDF acceptance before declaring rollout complete."
