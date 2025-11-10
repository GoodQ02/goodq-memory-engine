@echo off
REM GoodQ Analytics Launcher
REM Quick access to all analytics features

echo.
echo ===============================================
echo   GoodQ Analytics System
echo ===============================================
echo.
echo Select an option:
echo.
echo 1. Generate Global Dashboard
echo 2. Analyze Specific Video
echo 3. Interactive Query Session
echo 4. Run Full Analytics Test
echo 5. View Latest Dashboard
echo 6. View Quick Reference Guide
echo.
echo Q. Quit
echo.

set /p choice="Enter your choice: "

if "%choice%"=="1" goto dashboard
if "%choice%"=="2" goto analyze
if "%choice%"=="3" goto query
if "%choice%"=="4" goto test
if "%choice%"=="5" goto view_dashboard
if "%choice%"=="6" goto view_guide
if /i "%choice%"=="Q" goto end

echo Invalid choice!
pause
goto end

:dashboard
echo.
echo Generating global dashboard...
python analytics_dashboard.py --dashboard
echo.
echo Dashboard generated: output\analytics_dashboard.md
pause
goto end

:analyze
echo.
set /p video_path="Enter video path (or hash): "
echo.
echo Analyzing video: %video_path%
python analytics_dashboard.py "%video_path%"
echo.
echo Analysis complete!
pause
goto end

:query
echo.
echo Starting interactive query session...
echo Type 'quit' to exit the session
echo.
python analytics_query.py
pause
goto end

:test
echo.
echo Running comprehensive analytics test...
python test_phase7_analytics.py
echo.
pause
goto end

:view_dashboard
echo.
echo Opening dashboard...
start output\analytics_dashboard.md
goto end

:view_guide
echo.
echo Opening quick reference guide...
start ANALYTICS_QUICK_REFERENCE.md
goto end

:end
