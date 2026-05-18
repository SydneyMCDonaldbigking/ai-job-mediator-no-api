$ErrorActionPreference = "Stop"

function Test-PythonImport {
    param([string]$ModuleName)
    python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

Write-Host "Checking local environment..."

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH."
}

python --version

$requiredModules = @("uvicorn", "fastapi", "litellm", "chainlit", "playwright")
$missing = @()
foreach ($module in $requiredModules) {
    if (Test-PythonImport -ModuleName $module) {
        Write-Host "[ok] Python module '$module'"
    }
    else {
        Write-Host "[missing] Python module '$module'"
        $missing += $module
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Install missing dependencies before starting the app."
}

cmd /c "python -m playwright install --dry-run chromium >nul 2>nul" | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[ok] Playwright Chromium is installed or installable"
}
else {
    Write-Host "[warn] Playwright Chromium may be missing. Run: python -m playwright install chromium"
}

$resolvedPort =
    if ($env:BACKEND_PORT) { $env:BACKEND_PORT }
    elseif ($env:PORT) { $env:PORT }
    else { "8001" }
$resolvedBackendUrl =
    if ($env:BACKEND_URL) { $env:BACKEND_URL }
    else { "http://127.0.0.1:$resolvedPort" }

Write-Host ""
Write-Host "Resolved backend port: $resolvedPort"
Write-Host "Resolved backend URL: $resolvedBackendUrl"
