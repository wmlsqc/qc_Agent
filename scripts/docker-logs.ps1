Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    docker compose logs -f agent-project
}
finally {
    Pop-Location
}
