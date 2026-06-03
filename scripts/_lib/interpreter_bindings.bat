@echo off
REM Shared interpreter binding helpers for GoodQ4All batch scripts.
REM Sets:
REM   - GOODQ_WSL_DISTRO (default: Ubuntu)
REM   - GOODQ_CONDA_ENV (default: goodq_core)
REM   - CONDA_EXE (best-effort full path to conda.exe/conda.bat; fallback: conda)
REM   - PYTHONNOUSERSITE=1 to keep user-site packages out of GoodQ runtimes

if "%GOODQ_WSL_DISTRO%"=="" set "GOODQ_WSL_DISTRO=Ubuntu"
if "%GOODQ_CONDA_ENV%"=="" set "GOODQ_CONDA_ENV=goodq_core"
set "PYTHONNOUSERSITE=1"

if defined CONDA_EXE (
  if exist "%CONDA_EXE%" goto :eof
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

