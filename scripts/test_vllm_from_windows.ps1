# Quick Windows Test Script
# Save as test_vllm.ps1 and run from PowerShell

Write-Host "Testing vLLM from Windows..." -ForegroundColor Cyan

# Test 1: Can we reach the port?
Write-Host "`n1. Testing port 38005 connectivity..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:38005/v1/models" -UseBasicParsing -TimeoutSec 5
    Write-Host "   ✅ Port 38005 is reachable!" -ForegroundColor Green
    Write-Host "   Response:" -ForegroundColor Gray
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 3
} catch {
    Write-Host "   ❌ Cannot reach port 38005" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Try a chat completion
Write-Host "`n2. Testing chat completion..." -ForegroundColor Yellow
$modelId = if ($env:GOODQ_WSL_MODEL_PATH) { $env:GOODQ_WSL_MODEL_PATH } else { "Llama-3.2-1B-Instruct" }
$body = @{
    model = $modelId
    messages = @(
        @{
            role = "user"
            content = "Say: Test successful"
        }
    )
    max_tokens = 10
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:38005/v1/chat/completions" `
        -Method Post `
        -Body $body `
        -ContentType "application/json" `
        -TimeoutSec 30
    
    Write-Host "   ✅ Chat completion works!" -ForegroundColor Green
    Write-Host "   Response: $($response.choices[0].message.content)" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Chat completion failed" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nDone!" -ForegroundColor Cyan
