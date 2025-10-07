@echo off
cd /d L:\zenml_project
echo Stopping GoodQ services...
pwsh -Command "& { . .\scripts\stop_goodq_services.ps1 }"
pause
