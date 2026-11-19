[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$virtualEnvironmentPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"

if (Test-Path $virtualEnvironmentPython) {
    $python = $virtualEnvironmentPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3.11 or newer was not found. Install Python and run the setup steps in README.md."
    }
    $python = $pythonCommand.Source
}

Push-Location $repositoryRoot
try {
    & $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 or newer is required."
    }

    & $python -c "import fastapi, httpx, uvicorn"
    if ($LASTEXITCODE -ne 0) {
        throw 'Project dependencies are missing. Run: .\.venv\Scripts\python.exe -m pip install -e ".[dev]"'
    }

    $generatedApiKey = [string]::IsNullOrWhiteSpace($env:DIAGNOSTICS_API_KEY)
    if ($generatedApiKey) {
        $randomBytes = New-Object byte[] 32
        $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $randomGenerator.GetBytes($randomBytes)
        } finally {
            $randomGenerator.Dispose()
        }
        $env:DIAGNOSTICS_API_KEY = [Convert]::ToBase64String($randomBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    }

    if ($generatedApiKey) {
        Write-Host "Generated a temporary API key for this server process:"
        Write-Host $env:DIAGNOSTICS_API_KEY
    } else {
        Write-Host "Using DIAGNOSTICS_API_KEY from the environment."
    }
    Write-Host "Starting Ops Diagnostics at http://127.0.0.1:$Port"
    Write-Host "Press Ctrl+C to stop the server."

    & $python -m uvicorn ops_diagnostics.main:app --reload --app-dir src --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "The Ops Diagnostics server exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
