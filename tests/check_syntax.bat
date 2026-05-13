@echo off
setlocal
call "%~dp0..\scripts\_lib\interpreter_bindings.bat"
set "CONDA_TARGET_FLAG=-n"
set "CONDA_TARGET_VALUE=%GOODQ_CONDA_ENV%"
if exist "%GOODQ_CONDA_ENV%\python.exe" (
    set "CONDA_TARGET_FLAG=-p"
)

pushd "%~dp0.."
"%CONDA_EXE%" run %CONDA_TARGET_FLAG% "%CONDA_TARGET_VALUE%" python -c "import cli.run_ingestion; print('cli.run_ingestion import ok')"
set "GOODQ_TEST_EXIT=%ERRORLEVEL%"
popd

exit /b %GOODQ_TEST_EXIT%
