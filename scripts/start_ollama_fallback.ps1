# Compatibility check for the existing PAIR Ollama facade; never launch another server.
[CmdletBinding()]
param([string]$OllamaExe, [string]$ListenHost, [string]$Models, [switch]$CpuOnly)
$ErrorActionPreference = 'Stop'
if ($OllamaExe -or $Models -or $CpuOnly -or $env:GOODQ_OLLAMA_CPU_ONLY -eq '1' -or
    ($ListenHost -and $ListenHost -ne '127.0.0.1:11434')) {
    throw 'Standalone Ollama overrides are retired. Configure engine ownership and device placement in NVIDIA PAIR.'
}
$response = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5 -ErrorAction Stop
if (-not $response.version) { throw 'PAIR Ollama is unavailable. Open the existing NVIDIA PAIR app.' }
Write-Output 'PAIR Ollama is ready on http://127.0.0.1:11434/v1; model stores and engine lifetime are managed by PAIR.'
