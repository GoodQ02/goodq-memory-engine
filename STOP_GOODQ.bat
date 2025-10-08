@echo off
cd /d L:\GoodQ_4_All
echo Stopping GoodQ services...
pwsh -Command "& { . .\scripts\stop_goodq_services.ps1 }"
pause
