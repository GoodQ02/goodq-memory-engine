@echo off
cd /d L:\goodq4all
echo Stopping GoodQ services...
pwsh -Command "& { . .\scripts\stop_goodq_services.ps1 }"
pause
