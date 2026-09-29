# Launches MegaManager. Runs setup.ps1 automatically first if the virtual
# environment or dependencies aren't there yet.

Set-Location -Path $PSScriptRoot

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Test-NeedsSetup {
    if (-not (Test-Path ".venv\Scripts\python.exe")) { return $true }

    & .venv\Scripts\python.exe -c "import sqlalchemy" 2>$null
    if ($LASTEXITCODE -ne 0) { return $true }

    if (Test-Path "$env:LOCALAPPDATA\MEGAcmd") { $env:Path += ";$env:LOCALAPPDATA\MEGAcmd" }
    if (-not ((Test-Command "mega-cmd") -or (Test-Command "mega-login"))) { return $true }
    if (-not (Test-Command "rclone")) { return $true }

    return $false
}

if (Test-NeedsSetup) {
    Write-Host "==> First run (or missing dependencies) detected, running setup.ps1 first..." -ForegroundColor Green
    & "$PSScriptRoot\setup.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING setup.ps1 reported problems - trying to start anyway." -ForegroundColor Yellow
    }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "ERROR Could not find a working Python virtual environment. Run setup.bat manually to see what failed." -ForegroundColor Red
    exit 1
}

& .venv\Scripts\python.exe server.py
