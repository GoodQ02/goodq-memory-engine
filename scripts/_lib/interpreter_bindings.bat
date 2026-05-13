@echo off
REM Shared interpreter binding helpers for GoodQ4All batch scripts.
REM Sets:
REM   - GOODQ_WSL_DISTRO (default: Ubuntu)
REM   - GOODQ_CONDA_ENV (default: goodq_core)
REM   - CONDA_EXE (best-effort full path to conda.exe/conda.bat; fallback: conda)

if "%GOODQ_WSL_DISTRO%"=="" set "GOODQ_WSL_DISTRO=Ubuntu"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"

if defined CONDA_EXE (
  if exist "%CONDA_EXE%" goto :eof
)

for /f "delims=" %%I in ('where conda 2^>nul') do (
  set "CONDA_EXE=%%I"
  goto :eof
)

set "CONDA_EXE=conda"
goto :eof

