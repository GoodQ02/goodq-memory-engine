# GoodQ4All Developer Environment Auto-Start Script
# Runs Qdrant, API Server, and Watchdog under the conda environment in the background.

$ErrorActionPreference = 'SilentlyContinue'

$rootDir = 'L:\GOODCUBE\projects\goodq4all'

# 1. Start Qdrant service if present
Write-Host "Checking Qdrant service..."
Start-Service -Name "GoodQ_Qdrant"

# 2. Start API Server (in background, minimized/hidden)
Write-Host "Starting API Server..."
Start-Process powershell -ArgumentList "-NoExit", "-WindowStyle", "Minimized", "-Command", "conda run -n goodq_core --no-capture-output python -m api.server" -WorkingDirectory $rootDir

Start-Sleep -Seconds 3

# 3. Start Watchdog (in background, minimized/hidden)
Write-Host "Starting Ingestion Watchdog..."
Start-Process powershell -ArgumentList "-NoExit", "-WindowStyle", "Minimized", "-Command", "conda run -n goodq_core --no-capture-output python -m cli.watchdog" -WorkingDirectory $rootDir

Write-Host "GoodQ4All developer services triggered in background!"
