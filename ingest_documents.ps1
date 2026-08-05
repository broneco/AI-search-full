# Automated Document Ingestion Script for Azure Multi-Client AI Search
# Usage:
#   .\ingest_documents.ps1 -Client dolphin -Environment prod -FullRefresh
#   .\ingest_documents.ps1 -Client alzbeta -Environment prod -FullRefresh
#   .\ingest_documents.ps1 -Client dolphin -Environment dev

param (
    [string]$Client = "dolphin",
    [string]$Environment = "prod",
    [switch]$FullRefresh = $true,
    [string]$DataDir = "data"
)

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8

$ClientClean = $Client.ToLower()
$EnvClean = $Environment.ToLower()
$PostgresDbName = "${ClientClean}_ai_search_${EnvClean}"
$BlobContainer = "${ClientClean}-originals-${EnvClean}"
$TenantId = "${ClientClean}-${EnvClean}"

Write-Host ""
Write-Host "==== AI Search - Document Ingestion ====" -ForegroundColor Cyan
Write-Host "[INFO] Client:          $ClientClean" -ForegroundColor White
Write-Host "[INFO] Environment:     $EnvClean" -ForegroundColor White
Write-Host "[INFO] Target DB:       $PostgresDbName" -ForegroundColor White
Write-Host "[INFO] Blob Container:  $BlobContainer" -ForegroundColor White
Write-Host "[INFO] Tenant ID:       $TenantId" -ForegroundColor White
Write-Host "[INFO] Data Directory:  $DataDir" -ForegroundColor White

# Set environment variables
$env:APP_ENV = $EnvClean
$env:TENANT_ID = $TenantId
$env:POSTGRES_DB = $PostgresDbName
$env:AZURE_BLOB_CONTAINER_ORIGINALS = $BlobContainer

$PythonPath = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonPath)) {
    $PythonPath = "python"
}

if ($FullRefresh) {
    Write-Host "[1/1] Spoustim Full-Refresh indexaci z adresare '$DataDir' pro $ClientClean ($EnvClean)..." -ForegroundColor Yellow
    & $PythonPath full_refresh_ingest.py
} else {
    Write-Host "[1/1] Spoustim inkrementalni indexaci z adresare '$DataDir' pro $ClientClean ($EnvClean)..." -ForegroundColor Yellow
    & $PythonPath ingest.py
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Indexace dokumentu pro $ClientClean ($EnvClean) byla uspesne dokoncena!" -ForegroundColor Green
} else {
    Write-Error "Indexace dokumentu selhala."
}
