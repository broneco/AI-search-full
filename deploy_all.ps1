# Retired combined deployment entrypoint. Kept to fail existing callers safely.

param (
    [string]$Client = "showcase",
    [string]$Environment = "dev",
    [switch]$ForceLogin
)

$ErrorActionPreference = "Continue"

# A read-only backend plan must never cascade into legacy frontend deployments.
throw "Combined deployment is disabled. Review deploy_backend.ps1 (plan by default), then deploy frontends separately after migration approval."
