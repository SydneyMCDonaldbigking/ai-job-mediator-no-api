param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH."
}

$resolvedBackendUrl = $env:BACKEND_URL
if (-not $resolvedBackendUrl) {
    if ($env:BACKEND_PORT) {
        $resolvedBackendUrl = "http://127.0.0.1:$($env:BACKEND_PORT)"
    }
    elseif ($env:PORT) {
        $resolvedBackendUrl = "http://127.0.0.1:$($env:PORT)"
    }
    else {
        $resolvedBackendUrl = "http://127.0.0.1:8001"
    }
}

$env:BACKEND_URL = $resolvedBackendUrl
if (-not $env:CHAINLIT_AUTH_SECRET) {
    $env:CHAINLIT_AUTH_SECRET = "local-dev-secret-change-me-2026-very-long"
}

Write-Host "Starting frontend on http://${HostAddress}:$Port"
Write-Host "Using backend $resolvedBackendUrl"
Push-Location $frontendDir
try {
    python -m chainlit run app.py --headless --host $HostAddress --port $Port
}
finally {
    Pop-Location
}
