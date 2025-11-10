@echo off
REM Test progress tracking with the sample video
REM This script will process a sample and monitor progress in real-time

echo ================================================================================
echo  GoodQ Progress Tracking Test
echo ================================================================================
echo.
echo [1/3] Clearing previous progress...
del /Q "L:\goodq4all\logs\progress.json" 2>nul

echo [2/3] Starting API server in background...
start "GoodQ API Server" /MIN cmd /c "conda run --no-capture-output -n goodq_zenml python L:\goodq4all\api_server.py"

timeout /t 3 /nobreak >nul

echo [3/3] Starting ingestion with progress tracking...
echo.
echo ================================================================================
echo  Monitor progress at: http://localhost:3000
echo  Progress file: L:\goodq4all\logs\progress.json
echo ================================================================================
echo.

REM Use the smaller sample video for faster testing
conda run --no-capture-output -n goodq_zenml python -m cli.run_ingestion ^
  --input-dir "L:\goodq4all\import_inbox" ^
  --workspace "L:\goodq4all\logs\test_progress" ^
  --output "L:\goodq4all\logs\test_progress_results.json" ^
  --force ^
  --verbose

echo.
echo ================================================================================
echo  Processing complete! Check the results.
echo ================================================================================
pause
