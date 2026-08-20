@echo off
REM Shared interpreter binding helpers for GoodQ4All batch scripts.
REM Sets:
REM   - GOODQ_WSL_DISTRO (default: Ubuntu)
REM   - GOODQ_CONDA_ENV (default: goodq_core)
REM   - CONDA_EXE (best-effort full path to conda.exe/conda.bat; fallback: conda)
REM   - PYTHONNOUSERSITE=1 to keep user-site packages out of GoodQ runtimes

if exist "%~dp0..\..\.env.local" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\..\.env.local") do (
    if "%%A"=="GOODQ_WSL_DISTRO" if "%GOODQ_WSL_DISTRO%"=="" set "GOODQ_WSL_DISTRO=%%B"
    if "%%A"=="GOODQ_CONDA_ENV" if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=%%B"
  )
)

if "%GOODQ_WSL_DISTRO%"=="" (
  for /f "tokens=1 delims= " %%I in ('powershell -NoProfile -Command "try { $first = (wsl.exe -l -q 2>$null | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1); if ($first) { ($first -replace \"`0\", \"\").Trim() } } catch {}"') do (
    if not "%%I"=="" set "GOODQ_WSL_DISTRO=%%I"
  )
)

if "%GOODQ_WSL_DISTRO%"=="" set "GOODQ_WSL_DISTRO=Ubuntu"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"
set "PYTHONNOUSERSITE=1"

if defined CONDA_EXE (
  if exist "%CONDA_EXE%" (
    for %%I in ("%CONDA_EXE%") do (
      if /I "%%~xI"==".bat" if exist "%%~dpI..\Scripts\conda.exe" set "CONDA_EXE=%%~dpI..\Scripts\conda.exe"
    )
    goto :eof
  )
)

if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
  set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
  goto :eof
)

if exist "%USERPROFILE%\miniconda3\Scripts\conda.bat" (
  set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.bat"
  goto :eof
)

if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" (
  set "CONDA_EXE=%USERPROFILE%\miniconda3\condabin\conda.bat"
  goto :eof
)

if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
  set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe"
  goto :eof
)

if exist "%USERPROFILE%\anaconda3\Scripts\conda.bat" (
  set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.bat"
  goto :eof
)

if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
  set "CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe"
  goto :eof
)

if exist "C:\ProgramData\miniconda3\Scripts\conda.bat" (
  set "CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.bat"
  goto :eof
)

for /f "delims=" %%I in ('where conda 2^>nul') do (
  set "CONDA_EXE=%%I"
  goto :eof
)

set "CONDA_EXE=conda"
goto :eof

