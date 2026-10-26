param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start-db", "stop-db", "backend", "test", "start-jhu", "status-jhu", "stop-jhu")]
    [string]$Action,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$')]
    [string]$Tenant,
    [switch]$JhuManaged,
    [string]$JhuVault = "ju-ai-search-kv-prod",
    [string]$JhuVpnProfile = (Join-Path $env:USERPROFILE "OpenVPN\config\Client\Client.ovpn")
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
$LocalEnvPath = Join-Path $ProjectRoot ".env.local"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-LocalDocker {
    param(
        [string[]]$DockerArguments,
        [switch]$Quiet
    )

    Get-Command docker -ErrorAction Stop | Out-Null
    # Windows PowerShell 5.1 wraps native stderr (including warnings) as error
    # records. Only the process exit code determines whether Docker failed.
    # These preferences are function-local and do not weaken script validation.
    $ErrorActionPreference = "Continue"
    $PSNativeCommandUseErrorActionPreference = $false
    & docker @DockerArguments 2>&1 | ForEach-Object {
        if (-not $Quiet) { Write-Host $_.ToString() }
    }
    return $LASTEXITCODE
}

function Initialize-LocalEnvironment {
    if (-not (Test-Path -LiteralPath $LocalEnvPath)) {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw "Docker CLI nebylo nalezeno. Nainstaluj a spusť Docker Desktop, potom úlohu zopakuj."
        }

        $randomBytes = New-Object byte[] 24
        $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $randomGenerator.GetBytes($randomBytes)
        $randomGenerator.Dispose()
        $passwordSuffix = ($randomBytes | ForEach-Object { $_.ToString("X2") }) -join ""
        $password = "Aa1!" + $passwordSuffix
        $localSettings = @(
            "APP_ENV=local"
            "TENANT_ID=dolphin"
            "DATABASE_BACKEND=sqlserver"
            "AZURE_SQL_HOST=127.0.0.1"
            "AZURE_SQL_PORT=1433"
            "AZURE_SQL_DB=ai_search_local"
            "AZURE_SQL_USER=sa"
            "AZURE_SQL_PASSWORD=$password"
            "AZURE_SQL_DRIVER=ODBC Driver 17 for SQL Server"
            "LOCAL_SQL_SA_PASSWORD=$password"
        )
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($LocalEnvPath, $localSettings, $utf8NoBom)
        Write-Output "Vytvořil jsem ignorovaný .env.local s náhodným heslem pouze pro lokální SQL Server."
    }
}

function Import-LocalEnvironment {
    Initialize-LocalEnvironment
    foreach ($line in Get-Content -LiteralPath $LocalEnvPath) {
        if ($line -match '^\s*([^#=\s]+)\s*=\s*(.*?)\s*$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
        }
    }

    if ($Tenant) { $env:TENANT_ID = $Tenant }

    if ($env:APP_ENV -ne "local" -or $env:DATABASE_BACKEND -ne "sqlserver") {
        throw ".env.local musí používat APP_ENV=local a DATABASE_BACKEND=sqlserver."
    }
    if ($env:AZURE_SQL_HOST -notin @("localhost", "127.0.0.1", "::1") -or $env:AZURE_SQL_DB -ne "ai_search_local") {
        throw ".env.local smí mířit pouze na lokální databázi ai_search_local."
    }
    if (-not $env:LOCAL_SQL_SA_PASSWORD -or $env:LOCAL_SQL_SA_PASSWORD -ne $env:AZURE_SQL_PASSWORD) {
        throw ".env.local musí obsahovat stejné lokální heslo v LOCAL_SQL_SA_PASSWORD a AZURE_SQL_PASSWORD."
    }
}

function Invoke-JhuHelper {
    param([string]$HelperAction)
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Chybí projektová .venv." }
    if ((($env:TENANT_ID -split '-')[0]).ToLowerInvariant() -notin @('jhu', 'ju')) {
        throw "Spravované JHU připojení je dostupné jen pro JHU tenant. Použij -Tenant jhu."
    }
    $env:JHU_CONNECTION_MODE = "managed"
    $env:JHU_HELPER_WORKSPACE = $ProjectRoot
    if (-not $env:JHU_KEY_VAULT_NAME) { $env:JHU_KEY_VAULT_NAME = $JhuVault }
    if (-not $env:JHU_API_USERNAME_SECRET) { $env:JHU_API_USERNAME_SECRET = "ju-ai-search-jhu-api-username-prod" }
    if (-not $env:JHU_API_PASSWORD_SECRET) { $env:JHU_API_PASSWORD_SECRET = "ju-ai-search-jhu-api-password-prod" }
    $helperArguments = @((Join-Path $ProjectRoot 'jhu_connection.py'), $HelperAction, '--tenant', $env:TENANT_ID)
    if ($HelperAction -eq 'start') {
        $helperArguments += @('--vault', $env:JHU_KEY_VAULT_NAME, '--profile', $JhuVpnProfile, '--wait')
    }
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    & $PythonPath @helperArguments 2>&1 | ForEach-Object { Write-Host $_.ToString() }
    return $LASTEXITCODE
}

switch ($Action) {
    "start-db" {
        Import-LocalEnvironment
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw "Docker CLI nebylo nalezeno. Nainstaluj a spusť Docker Desktop."
        }
        $dockerInfoExitCode = Invoke-LocalDocker -DockerArguments @("info") -Quiet
        if ($dockerInfoExitCode -ne 0) {
            throw "Docker Engine neběží nebo není dostupný. Spusť Rancher Desktop a počkej, až bude Engine připravený (Docker API na npipe). Pak zopakuj AI Search: start local app."
        }
        $composeExitCode = Invoke-LocalDocker -DockerArguments @("compose", "--env-file", $LocalEnvPath, "-f", "docker-compose.local.yml", "up", "-d")
        if ($composeExitCode -ne 0) { throw "Lokální SQL Server se nepodařilo spustit." }

        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $client = [System.Net.Sockets.TcpClient]::new()
            try {
                $connect = $client.BeginConnect("127.0.0.1", 1433, $null, $null)
                if ($connect.AsyncWaitHandle.WaitOne(1000) -and $client.Connected) {
                    $client.EndConnect($connect)
                    $ready = $true
                    break
                }
            }
            catch { }
            finally { $client.Dispose() }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) {
            Invoke-LocalDocker -DockerArguments @("logs", "--tail", "40", "ai-search-sql-local") | Out-Null
            throw "SQL Server nezačal do 120 sekund naslouchat na portu 1433."
        }
        Write-Output "Lokální SQL Server naslouchá na 127.0.0.1:1433; data zůstávají v Docker volume."
    }
    "stop-db" {
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            $composeExitCode = Invoke-LocalDocker -DockerArguments @("compose", "--env-file", $LocalEnvPath, "-f", "docker-compose.local.yml", "down")
            if ($composeExitCode -ne 0) { throw "Lokální SQL Server se nepodařilo zastavit." }
        }
    }
    "backend" {
        Import-LocalEnvironment
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            throw "Chybí .venv. Vytvoř prostředí příkazem: python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt"
        }
        if ($JhuManaged -or $env:JHU_CONNECTION_MODE -eq 'managed') {
            $helperExit = Invoke-JhuHelper -HelperAction 'start'
            if ($helperExit -ne 0) {
                Write-Warning 'JHU helper není připravený. Backend se spustí s ostatními modely; JHU bude nedostupné.'
            }
        }
        & $PythonPath -m uvicorn app.main:app --reload --reload-dir (Join-Path $ProjectRoot "app") --host 127.0.0.1 --port 8000
        exit $LASTEXITCODE
    }
    "test" {
        $env:APP_ENV = "test"
        $env:JHU_CONNECTION_MODE = 'direct'
        Get-ChildItem Env: | Where-Object { $_.Name -match '^AZURE_(OPENAI|SQL|STORAGE|KEY_VAULT)' } | ForEach-Object {
            Remove-Item -Path "Env:$($_.Name)"
        }
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            throw "Chybí .venv. Vytvoř prostředí příkazem: python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt"
        }
        & $PythonPath -m pytest
        exit $LASTEXITCODE
    }
    "start-jhu" {
        Import-LocalEnvironment
        exit (Invoke-JhuHelper -HelperAction 'start')
    }
    "status-jhu" {
        Import-LocalEnvironment
        exit (Invoke-JhuHelper -HelperAction 'status')
    }
    "stop-jhu" {
        Import-LocalEnvironment
        exit (Invoke-JhuHelper -HelperAction 'stop')
    }
}
