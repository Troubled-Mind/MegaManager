# MegaManager setup - installs everything needed to run the app: Python (via
# a local virtualenv), MegaCMD, and rclone. Safe to re-run any time; every
# step checks what's already present and skips it.
#
# Usage: right-click setup.bat -> Run, or from PowerShell: .\setup.ps1

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$failedSteps = @()

function Write-Info($msg)  { Write-Host "==> $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "WARNING $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "ERROR $msg" -ForegroundColor Red }

function Refresh-Path {
    # winget/choco write PATH changes to the registry, but this already-running
    # process won't see them until we re-read and merge both hives ourselves.
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# 1. Winget availability check
# ---------------------------------------------------------------------------
$hasWinget = Test-Command "winget"
if (-not $hasWinget) {
    Write-Warn2 "winget not found. It ships with Windows 10 (2004+) and Windows 11 - update 'App Installer' from the Microsoft Store to get it, then re-run this script for automatic installs. Continuing with manual-install fallbacks where possible."
}

# ---------------------------------------------------------------------------
# 2. Python 3
# ---------------------------------------------------------------------------
$pythonOk = $false
if (Test-Command "python") {
    try {
        $verOutput = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($verOutput) {
            $parts = $verOutput.Split('.')
            if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 9)) {
                $pythonOk = $true
            }
        }
    } catch {}
}

if (-not $pythonOk) {
    if ($hasWinget) {
        Write-Info "Python 3.9+ not found, installing via winget..."
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
        $pythonOk = Test-Command "python"
    }
    if (-not $pythonOk) {
        Write-Err "Could not install Python automatically. Download it from https://www.python.org/downloads/ (tick 'Add Python to PATH' during install), then re-run this script."
        $failedSteps += "python"
    } else {
        Write-Info "Python installed: $(& python --version)"
    }
} else {
    Write-Info "Python OK: $(& python --version)"
}

# ---------------------------------------------------------------------------
# 3. Virtual environment + pip requirements
# ---------------------------------------------------------------------------
if ($pythonOk) {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Info "Creating virtual environment in .venv..."
        python -m venv .venv
    }

    if (Test-Path ".venv\Scripts\python.exe") {
        Write-Info "Installing/updating Python dependencies..."
        & .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
        & .venv\Scripts\python.exe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to install requirements.txt"
            $failedSteps += "requirements"
        }
    } else {
        Write-Err "Failed to create .venv"
        $failedSteps += "venv"
    }
}

# ---------------------------------------------------------------------------
# 4. MegaCMD (no official winget package - uses Chocolatey, bootstrapping it
#    if needed, since MEGA's own download page requires JavaScript and can't
#    be scripted reliably)
# ---------------------------------------------------------------------------
if ((Test-Command "mega-cmd") -or (Test-Command "mega-login") -or (Test-Path "$env:LOCALAPPDATA\MEGAcmd\mega-cmd.exe")) {
    Write-Info "MegaCMD already installed."
    if (Test-Path "$env:LOCALAPPDATA\MEGAcmd") {
        $env:Path += ";$env:LOCALAPPDATA\MEGAcmd"
    }
} else {
    Write-Info "MegaCMD not found, installing via Chocolatey..."
    if (-not (Test-Command "choco")) {
        Write-Info "Chocolatey not found, installing it first..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        Refresh-Path
    }

    if (Test-Command "choco") {
        choco install megacmd -y
        Refresh-Path
        if (Test-Path "$env:LOCALAPPDATA\MEGAcmd") {
            $env:Path += ";$env:LOCALAPPDATA\MEGAcmd"
        }
    }

    if (-not ((Test-Command "mega-cmd") -or (Test-Path "$env:LOCALAPPDATA\MEGAcmd\mega-cmd.exe"))) {
        Write-Err "Could not auto-install MegaCMD. Download and run the installer from https://mega.io/cmd manually, then re-run this script (or set the path in Settings -> Core Config once MegaManager is running)."
        $failedSteps += "megacmd"
    } else {
        Write-Info "MegaCMD installed."
    }
}

# ---------------------------------------------------------------------------
# 5. rclone
# ---------------------------------------------------------------------------
if (Test-Command "rclone") {
    Write-Info "rclone already installed."
} else {
    if ($hasWinget) {
        Write-Info "rclone not found, installing via winget..."
        winget install --id Rclone.Rclone -e --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
    }
    if (-not (Test-Command "rclone")) {
        Write-Err "Could not install rclone automatically. Download it from https://rclone.org/downloads/, add it to PATH, then re-run this script (or set the path in Settings -> Core Config)."
        $failedSteps += "rclone"
    } else {
        Write-Info "rclone installed."
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
if ($failedSteps.Count -eq 0) {
    Write-Info "Setup complete. Run run.bat to start MegaManager."
    exit 0
} else {
    Write-Err ("Setup finished with problems in: " + ($failedSteps -join ", "))
    Write-Err "Fix the steps above and re-run setup.bat, or run run.bat anyway if the app can work without them for now."
    exit 1
}
