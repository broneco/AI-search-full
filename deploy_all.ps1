# Master Automated Deployment Script (Backend + User Frontend + Admin Frontend)
# Usage:
#   .\deploy_all.ps1 -Client ju -Environment prod
#   .\deploy_all.ps1 -Client ju -Environment prod -ForceLogin

param (
    [string]$Client = "showcase",
    [string]$Environment = "dev",
    [switch]$ForceLogin
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  AI SEARCH - FULL AUTOMATED DEPLOYMENT ($Client / $Environment)" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$backendArgs = @{
    Client = $Client
    Environment = $Environment
}
if ($ForceLogin) {
    $backendArgs["ForceLogin"] = $true
}

Write-Host "`n[1/3] Spustam nasazeni Backendu (Azure Container App)..." -ForegroundColor Yellow
& .\deploy_backend.ps1 @backendArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Nasazeni backendu selhalo (Exit code $LASTEXITCODE). Prerusuji nasazeni." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[2/3] Spustam nasazeni Uzivatelskeho Frontendu (Static Web App)..." -ForegroundColor Yellow
& .\deploy_frontend.ps1 -Client $Client -Environment $Environment -AppType user
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Nasazeni uzivatelskeho frontendu selhalo. Prerusuji nasazeni." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[3/3] Spustam nasazeni Administracniho Frontendu (Static Web App)..." -ForegroundColor Yellow
& .\deploy_frontend.ps1 -Client $Client -Environment $Environment -AppType admin
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Nasazeni administracniho frontendu selhalo. Prerusuji nasazeni." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  [SUCCESS] VSECHNA NASAZENI DOKONCENA PRO TENANT '$Client' ($Environment)!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
