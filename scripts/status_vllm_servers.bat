@echo off
REM GoodQ4All vLLM Server Status Check
REM Shows status of all LLM servers

call "%~dp0_lib\\interpreter_bindings.bat"

echo ========================================
echo vLLM Server Status
echo ========================================
echo.

"%CONDA_EXE%" run -n goodq_core python L:\goodq4all\scripts\test_llm_client.py

pause
