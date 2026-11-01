# PowerShell Launcher for UWB Antenna Engineering Workflow
# Usage: .\run_antenna.ps1 [-Yes]

param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "   UWB ANTENNA ENGINEERING — POWERSHELL ONE-COMMAND LAUNCHER" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Locate or create Python virtual environment
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/3] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv (Join-Path $ProjectRoot ".venv")
    if (-not (Test-Path $VenvPython)) {
        Write-Error "Failed to initialize .venv. Ensure Python is installed on PATH."
        exit 1
    }
}

# 2. Synchronize dependencies
Write-Host "[2/3] Checking dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -r (Join-Path $ProjectRoot "requirements.txt")

# Check PyAEDT on Windows (using verified ansys.aedt.core import)
$HasPyAEDT = & $VenvPython -c "from ansys.aedt.core import Hfss" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyAEDT for Windows HFSS simulation..." -ForegroundColor Yellow
    & $VenvPython -m pip install pyaedt
}

# 3. Launch main orchestration workflow
Write-Host "[3/3] Executing main.py..." -ForegroundColor Green
$ArgsList = @()
if ($Yes) {
    $ArgsList += "-y"
}

& $VenvPython (Join-Path $ProjectRoot "main.py") @ArgsList
Write-Host "Workflow finished with exit code: $LASTEXITCODE" -ForegroundColor Cyan
