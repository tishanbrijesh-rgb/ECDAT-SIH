$ErrorActionPreference = "Stop"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    Write-Host "[1/5] Python compilation"
    python -m compileall -q backend scanner scripts tests
    Assert-NativeSuccess "Python compilation"

    Write-Host "[2/5] Unit and API integration tests"
    python -W error::ResourceWarning -m unittest discover -s tests -v
    Assert-NativeSuccess "Unit and API integration tests"

    Write-Host "[3/5] Python dependency consistency"
    python -m pip check
    Assert-NativeSuccess "Python dependency consistency"

    Push-Location dashboard
    try {
        Write-Host "[4/5] Frontend formatting and production build"
        npm run format:check
        Assert-NativeSuccess "Frontend formatting"
        npm run build
        Assert-NativeSuccess "Frontend build"

        Write-Host "[5/5] Dependency advisory audit"
        npm audit --fetch-retries=0 --fetch-timeout=30000
        Assert-NativeSuccess "Dependency advisory audit"
    }
    finally {
        Pop-Location
    }

    Write-Host "ECDAT release verification passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
