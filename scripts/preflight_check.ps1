# GoodQ Pre-Flight Check & Auto-Launcher
# Ensures all required services are running before starting GoodQ
# Self-healing: Automatically launches missing services

Param(
    [switch]$SkipLLM,
    [switch]$ForceOpenAI,
    [string]$LLMProvider = "auto"  # auto, lmstudio, ollama, openai
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "_lib\\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe

# Mission colors for Q Branch styling
function Write-Mission($msg, $type = "info") {
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($type) {
        "success" { Write-Host "[$timestamp] [SUCCESS]" -ForegroundColor Green -NoNewline; Write-Host " $msg" }
        "error"   { Write-Host "[$timestamp] [FAILED]" -ForegroundColor Red -NoNewline; Write-Host " $msg" }
        "warning" { Write-Host "[$timestamp] [CAUTION]" -ForegroundColor Yellow -NoNewline; Write-Host " $msg" }
        "intel"   { Write-Host "[$timestamp] [INTEL]" -ForegroundColor Cyan -NoNewline; Write-Host " $msg" }
        "mission" { Write-Host "[$timestamp] [MISSION]" -ForegroundColor Magenta -NoNewline; Write-Host " $msg" }
        default   { Write-Host "[$timestamp] [STATUS]" -ForegroundColor Cyan -NoNewline; Write-Host " $msg" }
    }
}

function Write-Header($title) {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  $($title.PadRight(60))  ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

# Start mission
Write-Header "GoodQ Pre-Flight Check - Mission Control"
Write-Mission "Initiating pre-flight systems check..." "mission"

# Change to project directory
Set-Location "L:\goodq4all"

# ============================================================================
# LLM SERVICE DETECTION & AUTO-START
# ============================================================================

Write-Header "LLM Service Detection & Verification"

# LLM Configuration
$LLMConfig = @{
    LMStudio = @{
        Name = "LM Studio"
        ProcessName = "LM Studio"
        ExecutablePath = "C:\Program Files\LM Studio\LM Studio.exe"
        APIEndpoint = "http://localhost:1234/v1/models"
        APIPort = 1234
        Required = $true
        Priority = 1
    }
    Ollama = @{
        Name = "Ollama"
        ProcessName = "ollama"
        ExecutablePath = "$env:USERPROFILE\AppData\Local\Programs\Ollama\ollama.exe"
        ServiceName = "OllamaService"
        APIEndpoint = "http://localhost:31434/api/tags"
        APIPort = 31434
        Required = $false
        Priority = 2
    }
    OpenAI = @{
        Name = "OpenAI API"
        EnvVar = "OPENAI_API_KEY"
        Required = $false
        Priority = 3
    }
}

# Function to check if process is running
function Test-ProcessRunning($processName) {
    $process = Get-Process -Name $processName -ErrorAction SilentlyContinue
    return $null -ne $process
}

# Function to test API endpoint
function Test-APIEndpoint($url, $timeoutSec = 3) {
    try {
        $response = Invoke-WebRequest -Uri $url -TimeoutSec $timeoutSec -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

# Function to start LM Studio
function Start-LMStudio {
    param($config)
    
    Write-Mission "Deploying LM Studio..." "info"
    
    if (-not (Test-Path $config.ExecutablePath)) {
        Write-Mission "LM Studio executable not found at: $($config.ExecutablePath)" "error"
        return $false
    }
    
    try {
        # Start LM Studio
        Start-Process -FilePath $config.ExecutablePath -WindowStyle Normal
        Write-Mission "LM Studio process initiated" "info"
        
        # Wait for API to become available (up to 30 seconds)
        Write-Mission "Waiting for LM Studio API to initialize..." "info"
        $maxWait = 30
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 2
            $waited += 2
            
            if (Test-APIEndpoint $config.APIEndpoint -timeoutSec 2) {
                Write-Mission "LM Studio API online and operational" "success"
                return $true
            }
            
            Write-Host "." -NoNewline -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Mission "LM Studio started but API not responding yet. May need manual model load." "warning"
        return $true
        
    } catch {
        Write-Mission "Failed to start LM Studio: $_" "error"
        return $false
    }
}

# Function to start Ollama
function Start-Ollama {
    param($config)
    
    Write-Mission "Deploying Ollama service..." "info"
    
    # Check if Ollama service exists
    $service = Get-Service -Name "OllamaService" -ErrorAction SilentlyContinue
    
    if ($service) {
        # Start service if stopped
        if ($service.Status -ne 'Running') {
            Write-Mission "Starting Ollama service..." "info"
            Start-Service -Name "OllamaService"
            Start-Sleep -Seconds 3
        }
    } else {
        # Service doesn't exist, try starting executable
        if (Test-Path $config.ExecutablePath) {
            Write-Mission "Starting Ollama from executable..." "info"
            Start-Process -FilePath $config.ExecutablePath -ArgumentList "serve" -WindowStyle Hidden
            Start-Sleep -Seconds 5
        } else {
            Write-Mission "Ollama not found. Install from: https://ollama.ai" "warning"
            return $false
        }
    }
    
    # Test API
    if (Test-APIEndpoint $config.APIEndpoint) {
        Write-Mission "Ollama API online and operational" "success"
        return $true
    } else {
        Write-Mission "Ollama service started but API not responding" "warning"
        return $false
    }
}

# Auto-detect and start LLM services
$activeLLM = $null

# Check LM Studio
Write-Mission "Checking LM Studio status..." "info"
$lmConfig = $LLMConfig.LMStudio

if (Test-ProcessRunning $lmConfig.ProcessName) {
    Write-Mission "LM Studio process is running" "success"
    
    # Verify API
    if (Test-APIEndpoint $lmConfig.APIEndpoint) {
        Write-Mission "LM Studio API is responding" "success"
        $activeLLM = "LMStudio"
    } else {
        Write-Mission "LM Studio running but API not responding. May need to load a model." "warning"
        Write-Mission "Opening LM Studio - Please ensure a model is loaded" "intel"
    }
} else {
    Write-Mission "LM Studio not running" "warning"
    
    if (-not $SkipLLM -and ($LLMProvider -eq "auto" -or $LLMProvider -eq "lmstudio")) {
        Write-Mission "Attempting to start LM Studio..." "mission"
        if (Start-LMStudio $lmConfig) {
            $activeLLM = "LMStudio"
        }
    }
}

# Check Ollama (fallback or if preferred)
if (-not $activeLLM -or $LLMProvider -eq "ollama") {
    Write-Mission "Checking Ollama status..." "info"
    $ollamaConfig = $LLMConfig.Ollama
    
    $ollamaService = Get-Service -Name "OllamaService" -ErrorAction SilentlyContinue
    
    if ($ollamaService -and $ollamaService.Status -eq 'Running') {
        Write-Mission "Ollama service is running" "success"
        
        if (Test-APIEndpoint $ollamaConfig.APIEndpoint) {
            Write-Mission "Ollama API is responding" "success"
            if (-not $activeLLM) { $activeLLM = "Ollama" }
        }
    } else {
        Write-Mission "Ollama service not running" "warning"
        
        if (-not $SkipLLM -and -not $activeLLM) {
            Write-Mission "Attempting to start Ollama..." "mission"
            if (Start-Ollama $ollamaConfig) {
                $activeLLM = "Ollama"
            }
        }
    }
}

# Check OpenAI (last resort)
if (-not $activeLLM -or $ForceOpenAI) {
    Write-Mission "Checking OpenAI API configuration..." "info"
    
    # Load .env.local
    $envFile = Join-Path (Get-Location) ".env.local"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
    
    $openaiKey = [System.Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "Process")
    if ($openaiKey) {
        Write-Mission "OpenAI API key configured" "success"
        $activeLLM = "OpenAI"
    } else {
        Write-Mission "OpenAI API key not configured" "warning"
    }
}

# LLM Summary
Write-Host ""
if ($activeLLM) {
    Write-Mission "LLM Provider Active: $activeLLM" "success"
} else {
    Write-Mission "No LLM provider available" "error"
    Write-Host ""
    Write-Host "  [!] GoodQ requires an LLM provider for chat functionality." -ForegroundColor Yellow
    Write-Host "  [!] Options:" -ForegroundColor Yellow
    Write-Host "      1. LM Studio - Start manually and load a model" -ForegroundColor White
    Write-Host "      2. Ollama - Install from https://ollama.ai" -ForegroundColor White
    Write-Host "      3. OpenAI - Set OPENAI_API_KEY in .env.local" -ForegroundColor White
    Write-Host ""
    
    $response = Read-Host "Continue without LLM? (y/n)"
    if ($response -ne 'y') {
        Write-Mission "Mission aborted - LLM required" "error"
        exit 1
    }
}

# ============================================================================
# SYSTEM HEALTH CHECK
# ============================================================================

Write-Header "System Health Verification"

# Run unified health check
Write-Mission "Running comprehensive health check..." "info"
$healthCheckOutput = & $condaExe run -n goodq_zenml python scripts\unified_health_check.py --auto-heal 2>&1 | Out-String

# Parse health check status
$healthStatus = "UNKNOWN"
if ($healthCheckOutput -match "Overall Status:\s*(\w+)") {
    $healthStatus = $matches[1]
}

switch ($healthStatus) {
    "GREEN"  { Write-Mission "System health: GREEN - All systems operational" "success" }
    "YELLOW" { Write-Mission "System health: YELLOW - Minor warnings (non-critical)" "warning" }
    "RED"    { Write-Mission "System health: RED - Critical issues detected" "error" }
    default  { Write-Mission "System health: Could not determine status" "warning" }
}

if ($healthStatus -eq "RED") {
    Write-Host ""
    Write-Host "  [!] Critical system issues detected!" -ForegroundColor Red
    Write-Host "  [!] Review the health check output above." -ForegroundColor Red
    Write-Host ""
    
    $response = Read-Host "Continue despite critical issues? (y/n)"
    if ($response -ne 'y') {
        Write-Mission "Mission aborted - System health check failed" "error"
        exit 1
    }
}

# ============================================================================
# REQUIRED SERVICES CHECK
# ============================================================================

Write-Header "Required Services Verification"

# Check Conda
Write-Mission "Verifying Conda installation..." "info"
$condaCheck = Get-Command conda -ErrorAction SilentlyContinue
if ($condaCheck) {
    Write-Mission "Conda available: $($condaCheck.Source)" "success"
} else {
    Write-Mission "Conda not found in PATH" "error"
    exit 1
}

# Check Python (zenml environment)
Write-Mission "Verifying Python environment (goodq_zenml)..." "info"
$pythonTest = & $condaExe run -n goodq_zenml python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Mission "Python environment active: $pythonTest" "success"
} else {
    Write-Mission "Python environment check failed" "error"
    exit 1
}

# Check GPU availability
Write-Mission "Checking GPU status..." "info"
$gpuCheck = nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Mission "GPU detected: $gpuCheck" "success"
} else {
    Write-Mission "GPU check failed - CUDA operations may not work" "warning"
}

# Check critical paths
Write-Mission "Verifying critical paths..." "info"
$criticalPaths = @{
    "Project Root" = "L:\goodq4all"
    "Models Cache" = "L:\models"
    "Dataset Cache" = "L:\models\hf\datasets"
    "Data Directory" = "L:\goodq4all\data"
    "Logs Directory" = "L:\goodq4all\logs"
}

$pathsOk = $true
foreach ($name in $criticalPaths.Keys) {
    $path = $criticalPaths[$name]
    if (Test-Path $path) {
        Write-Mission "$name verified: $path" "success"
    } else {
        Write-Mission "$name MISSING: $path" "error"
        $pathsOk = $false
    }
}

if (-not $pathsOk) {
    Write-Mission "Critical paths missing - cannot proceed" "error"
    exit 1
}

# ============================================================================
# LAUNCH SUMMARY
# ============================================================================

Write-Header "Pre-Flight Check Complete - Launch Summary"

Write-Host "  System Status:" -ForegroundColor Cyan
Write-Host "    ✓ Health Check:  $healthStatus" -ForegroundColor $(if($healthStatus -eq "GREEN"){"Green"}elseif($healthStatus -eq "YELLOW"){"Yellow"}else{"Red"})
Write-Host "    ✓ LLM Provider:  $(if($activeLLM){$activeLLM + ' [ACTIVE]'}else{'None [OPTIONAL]'})" -ForegroundColor $(if($activeLLM){"Green"}else{"Yellow"})
Write-Host "    ✓ GPU:           $(if($LASTEXITCODE -eq 0){'Available'}else{'Not Available'})" -ForegroundColor $(if($LASTEXITCODE -eq 0){"Green"}else{"Yellow"})
Write-Host "    ✓ Conda:         Active" -ForegroundColor Green
Write-Host "    ✓ Paths:         Verified" -ForegroundColor Green
Write-Host ""

Write-Host "  LLM Configuration:" -ForegroundColor Cyan
Write-Host "    • Active Provider: $(if($activeLLM){$activeLLM}else{'None'})" -ForegroundColor White
if ($activeLLM -eq "LMStudio") {
    Write-Host "    • Endpoint:        http://localhost:1234/v1/chat/completions" -ForegroundColor White
    Write-Host "    • Status:          $(if(Test-APIEndpoint $LLMConfig.LMStudio.APIEndpoint){'Online'}else{'Starting...'})" -ForegroundColor $(if(Test-APIEndpoint $LLMConfig.LMStudio.APIEndpoint){"Green"}else{"Yellow"})
} elseif ($activeLLM -eq "Ollama") {
    Write-Host "    • Endpoint:        http://localhost:31434/api" -ForegroundColor White
    Write-Host "    • Status:          $(if(Test-APIEndpoint $LLMConfig.Ollama.APIEndpoint){'Online'}else{'Starting...'})" -ForegroundColor $(if(Test-APIEndpoint $LLMConfig.Ollama.APIEndpoint){"Green"}else{"Yellow"})
} elseif ($activeLLM -eq "OpenAI") {
    Write-Host "    • Provider:        OpenAI Cloud API" -ForegroundColor White
    Write-Host "    • Status:          API Key Configured" -ForegroundColor Green
}
Write-Host ""

Write-Host "  Important Reminders:" -ForegroundColor Cyan
if ($activeLLM -eq "LMStudio") {
    Write-Host "    [!] Ensure LM Studio has a model loaded and server started" -ForegroundColor Yellow
    Write-Host "    [!] Recommended: Mistral 7B or similar 7B+ parameter model" -ForegroundColor Yellow
} elseif ($activeLLM -eq "Ollama") {
    Write-Host "    [!] Ensure Ollama has models pulled: ollama pull mistral" -ForegroundColor Yellow
}

if ($healthStatus -ne "GREEN") {
    Write-Host "    [!] System health is $healthStatus - review warnings above" -ForegroundColor Yellow
}

Write-Host ""
Write-Mission "Pre-flight check complete - All systems ready for launch" "success"
Write-Host ""

# Return status
return @{
    HealthStatus = $healthStatus
    LLMProvider = $activeLLM
    AllSystemsGo = ($healthStatus -ne "RED")
}
