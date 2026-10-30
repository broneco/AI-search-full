# Existing Static Web App release. Default: read-only plan. Never provisions resources.
[CmdletBinding()]
param (
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]*$')][string]$Client = 'showcase',
    [ValidateSet('dev', 'prod')][string]$Environment = 'dev',
    [ValidateSet('user', 'admin')][string]$AppType = 'user',
    [string]$ClientTheme = '',
    [string]$ResourceGroup = '',
    [string]$BackendUrl = '',
    [string]$StaticWebAppName = '',
    [string]$ExpectedSubscriptionId = '',
    [string]$ExpectedAzureTenantId = '',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-AzureRead {
    param([string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    $output = & az @Arguments --only-show-errors --output json 2>$null
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "Azure read failed (exit $code). No resource will be created or deployment attempted." }
    if ($output) { return ($output -join "`n" | ConvertFrom-Json) }
    throw 'Azure returned an empty response.'
}
function Invoke-ReleaseCommand {
    param([string]$Command, [string[]]$Arguments, [switch]$Quiet)
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    & $Command @Arguments 2>&1 | ForEach-Object { if (-not $Quiet) { Write-Host $_.ToString() } }
    if ($LASTEXITCODE -ne 0) { throw "Release command failed (exit $LASTEXITCODE); deployment not confirmed." }
}

$null = Get-Command az -ErrorAction Stop
$clientName = $Client.ToLowerInvariant()
if ($clientName -eq 'ju') { $clientName = 'jhu' }
if (-not $ClientTheme) { $ClientTheme = $clientName }
$config = @{}
$envFile = Join-Path $PSScriptRoot "tenants/$clientName/.env.$Environment"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([^#=\s]+)\s*=\s*(.*?)\s*$') {
            $config[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
        }
    }
}
function Get-TargetValue([string]$Name) {
    if ($config.ContainsKey($Name)) { return $config[$Name] }
    return [Environment]::GetEnvironmentVariable($Name)
}
if (-not $ResourceGroup) { $ResourceGroup = Get-TargetValue 'AZURE_RESOURCE_GROUP' }
if (-not $StaticWebAppName) {
    $key = if ($AppType -eq 'admin') { 'AZURE_SWA_ADMIN_NAME' } else { 'AZURE_SWA_USER_NAME' }
    $StaticWebAppName = Get-TargetValue $key
}
if (-not $ResourceGroup -or -not $StaticWebAppName) { throw 'Explicit resource group and existing Static Web App name required.' }

$account = Invoke-AzureRead -Arguments @('account', 'show')
if ($ExpectedSubscriptionId -and $account.id -cne $ExpectedSubscriptionId) { throw 'Azure subscription mismatch.' }
if ($ExpectedAzureTenantId -and $account.tenantId -cne $ExpectedAzureTenantId) { throw 'Azure directory mismatch.' }
$scope = @('--subscription', $account.id)
$swa = Invoke-AzureRead -Arguments (@('staticwebapp', 'show', '--name', $StaticWebAppName, '--resource-group', $ResourceGroup) + $scope)
if (-not $swa.id -or -not $swa.defaultHostname) { throw 'Static Web App identity/hostname missing.' }
if (-not $BackendUrl) {
    $appName = Get-TargetValue 'AZURE_CONTAINER_APP_NAME'
    if (-not $appName) { throw 'BackendUrl or configured Container App name required.' }
    $backend = Invoke-AzureRead -Arguments (@('containerapp', 'show', '--name', $appName, '--resource-group', $ResourceGroup) + $scope)
    $fqdn = $backend.properties.configuration.ingress.fqdn
    if (-not $fqdn) { throw 'Backend has no public FQDN; specify a reviewed BackendUrl.' }
    $BackendUrl = "https://$fqdn"
}
$uri = $null
if (-not [Uri]::TryCreate($BackendUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or
    $uri.UserInfo -or $uri.Query -or $uri.Fragment) { throw 'A reviewed HTTPS BackendUrl without credentials/query/fragment is required.' }
$appDir = Join-Path $PSScriptRoot "frontend-$AppType"
@{client = $clientName; app_type = $AppType; subscription_id = $account.id; azure_tenant_id = $account.tenantId;
  resource_group = $ResourceGroup; swa_id = $swa.id; swa_hostname = $swa.defaultHostname;
  backend_url = $BackendUrl; theme = $ClientTheme; apply = [bool]$Apply} | ConvertTo-Json
if (-not $Apply) { return }
if (-not $ExpectedSubscriptionId -or -not $ExpectedAzureTenantId) { throw 'Apply requires ExpectedSubscriptionId and ExpectedAzureTenantId.' }
if (-not (Test-Path -LiteralPath (Join-Path $appDir 'package.json'))) { throw 'Frontend package.json missing.' }
$npmPath = (Get-Command npm.cmd -ErrorAction Stop).Source
$npxPath = (Get-Command npx.cmd -ErrorAction Stop).Source
$previousUrl = [Environment]::GetEnvironmentVariable('NEXT_PUBLIC_BACKEND_URL')
$previousTheme = [Environment]::GetEnvironmentVariable('NEXT_PUBLIC_CLIENT_THEME')
$previousDeploymentToken = [Environment]::GetEnvironmentVariable('SWA_CLI_DEPLOYMENT_TOKEN')
$previousDeployDebug = [Environment]::GetEnvironmentVariable('SWA_CLI_DEBUG')
Push-Location -LiteralPath $appDir
try {
    $env:NEXT_PUBLIC_BACKEND_URL = $BackendUrl
    $env:NEXT_PUBLIC_CLIENT_THEME = $ClientTheme
    Invoke-ReleaseCommand -Command $npmPath -Arguments @('run', 'build')
    if (-not (Test-Path -LiteralPath (Join-Path $appDir 'out/index.html'))) { throw 'Static build output missing.' }
    $currentAccount = Invoke-AzureRead -Arguments @('account', 'show')
    if ($currentAccount.id -cne $account.id -or $currentAccount.tenantId -cne $account.tenantId) { throw 'Azure account changed during build.' }
    $currentSwa = Invoke-AzureRead -Arguments (@('staticwebapp', 'show', '--name', $StaticWebAppName, '--resource-group', $ResourceGroup) + $scope)
    if ($currentSwa.id -cne $swa.id -or $currentSwa.defaultHostname -cne $swa.defaultHostname) { throw 'SWA changed during build.' }
    $secrets = Invoke-AzureRead -Arguments (@('staticwebapp', 'secrets', 'list', '--name', $StaticWebAppName, '--resource-group', $ResourceGroup) + $scope)
    $deploymentToken = $secrets.properties.apiKey
    if (-not $deploymentToken) { throw 'Deployment token unavailable; no deployment attempted.' }
    # Keep the token out of command arguments/process listings and debug output.
    $env:SWA_CLI_DEPLOYMENT_TOKEN = $deploymentToken
    $env:SWA_CLI_DEBUG = 'error'
    Invoke-ReleaseCommand -Command $npxPath -Arguments @('@azure/static-web-apps-cli', 'deploy', './out', '--env', 'production') -Quiet
    Write-Output "Frontend deployment CLI completed for $($swa.defaultHostname). Verify live version, auth, citations and CORS."
} finally {
    $deploymentToken = $null
    [Environment]::SetEnvironmentVariable('NEXT_PUBLIC_BACKEND_URL', $previousUrl)
    [Environment]::SetEnvironmentVariable('NEXT_PUBLIC_CLIENT_THEME', $previousTheme)
    [Environment]::SetEnvironmentVariable('SWA_CLI_DEPLOYMENT_TOKEN', $previousDeploymentToken)
    [Environment]::SetEnvironmentVariable('SWA_CLI_DEBUG', $previousDeployDebug)
    Pop-Location
}
