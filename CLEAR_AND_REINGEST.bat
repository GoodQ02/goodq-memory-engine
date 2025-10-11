@echo off
REM Clear all databases and re-ingest to get complete AI analysis

echo.
echo ========================================================================
echo   CLEAR DATABASE AND RE-INGEST
echo ========================================================================
echo.
echo This will:
echo   1. Backup current databases
echo   2. Clear all memory databases
echo   3. Clear FAISS indexes
echo   4. Re-ingest files to run full AI analysis
echo.
echo Press Ctrl+C to cancel or
pause

echo.
echo [1/5] Backing up databases...
if exist "L:\goodq4all\data\memory.db" (
    copy "L:\goodq4all\data\memory.db" "L:\goodq4all\data\memory.db.backup_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.db"
)
if exist "L:\_DATA\GoodQ_Data\data\memory_db\memory.db" (
    copy "L:\_DATA\GoodQ_Data\data\memory_db\memory.db" "L:\_DATA\GoodQ_Data\data\memory_db\memory.db.backup_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.db"
)

echo [2/5] Clearing databases...
del /Q "L:\goodq4all\data\memory.db" 2>nul
del /Q "L:\_DATA\GoodQ_Data\data\memory_db\memory.db" 2>nul
del /Q "L:\_DATA\memory.db" 2>nul
del /Q "L:\_DATA\GoodQ_Data\memory.db" 2>nul
del /Q "L:\_DATA\GoodQ_Data\databases\memory.db" 2>nul

echo [3/5] Clearing FAISS indexes...
del /Q "L:\goodq4all\data\faiss\*" 2>nul
del /Q "L:\_DATA\GoodQ_Data\data\faiss_db\*" 2>nul

echo [4/5] Clearing step logs...
del /Q "L:\goodq4all\logs\steps.jsonl" 2>nul

echo [5/5] Starting fresh ingestion with full AI analysis...
echo.
echo Files in import_inbox will now be processed with FULL AI analysis.
echo Watch the Command Center to see progress.
echo.
pause

REM Start watchdog to process files
call "%~dp0START_WATCHDOG.bat"
