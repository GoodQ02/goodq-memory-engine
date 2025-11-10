# Quick test of agent system

Write-Host "=== Quick Agent Test ===" -ForegroundColor Cyan

cd L:\goodq4all
conda activate base

Write-Host "`nTesting agent setup..." -ForegroundColor Yellow
python agents/pipeline_integration.py

Write-Host "`nTest complete!" -ForegroundColor Green
Write-Host "`nCheck L:\goodq4all\logs\ for detailed results" -ForegroundColor Yellow
