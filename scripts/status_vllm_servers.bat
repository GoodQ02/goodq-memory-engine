@echo off
REM GoodQ4All vLLM Service Status Check
REM Shows status of the current injected vLLM + Ollama contract

call "%~dp0_lib\\interpreter_bindings.bat"
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

echo ========================================
echo vLLM Service Status
echo ========================================
echo.

pushd "%REPO_ROOT%" >nul
set "PYTHONPATH=%CD%"
"%CONDA_EXE%" run -n %GOODQ_CONDA_ENV% python scripts\test_llm_client.py
popd >nul

pause
