Param(
  [string]$ModelsDir = 'L:\models'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[assets] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[assets] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[assets] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Error $m; exit 1 }

New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
$lexDir = Join-Path $ModelsDir 'lexicons\NRC-Emotion-Lexicon'
if (-not (Test-Path $lexDir)) {
  Info "Fetching NRC Emotion Lexicon"
  New-Item -ItemType Directory -Force -Path $lexDir | Out-Null
  try {
    $zip = Join-Path $lexDir 'NRC-Emotion-Lexicon.zip'
    Invoke-WebRequest -Uri 'https://saifmohammad.com/WebDocs/NRC-Emotion-Lexicon.zip' -OutFile $zip -UseBasicParsing
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $lexDir)
    Remove-Item $zip -Force
    Ok "NRC lexicon installed at $lexDir"
  } catch {
    Warn "Failed to fetch NRC lexicon: $_"
  }
} else {
  Info "Lexicon present at $lexDir"
}

Ok 'Assets bootstrap complete.'

