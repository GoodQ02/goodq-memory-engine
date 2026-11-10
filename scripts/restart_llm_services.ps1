# Recycle only the configured GoodQ vLLM owner. PAIR owns the shared Ollama engine.
[CmdletBinding()]
param([switch]$GamingMode)
$ErrorActionPreference = 'Stop'
if ($GamingMode) {
    throw 'GamingMode cannot force a shared PAIR engine onto CPU. Use the GoodQ vLLM Off and PAIR local-model unload controls, then select device placement in PAIR.'
}
# Fail before changing vLLM when the shared dependency is unavailable.
& (Join-Path $PSScriptRoot 'start_ollama_fallback.ps1')
& (Join-Path $PSScriptRoot 'stop_vllm_servers.ps1')
& (Join-Path $PSScriptRoot 'start_vllm_servers.ps1')
Write-Output 'GoodQ vLLM recycled and verified; PAIR Ollama remained under its existing owner.'
