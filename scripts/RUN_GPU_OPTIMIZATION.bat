@echo off
REM =============================================================================
REM  GoodQ4All GPU Pipeline Optimization
REM  Runs comprehensive GPU performance testing and optimization
REM =============================================================================

call "%~dp0_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"

echo.
echo ================================================================================
echo   GoodQ4All GPU Pipeline Optimization Suite
echo ================================================================================
echo.
echo This will run a comprehensive GPU optimization process:
echo   1. Verify GPU is available and configured
echo   2. Run baseline pipeline test with monitoring
echo   3. Analyze GPU usage per step
echo   4. Optimize memory allocations
echo   5. Run validation tests
echo.
echo This may take 1-2 hours depending on video length
echo.
pause

echo.
echo ================================================================================
echo  Step 1: Verifying GPU Configuration
echo ================================================================================
echo.

"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\test_gpu_config.py
if errorlevel 1 (
    echo.
    echo ERROR: GPU configuration test failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo  Step 2: Running Monitored Pipeline Test
echo ================================================================================
echo.

"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\monitor_gpu_pipeline.py
if errorlevel 1 (
    echo.
    echo ERROR: Pipeline monitoring failed
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo  Optimization Complete!
echo ================================================================================
echo.
echo Results saved in: %REPO_ROOT%\logs\gpu_optimization\
echo GPU configurations updated in: %REPO_ROOT%\steps\common\gpu_config.py
echo.
echo Next steps:
echo   1. Review the optimization report
echo   2. Run production pipeline with optimized settings
echo   3. Monitor for any issues
echo.
pause
