@echo off
setlocal ENABLEDELAYEDEXPANSION
REM Change to repo root (one level up from this script)
cd /d "%~dp0.."

echo [launch] Starting GoodQ dry run and Command Center...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\mission_launch.ps1" -Mode dryrun -EnvPrefix goodq

REM Launch Command Center in a new window with refresh
start powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\command_center.ps1" -Refresh

echo [launch] Done.

