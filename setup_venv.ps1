# PowerShell script to set up virtual environment for thermomaxing

$ErrorActionPreference = "Stop"

Write-Host "Setting up virtual environment..." -ForegroundColor Cyan

# Check if Python is installed
try {
    $pythonVersion = python --version
    Write-Host "Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# If a virtual environment already exists, don't remove it — just notify
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. If you are experiencing issues, remove the 'venv' directory and rerun this script." -ForegroundColor Yellow
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# Install requirements
Write-Host "Installing requirements..." -ForegroundColor Cyan
pip install -r requirements.txt

# Install Playwright browsers
Write-Host "Installing Playwright browsers..." -ForegroundColor Cyan
playwright install

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "To activate the virtual environment, run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
