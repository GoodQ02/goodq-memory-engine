<#
.SYNOPSIS
    Post-install Qdrant health check for GoodQ4All offline installer.
.DESCRIPTION
    Exercises the installed Qdrant binary:
    1. Start Qdrant on an ephemeral port with temp storage
    2. Wait for HTTP readiness on /readyz
    3. Create a test collection, insert a vector, query it, delete collection
    4. Stop Qdrant and clean up
.PARAMETER InstallDir
    Root directory of the GoodQ4All installation.
    Defaults to $env:ProgramFiles\GoodQ4All
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\GoodQ4All"
)

$ErrorActionPreference = "Stop"
$testPort = 16333 + (Get-Random -Maximum 1000)
$tempStorage = Join-Path $env:TEMP "goodq_qdrant_smoke_$testPort"
$qdrantExe = Join-Path $InstallDir "qdrant\qdrant.exe"
$baseUrl = "http://127.0.0.1:$testPort"
$result = @{ pass = $false; port = $testPort; errors = @() }
$qdrantProc = $null

try {
    # Pre-check
    if (-not (Test-Path $qdrantExe)) {
        throw "Qdrant binary not found at $qdrantExe"
    }

    # Create temp storage
    New-Item -ItemType Directory -Path $tempStorage -Force | Out-Null

    # Start Qdrant
    Write-Host "Starting Qdrant on port $testPort..." -ForegroundColor Cyan
    $env:QDRANT__SERVICE__HTTP_PORT = "$testPort"
    $env:QDRANT__STORAGE__STORAGE_PATH = $tempStorage
    $qdrantProc = Start-Process -FilePath $qdrantExe -PassThru -NoNewWindow -RedirectStandardOutput "$env:TEMP\qdrant_out.tmp" -RedirectStandardError "$env:TEMP\qdrant_err.tmp"

    # Wait for readiness (max 30s)
    $deadline = (Get-Date).AddSeconds(30)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Uri "$baseUrl/readyz" -TimeoutSec 2 -ErrorAction Stop
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw "Qdrant did not become ready within 30 seconds" }
    Write-Host "  [OK] Qdrant ready on port $testPort" -ForegroundColor Green

    # Create test collection
    $collectionName = "_smoke_test_collection"
    $createBody = @{ vectors = @{ size = 4; distance = "Cosine" } } | ConvertTo-Json -Depth 3
    Invoke-RestMethod -Uri "$baseUrl/collections/$collectionName" -Method Put -Body $createBody -ContentType "application/json" -ErrorAction Stop | Out-Null
    Write-Host "  [OK] Created test collection" -ForegroundColor Green

    # Insert a vector
    $insertBody = @{ points = @(@{ id = 1; vector = @(0.1, 0.2, 0.3, 0.4); payload = @{ test = "smoke" } }) } | ConvertTo-Json -Depth 4
    Invoke-RestMethod -Uri "$baseUrl/collections/$collectionName/points" -Method Put -Body $insertBody -ContentType "application/json" -ErrorAction Stop | Out-Null
    Write-Host "  [OK] Inserted test vector" -ForegroundColor Green

    # Query
    $queryBody = @{ vector = @(0.1, 0.2, 0.3, 0.4); top = 1 } | ConvertTo-Json -Depth 3
    $queryResult = Invoke-RestMethod -Uri "$baseUrl/collections/$collectionName/points/search" -Method Post -Body $queryBody -ContentType "application/json" -ErrorAction Stop
    if ($queryResult.result.Count -ge 1) {
        Write-Host "  [OK] Query returned results" -ForegroundColor Green
    } else {
        throw "Query returned no results"
    }

    # Delete collection
    Invoke-RestMethod -Uri "$baseUrl/collections/$collectionName" -Method Delete -ErrorAction Stop | Out-Null
    Write-Host "  [OK] Cleaned up test collection" -ForegroundColor Green

    $result.pass = $true
    Write-Host "`n[PASS] Qdrant smoke test passed." -ForegroundColor Green

} catch {
    $result.errors += $_.Exception.Message
    Write-Host "`n[FAIL] Qdrant smoke test failed: $($_.Exception.Message)" -ForegroundColor Red

} finally {
    # Stop Qdrant
    if ($qdrantProc -and -not $qdrantProc.HasExited) {
        Stop-Process -Id $qdrantProc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  Qdrant process stopped." -ForegroundColor Gray
    }
    # Clear environment variables
    $env:QDRANT__SERVICE__HTTP_PORT = $null
    $env:QDRANT__STORAGE__STORAGE_PATH = $null
    # Clean up temp storage
    if (Test-Path $tempStorage) {
        Remove-Item -Recurse -Force $tempStorage -ErrorAction SilentlyContinue
    }
}

$result | ConvertTo-Json -Depth 3
if ($result.pass) { exit 0 } else { exit 1 }
