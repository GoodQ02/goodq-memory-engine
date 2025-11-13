################################################################################
# GoodQ4All - Windows Setup for WSL2 Audio Offload
#
# This script prepares the Windows side for WSL2 audio integration
################################################################################

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  GoodQ4All - Windows WSL2 Audio Setup" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = "L:\goodq4all"
$WSL2Dir = "$ProjectRoot\wsl2_audio"

# Create directories
Write-Host "[1/5] Creating Windows directories..." -ForegroundColor Yellow
$Dirs = @(
    "$WSL2Dir\queue",
    "$WSL2Dir\output",
    "$WSL2Dir\logs"
)

foreach ($Dir in $Dirs) {
    if (!(Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        Write-Host "  Created: $Dir" -ForegroundColor Green
    }
}

# Create bridge config
Write-Host "[2/5] Creating bridge configuration..." -ForegroundColor Yellow
$BridgeConfig = @{
    windows_queue_dir = "$WSL2Dir\queue"
    windows_output_dir = "$WSL2Dir\output"
    wsl_home_dir = "/home/`$USER/goodq_audio"
    timeout_seconds = 3600
    poll_interval = 1.0
} | ConvertTo-Json

$BridgeConfig | Out-File -FilePath "$WSL2Dir\bridge_config.json" -Encoding utf8
Write-Host "  Created: bridge_config.json" -ForegroundColor Green

# Check WSL2
Write-Host "[3/5] Checking WSL2 installation..." -ForegroundColor Yellow
try {
    $WSLVersion = wsl --version 2>&1
    Write-Host "  WSL2 detected" -ForegroundColor Green
    
    # Check if Ubuntu is installed
    $Distributions = wsl --list --quiet
    if ($Distributions -match "Ubuntu") {
        Write-Host "  Ubuntu distribution found" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Ubuntu distribution not found" -ForegroundColor Yellow
        Write-Host "  Install with: wsl --install -d Ubuntu" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ERROR: WSL2 not installed or not in PATH" -ForegroundColor Red
    Write-Host "  Install with: wsl --install" -ForegroundColor Yellow
    exit 1
}

# Check CUDA passthrough
Write-Host "[4/5] Checking CUDA passthrough..." -ForegroundColor Yellow
try {
    $GPUCheck = wsl nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  CUDA passthrough working!" -ForegroundColor Green
        
        # Extract GPU info
        $GPUName = wsl nvidia-smi --query-gpu=name --format=csv,noheader | Select-Object -First 1
        Write-Host "  GPU: $GPUName" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: CUDA passthrough not working" -ForegroundColor Yellow
        Write-Host "  Ensure you have:" -ForegroundColor Yellow
        Write-Host "    1. Latest NVIDIA drivers for WSL2" -ForegroundColor Yellow
        Write-Host "    2. Windows 11 or Windows 10 21H2+" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  WARNING: Could not check CUDA passthrough" -ForegroundColor Yellow
}

# Copy setup script to WSL2
Write-Host "[5/5] Copying setup script to WSL2..." -ForegroundColor Yellow
try {
    # Make setup script executable and copy
    wsl bash -c "mkdir -p ~/goodq_audio"
    wsl bash -c "cp /mnt/l/goodq4all/wsl2_audio/setup_wsl2_audio.sh ~/goodq_audio/"
    wsl bash -c "cp /mnt/l/goodq4all/wsl2_audio/audio_service.py ~/goodq_audio/"
    wsl bash -c "chmod +x ~/goodq_audio/setup_wsl2_audio.sh"
    
    Write-Host "  Scripts copied to WSL2" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Failed to copy scripts to WSL2" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Windows Setup Complete!" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open WSL2 Ubuntu terminal" -ForegroundColor White
Write-Host "  2. Run: cd ~/goodq_audio && ./setup_wsl2_audio.sh" -ForegroundColor White
Write-Host "  3. Edit ~/goodq_audio/config.json with your HuggingFace token" -ForegroundColor White
Write-Host "  4. Start service: source venv/bin/activate && python3 audio_service.py" -ForegroundColor White
Write-Host ""
Write-Host "To test the bridge:" -ForegroundColor Yellow
Write-Host "  python $WSL2Dir\test_bridge.py" -ForegroundColor White
Write-Host ""
