@echo off
REM GoodQ4All - Qdrant Health Check
REM Quick validation that Qdrant is running and configured correctly

echo.
echo ========================================
echo   Qdrant Health Check
echo ========================================
echo.

REM Test if Qdrant is running
echo [1/4] Checking if Qdrant is running...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:6333/collections -TimeoutSec 5; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" > nul 2>&1
if errorlevel 1 (
    echo [FAIL] Qdrant is not responding on port 6333
    echo.
    echo Preferred fix:
    echo   Service install/repair: INSTALL_QDRANT_SERVICE.bat
    echo   Start existing service: net start GoodQ_Qdrant
    echo.
    echo Foreground testing fallback only:
    echo   START_QDRANT.bat
    echo.
    pause
    exit /b 1
)
echo [OK] Qdrant is running

echo.
echo [2/4] Checking collections...
powershell -Command "$r = Invoke-RestMethod http://localhost:6333/collections; $cols = $r.result.collections; if ($cols.Count -eq 0) { Write-Host '[WARN] No collections found - run INIT_QDRANT.bat' -ForegroundColor Yellow } else { Write-Host '[OK] Found' $cols.Count 'collections' -ForegroundColor Green; $cols | ForEach-Object { Write-Host '  -' $_.name -ForegroundColor Gray } }"

echo.
echo [3/4] Checking config.yaml...
findstr /C:"enabled: true" configs\config.yaml > nul 2>&1
if errorlevel 1 (
    echo [WARN] Qdrant may not be enabled in config.yaml
    echo Verify: configs\config.yaml -^> qdrant.enabled should be true
) else (
    echo [OK] Qdrant enabled in config.yaml
)

echo.
echo [4/4] Testing dashboard...
echo Dashboard URL: http://localhost:6333/dashboard
echo.

echo ========================================
echo   Health Check Complete
echo ========================================
echo.
echo Status: Qdrant is operational
echo.
echo Next steps:
echo   - View dashboard: http://localhost:6333/dashboard
echo   - Initialize collections: INIT_QDRANT.bat
echo   - Run bootstrap validation: scripts\bootstrap_validate.bat
echo.
pause
