# Quick Windows Test Script
# Save as test_vllm.ps1 and run from PowerShell

Write-Host "Testing vLLM from Windows..." -ForegroundColor Cyan

# Test 1: Can we reach the port?
Write-Host "`n1. Testing port 38005 connectivity..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:38005/v1/models" -TimeoutSec 15
    Write-Host "   [OK] Port 38005 is reachable!" -ForegroundColor Green
    Write-Host "   Response:" -ForegroundColor Gray
    $response | ConvertTo-Json -Depth 3
} catch {
    Write-Host "   [FAIL] Cannot reach port 38005" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Try a chat completion
Write-Host "`n2. Testing chat completion..." -ForegroundColor Yellow
$modelId = $null
try {
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:38005/v1/models" -TimeoutSec 15
    if ($models.data -and $models.data.Count -gt 0) {
        $modelId = $models.data[0].id
    }
} catch {
    # The connectivity test above already reports the failure.
}
if (-not $modelId) {
    $modelId = if ($env:GOODQ_WSL_MODEL_PATH) { $env:GOODQ_WSL_MODEL_PATH } else { "/home/jdben/models/Qwen2.5-0.5B-Instruct" }
}
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
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:38005/v1/chat/completions" `
        -Method Post `
        -Body $body `
        -ContentType "application/json" `
        -TimeoutSec 30
    
    Write-Host "   [OK] Chat completion works!" -ForegroundColor Green
    Write-Host "   Response: $($response.choices[0].message.content)" -ForegroundColor Gray
} catch {
    Write-Host "   [FAIL] Chat completion failed" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nDone!" -ForegroundColor Cyan
