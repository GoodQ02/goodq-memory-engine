# restart_llm_services.ps1
# ==============================================================================
# GoodQ4All LLM Services Recycler & Warmup Script
# Gracefully recycles vLLM and Ollama to clear VRAM and restore clean posture.
#
# Supports -GamingMode: Stops vLLM (off) and starts Ollama on CPU only (VRAM free).
# ==============================================================================

param(
    [switch]$GamingMode = $false
)

$ErrorActionPreference = "Stop"

# Load repository paths and configurations
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$WslDistro = $env:GOODQ_WSL_DISTRO
if ([string]::IsNullOrEmpty($WslDistro)) {
    $WslDistro = "Ubuntu-22.04"
}

Write-Output "========================================"
Write-Output "Recycling LLM Services (WSL vLLM & Host Ollama)"
Write-Output "========================================"
Write-Output ""

# --- STEP 1: STOP SERVICES ---
Write-Output "[1/4] Stopping active services to reclaim VRAM..."

# Stop WSL vLLM
Write-Output "Stopping WSL vLLM systemd service..."
wsl -d $WslDistro -u root -- systemctl stop vllm-llama1b 2>&1 | Out-Null
wsl -d $WslDistro -u root -- pkill -KILL -f "[v]llm.entrypoints.openai.api_server" 2>&1 | Out-Null
wsl -d $WslDistro -u root -- pkill -KILL -f "[V]LLM::EngineCore" 2>&1 | Out-Null
wsl -d $WslDistro -- pkill -KILL -f "[g]oodq-vllm-keepalive" 2>&1 | Out-Null

# Stop WSL Ollama (if running there)
wsl -d $WslDistro -u root -- bash -lc "systemctl list-unit-files ollama.service >/dev/null 2>&1 && systemctl stop ollama || true" 2>&1 | Out-Null

# Stop Windows Host Ollama
$OllamaProc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($OllamaProc) {
    Write-Output "Stopping Windows host Ollama process..."
    Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
    # Give Windows a moment to clean up process handles
    Start-Sleep -Seconds 2
}

# --- STEP 2: VERIFY VRAM & PORT RELEASE ---
Write-Output "[2/4] Verifying port and VRAM release..."

$Ports = @(38005, 11434, 31434)
foreach ($Port in $Ports) {
    $Conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($Conn) {
        Write-Warning "Port $Port is still in use by PID $($Conn.OwningProcess). Attempting forced cleanup..."
        Stop-Process -Id $Conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

# Query current GPU VRAM using nvidia-smi
try {
    $VramInfo = wsl -d $WslDistro -- nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>&1
    if ($LastExitCode -eq 0) {
        $UsedVram = [float]($VramInfo.Trim()) / 1024.0
        Write-Output "GPU VRAM currently in use: $($UsedVram.ToString('F2')) GB"
    }
} catch {
    Write-Output "Could not query GPU VRAM status."
}

# --- STEP 3: RESTART SERVICES ---
Write-Output ""
Write-Output "[3/4] Re-starting LLM Services..."

if ($GamingMode) {
    Write-Output "Gaming Mode Active: Keeping WSL vLLM service offline to preserve GPU VRAM."
    
    # Start host Ollama on CPU only
    $StartOllamaScript = Join-Path $ScriptDir "start_ollama_fallback.ps1"
    if (Test-Path $StartOllamaScript) {
        Write-Output "Starting Windows host Ollama in CPU-only mode..."
        powershell -NoProfile -ExecutionPolicy Bypass -File $StartOllamaScript -CpuOnly
    }
} else {
    # Check if GoodQ4All Task Scheduler tasks exist
    $Tasks = schtasks /query /fo CSV 2>&1
    $vLlmTaskExists = $Tasks -match "GoodQ4All vLLM WSL Startup"
    $OllamaTaskExists = $Tasks -match "GoodQ4All Ollama Fallback Startup"

    if ($vLlmTaskExists) {
        Write-Output "Starting WSL vLLM via Windows Task Scheduler..."
        schtasks /run /tn "GoodQ4All vLLM WSL Startup" | Out-Null
    } else {
        Write-Output "Starting WSL vLLM service directly..."
        wsl -d $WslDistro -u root -- systemctl start vllm-llama1b
        wsl -d $WslDistro -- bash -lc "pgrep -f '[g]oodq-vllm-keepalive' >/dev/null || (nohup bash -c 'exec -a goodq-vllm-keepalive sleep infinity' >/dev/null 2>&1 &)"
    }

    if ($OllamaTaskExists) {
        Write-Output "Starting Windows host Ollama via Windows Task Scheduler..."
        schtasks /run /tn "GoodQ4All Ollama Fallback Startup" | Out-Null
    } else {
        $StartOllamaScript = Join-Path $ScriptDir "start_ollama_fallback.ps1"
        if (Test-Path $StartOllamaScript) {
            Write-Output "Starting Windows host Ollama fallback directly..."
            powershell -NoProfile -ExecutionPolicy Bypass -File $StartOllamaScript
        }
    }
}

# --- STEP 4: HEALTH CHECK & WARMUP ---
Write-Output ""
Write-Output "[4/4] Verifying service endpoints and warming up..."

# Helper function to check endpoint readiness
function Test-Endpoint {
    param([string]$Url, [int]$TimeoutSeconds = 45)
    $Start = [DateTime]::UtcNow
    while (([DateTime]::UtcNow - $Start).TotalSeconds -lt $TimeoutSeconds) {
        try {
            $Resp = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($Resp) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

if (-not $GamingMode) {
    $vLlmReady = Test-Endpoint -Url "http://127.0.0.1:38005/v1/models" -TimeoutSeconds 55
    if ($vLlmReady) {
        Write-Output "[OK] Primary vLLM is active at http://127.0.0.1:38005/v1"
    } else {
        Write-Warning "[WARN] Primary vLLM failed to respond on port 38005 within timeout."
    }
} else {
    Write-Output "[INFO] WSL vLLM is offline (VRAM preserved)."
}

$OllamaPort = 11434
$OllamaReady = Test-Endpoint -Url "http://127.0.0.1:11434/v1/models" -TimeoutSeconds 15
if (-not $OllamaReady) {
    $OllamaReady = Test-Endpoint -Url "http://127.0.0.1:31434/v1/models" -TimeoutSeconds 5
    if ($OllamaReady) { $OllamaPort = 31434 }
}
if ($OllamaReady) {
    if ($GamingMode) {
        Write-Output "[OK] Fallback Ollama is active on CPU at http://127.0.0.1:$OllamaPort/v1"
    } else {
        Write-Output "[OK] Fallback Ollama is active at http://127.0.0.1:$OllamaPort/v1"
    }
} else {
    Write-Warning "[WARN] Fallback Ollama failed to respond on port 11434 or 31434 within timeout."
}

Write-Output ""
Write-Output "========================================"
Write-Output "Recycle and verification completed."
Write-Output "========================================"
