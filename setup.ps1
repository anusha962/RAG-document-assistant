# One-time setup for Windows. Run:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$py = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { throw "Python was not found. Install it from python.org and tick 'Add python.exe to PATH', then reopen PowerShell." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js was not found. Install the LTS version from nodejs.org, then reopen PowerShell." }

Write-Host "`n[1/3] Setting up the backend..." -ForegroundColor Cyan
Set-Location "$root\backend"
& $py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed. Read the error above." }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
& .\.venv\Scripts\python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw "Database setup failed. Read the error above." }

Write-Host "`n[2/3] Setting up the frontend..." -ForegroundColor Cyan
Set-Location "$root\frontend"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed. Read the error above." }

Write-Host "`n[3/3] Done." -ForegroundColor Green
Write-Host "Start the app with:  powershell -ExecutionPolicy Bypass -File .\run.ps1"
