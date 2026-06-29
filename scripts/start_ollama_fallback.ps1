param(
    [string]$OllamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    [string]$ListenHost = $env:OLLAMA_HOST,
    [string]$Models = $env:OLLAMA_MODELS,
    [switch]$CpuOnly = $false
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ListenHost)) {
    $ListenHost = "127.0.0.1:11434"
}

if ([string]::IsNullOrWhiteSpace($Models) -and -not [string]::IsNullOrWhiteSpace($env:GOODQ_DATA_ROOT)) {
    $Models = Join-Path $env:GOODQ_DATA_ROOT "models\ollama"
}

if ([string]::IsNullOrWhiteSpace($OllamaExe) -or -not (Test-Path -LiteralPath $OllamaExe)) {
    throw "Ollama executable not found at '$OllamaExe'. Install Ollama for Windows first."
}

if (-not [string]::IsNullOrWhiteSpace($Models)) {
    New-Item -ItemType Directory -Force -Path $Models | Out-Null
    $env:OLLAMA_MODELS = $Models
}

$env:OLLAMA_HOST = $ListenHost

if ($CpuOnly -or $env:GOODQ_OLLAMA_CPU_ONLY -eq "1") {
    $env:CUDA_VISIBLE_DEVICES = ""
    Write-Output "Hiding GPU devices. Forcing Ollama to run on CPU."
}

# Memory and performance optimizations for single-user fallback use cases
$env:OLLAMA_FLASH_ATTENTION = "1"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:OLLAMA_KV_CACHE_TYPE = "q8_0"

$alreadyListening = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @("127.0.0.1", "::1") -and $_.LocalPort -eq ([Uri]"http://$ListenHost").Port } |
    Select-Object -First 1

if ($alreadyListening) {
    Write-Output "Ollama already listening on $ListenHost"
    exit 0
}

Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden
Write-Output "Started Ollama fallback on $ListenHost"
