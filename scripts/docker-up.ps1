Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    docker compose up -d --build
    docker compose ps
}
finally {
    Pop-Location
}
