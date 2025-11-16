# ===================================================================
# GoodQ4All - Production Reset Script
# ===================================================================
# Clears all test data, caches, and artifacts for fresh production run
# ===================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GoodQ4All Production Reset" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$dataPath = "L:\goodq4all\data"

# Stop any running servers first
Write-Host "[1/10] Checking for running servers..." -ForegroundColor Yellow
$serverProcesses = Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*api_server*" }
if ($serverProcesses) {
    Write-Host "  → Stopping API server processes..." -ForegroundColor Yellow
    $serverProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# 1. Delete all database files (keeping structure)
Write-Host "[2/10] Clearing databases..." -ForegroundColor Yellow
$dbFiles = @(
    "$dataPath\goodq.db",
    "$dataPath\goodq_memory.db",
    "$dataPath\knowledge_graph.db",
    "$dataPath\memory.db",
    "$dataPath\unified_goodq.db",
    "$dataPath\test_knowledge_graph.db",
    "$dataPath\memory_partial.db"
)
foreach ($db in $dbFiles) {
    if (Test-Path $db) {
        Remove-Item $db -Force
        Write-Host "  ✓ Removed: $(Split-Path $db -Leaf)" -ForegroundColor Green
    }
}

# 2. Clear backup databases
Write-Host "[3/10] Clearing database backups..." -ForegroundColor Yellow
Get-ChildItem "$dataPath\*backup*.db" | Remove-Item -Force
Write-Host "  ✓ Removed all backup databases" -ForegroundColor Green

# 3. Clear FAISS indices
Write-Host "[4/10] Clearing FAISS indices..." -ForegroundColor Yellow
if (Test-Path "$dataPath\faiss_indices") {
    Get-ChildItem "$dataPath\faiss_indices\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared FAISS indices" -ForegroundColor Green
}

# 4. Clear processed files
Write-Host "[5/10] Clearing processed files..." -ForegroundColor Yellow
if (Test-Path "$dataPath\processed") {
    Get-ChildItem "$dataPath\processed\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared processed directory" -ForegroundColor Green
}

# 5. Clear processing temp files
Write-Host "[6/10] Clearing processing temp files..." -ForegroundColor Yellow
if (Test-Path "$dataPath\processing") {
    Get-ChildItem "$dataPath\processing\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared processing directory" -ForegroundColor Green
}

# 6. Clear output files
Write-Host "[7/10] Clearing output files..." -ForegroundColor Yellow
if (Test-Path "$dataPath\output") {
    Get-ChildItem "$dataPath\output\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared output directory" -ForegroundColor Green
}

# 7. Clear temp files
Write-Host "[8/10] Clearing temp files..." -ForegroundColor Yellow
if (Test-Path "$dataPath\temp") {
    Get-ChildItem "$dataPath\temp\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared temp directory" -ForegroundColor Green
}

# 8. Clear testing artifacts
Write-Host "[9/10] Clearing testing artifacts..." -ForegroundColor Yellow
if (Test-Path "$dataPath\testing") {
    Get-ChildItem "$dataPath\testing\*" -Recurse | Remove-Item -Force -Recurse
    Write-Host "  ✓ Cleared testing directory" -ForegroundColor Green
}

# 9. Clear workflow logs
Write-Host "[10/10] Clearing workflow logs..." -ForegroundColor Yellow
if (Test-Path "$dataPath\workflow_logs") {
    Get-ChildItem "$dataPath\workflow_logs\*.log" | Remove-Item -Force
    Write-Host "  ✓ Cleared workflow logs" -ForegroundColor Green
}

# 10. Clear exception audit
if (Test-Path "$dataPath\exception_audit.json") {
    Remove-Item "$dataPath\exception_audit.json" -Force
    Write-Host "  ✓ Cleared exception audit" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✓ Production Reset Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Place your video file in: L:\goodq4all\data\import_inbox\" -ForegroundColor White
Write-Host "  2. Launch server: .\scripts\launch_server.bat" -ForegroundColor White
Write-Host "  3. Open browser: http://localhost:3000" -ForegroundColor White
Write-Host ""
