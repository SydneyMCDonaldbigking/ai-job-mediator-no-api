param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH."
}

$resolvedPort = $Port
if ($resolvedPort -le 0) {
    if ($env:BACKEND_PORT) {
        $resolvedPort = [int]$env:BACKEND_PORT
    }
    elseif ($env:PORT) {
        $resolvedPort = [int]$env:PORT
    }
    else {
        $resolvedPort = 8001
    }
}

$env:BACKEND_PORT = "$resolvedPort"
if (-not $env:PORT) {
    $env:PORT = "$resolvedPort"
}

Write-Host "Starting backend on http://${HostAddress}:$resolvedPort"
Push-Location $backendDir
try {
    python -m uvicorn app.main:app --host $HostAddress --port $resolvedPort
}
finally {
    Pop-Location
}
