##############################################################################
# GoodQ4All - Install GPU Support in All Environments
# 
# Installs PyTorch with CUDA 12.1 support in GPU-capable conda environments
##############################################################################

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# GPU-capable environments and their required packages
$envConfig = @{
    "goodq_audio_diarize" = @("torch", "torchvision", "torchaudio")
    "goodq_audio_transcribe" = @("torch")
    "goodq_audio_emotion" = @("torch", "torchvision")
    "goodq_emotion_classify" = @("torch", "torchvision")
    "goodq_face_embed" = @("torch", "torchvision")
    "goodq_text_embed" = @("torch", "torchvision")
    "goodq_image_caption" = @("torch", "torchvision")
    "goodq_ocr" = @("torch", "torchvision")
    "goodq_llm_chat" = @("torch")
    "goodq_object_track_yolo" = @("torch", "torchvision")
}

# PyTorch CUDA 12.1 installation command
$torchInstallCmd = "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "  GoodQ4All - GPU Support Installation" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "This will install PyTorch with CUDA 12.1 support in:" -ForegroundColor Yellow
$envConfig.Keys | ForEach-Object { Write-Host "  - $_" }
Write-Host ""
Write-Host "This may take 15-30 minutes depending on internet speed..." -ForegroundColor Yellow
Write-Host ""

if (-not $Force) {
    $response = Read-Host "Press ENTER to continue or CTRL+C to cancel"
}

$successful = @()
$failed = @()

foreach ($envName in $envConfig.Keys) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "Installing GPU support in: $envName" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host ""
    
    try {
        # Activate environment and install PyTorch with CUDA
        Write-Host "  Running: $torchInstallCmd" -ForegroundColor Gray
        
        $condaPath = "C:\Users\jdben\miniconda3\Scripts\conda.exe"
        $activatePath = "C:\Users\jdben\miniconda3\Scripts\activate.bat"
        
        # Use cmd to properly activate conda environment
        $cmd = "call `"$activatePath`" $envName && $torchInstallCmd"
        $output = cmd /c $cmd 2>&1 | Out-String
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $envName configured successfully" -ForegroundColor Green
            $successful += $envName
        } else {
            Write-Host "  ✗ $envName configuration failed" -ForegroundColor Red
            Write-Host $output -ForegroundColor DarkRed
            $failed += $envName
        }
    }
    catch {
        Write-Host "  ✗ $envName configuration failed: $_" -ForegroundColor Red
        $failed += $envName
    }
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Installation Summary" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Successful: $($successful.Count)/$($envConfig.Count)" -ForegroundColor Green
if ($successful.Count -gt 0) {
    $successful | ForEach-Object { Write-Host "  ✓ $_" -ForegroundColor Green }
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed: $($failed.Count)" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  ✗ $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "To retry failed environments, run:" -ForegroundColor Yellow
    Write-Host "  conda activate <env_name>" -ForegroundColor Yellow
    Write-Host "  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
