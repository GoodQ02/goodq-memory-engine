# GoodQ4All Developer Environment Auto-Start Script
# Runs Qdrant, API Server, and Watchdog under the conda environment in the background.

$ErrorActionPreference = 'SilentlyContinue'

$rootDir = 'L:\GOODCUBE\projects\goodq4all_public'

# Import interpreter bindings to locate conda and environment python
. "$rootDir\scripts\_lib\interpreter_bindings.ps1"
$pyExe = Get-GoodQPythonExe

# 1. Start Qdrant service if present
Write-Host "Checking Qdrant service..."
Start-Service -Name "GoodQ_Qdrant"

# 2. Stop any existing API or Watchdog instances to prevent conflicts
Write-Host "Checking for existing developer service processes..."

# Stop process holding port 30000
$connections = Get-NetTCPConnection -LocalPort 30000 -ErrorAction SilentlyContinue
foreach ($conn in $connections) {
    if ($conn.OwningProcess -and $conn.OwningProcess -ne $PID) {
        Write-Host "Stopping existing API process (PID $($conn.OwningProcess)) on port 30000..."
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

# Stop any other API server Python instances
$apiProcs = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | 
             Where-Object { $_.CommandLine -match "api.server" }
foreach ($p in $apiProcs) {
    Write-Host "Stopping duplicate API process (PID $($p.ProcessId))..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# Stop any existing Watchdog Python instances
$watchdogProcs = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | 
                  Where-Object { $_.CommandLine -match "cli.watchdog" }
foreach ($p in $watchdogProcs) {
    Write-Host "Stopping existing Watchdog process (PID $($p.ProcessId))..."
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

# 3. Start API Server (in background, minimized/hidden)
Write-Host "Starting API Server..."
Start-Process powershell -ArgumentList "-NoExit -WindowStyle Minimized -Command `"& '$pyExe' -m api.server`"" -WorkingDirectory $rootDir

Start-Sleep -Seconds 2

# 4. Start Watchdog (in background, minimized/hidden)
Write-Host "Starting Ingestion Watchdog..."
Start-Process powershell -ArgumentList "-NoExit -WindowStyle Minimized -Command `"& '$pyExe' -m cli.watchdog`"" -WorkingDirectory $rootDir

Write-Host "GoodQ4All developer services triggered/restarted in background!"



