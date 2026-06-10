# GoodQ4All - Offline Dependency Stager Script
# ---------------------------------------------
# Enables strict separation of online asset acquisition from offline packaging.
# Modes: Acquire, Verify, Audit, PrintSummary.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Acquire", "Verify", "Audit", "PrintSummary")]
    [string]$Mode,

    [string]$CacheDir = "staged_cache",
    [string]$ManifestPath = "..\..\configs\offline_dependencies_manifest.json"
)

$ErrorActionPreference = "Stop"

# Helper: compute SHA256 of file
function Get-FileSHA256 {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLower()
}

# Resolve paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
cd $ScriptDir

$ResolvedManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
if (-not (Test-Path $ResolvedManifestPath)) {
    Write-Error "Manifest not found at $ResolvedManifestPath"
}

# Read manifest
$Manifest = Get-Content -Raw -Path $ResolvedManifestPath | ConvertFrom-Json

# Helper: ensure folder structure
function Ensure-Directory {
    param([string]$Path)
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " GoodQ4All Dependency Stager: Mode = $Mode" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

$AcquireCount = 0
$VerifyCount = 0
$AuditFailed = $false
$VerificationFailed = $false

# Process Toolchains and Dependencies
$Artifacts = @()
foreach ($prop in $Manifest.toolchains.psobject.properties) {
    $Artifacts += $Manifest.toolchains.$($prop.Name)
}
foreach ($prop in $Manifest.dependencies.psobject.properties) {
    $Artifacts += $Manifest.dependencies.$($prop.Name)
}

if ($Mode -eq "Acquire") {
    # Phase 1: Download external binaries and runtimes
    foreach ($art in $Artifacts) {
        $destPath = Join-Path $CacheDir $art.cache_path.Replace("staged_cache/", "")
        Ensure-Directory $destPath
        
        Write-Host "Checking artifact: $($art.artifact_id)..." -ForegroundColor Cyan
        
        $needDownload = $true
        if (Test-Path $destPath) {
            $currentHash = Get-FileSHA256 $destPath
            if ($currentHash -eq $art.sha256.ToLower()) {
                Write-Host "  Cached file matches expected SHA256: $($art.sha256)" -ForegroundColor Green
                $needDownload = $false
            } else {
                Write-Host "  Cached file hash mismatch (Got: $currentHash). Re-downloading..." -ForegroundColor Yellow
                Remove-Item $destPath -Force
            }
        }
        
        if ($needDownload) {
            if ($art.source_url -like "local://*") {
                # Resolve local Conda environment path
                $condaBase = "C:\Users\jdben\miniconda3\envs\goodq_audio_embed\Lib\site-packages"
                $localRel = $art.source_url.Substring(8).Replace("/", "\")
                $localSrcPath = Join-Path $condaBase $localRel
                Write-Host "  Copying from local source: $localSrcPath..." -ForegroundColor Yellow
                if (-not (Test-Path $localSrcPath)) {
                    Write-Error "  Local source file not found: $localSrcPath"
                }
                Copy-Item -Path $localSrcPath -Destination $destPath -Force
            } else {
                Write-Host "  Downloading from $($art.source_url)..." -ForegroundColor Yellow
                $wc = New-Object System.Net.WebClient
                $wc.Headers.Add("User-Agent", "Wget")
                try {
                    $wc.DownloadFile($art.source_url, $destPath)
                } catch {
                    Write-Host "    Download failed with default UA. Retrying with browser UA..." -ForegroundColor Yellow
                    $wc2 = New-Object System.Net.WebClient
                    $wc2.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                    $wc2.DownloadFile($art.source_url, $destPath)
                }
            }
            
            $downloadedHash = Get-FileSHA256 $destPath
            if ($downloadedHash -ne $art.sha256.ToLower()) {
                Remove-Item $destPath -Force
                Write-Error "  SHA256 mismatch for newly staged artifact: $($art.artifact_id) (Got: $downloadedHash, Expected: $($art.sha256))"
            }
            Write-Host "  [OK] Successfully staged and verified." -ForegroundColor Green
        }
        $AcquireCount++
    }

    # Phase 2: Stage python wheels offline
    $wheelsDir = Join-Path $CacheDir "wheels"
    if (-not (Test-Path $wheelsDir)) {
        New-Item -ItemType Directory -Path $wheelsDir -Force | Out-Null
    }
    Write-Host "Staging python wheels offline via pip download..." -ForegroundColor Cyan
    $reqFile = [System.IO.Path]::GetFullPath("..\..\requirements-baseline-lock.txt")
    
    # Run pip download securely with retries
    $retryCount = 0
    $success = $false
    while (-not $success -and $retryCount -lt 5) {
        Write-Host "  Running pip download (Attempt $($retryCount + 1) of 5)..." -ForegroundColor Yellow
        pip download --timeout 120 --dest $wheelsDir --python-version 3.10 --only-binary=:all: --platform win_amd64 --implementation cp --abi cp310 --extra-index-url https://download.pytorch.org/whl/cu121 -r $reqFile
        if ($LASTEXITCODE -eq 0) {
            $success = $true
        } else {
            $retryCount++
            if ($retryCount -lt 5) {
                Write-Host "  Pip download failed with code $LASTEXITCODE. Retrying in 5 seconds..." -ForegroundColor Yellow
                Start-Sleep -Seconds 5
            }
        }
    }
    if (-not $success) {
        Write-Error "Pip wheels download failed after 5 attempts."
    }
    Write-Host "Pip wheels staged successfully." -ForegroundColor Green

} elseif ($Mode -eq "Verify") {
    # Strictly offline hash verification
    foreach ($art in $Artifacts) {
        $destPath = Join-Path $CacheDir $art.cache_path.Replace("staged_cache/", "")
        Write-Host "Verifying artifact: $($art.artifact_id)..." -ForegroundColor Cyan
        if (-not (Test-Path $destPath)) {
            Write-Host "  [ERROR] Staged file missing: $destPath" -ForegroundColor Red
            $VerificationFailed = $true
            continue
        }
        
        $currentHash = Get-FileSHA256 $destPath
        if ($currentHash -eq $art.sha256.ToLower()) {
            Write-Host "  [OK] Hash matches: $currentHash" -ForegroundColor Green
            $VerifyCount++
        } else {
            Write-Host "  [ERROR] Hash mismatch! (Got: $currentHash, Expected: $($art.sha256))" -ForegroundColor Red
            $VerificationFailed = $true
        }
    }
    
    # Verify wheels exist
    $wheelsDir = Join-Path $CacheDir "wheels"
    if (-not (Test-Path $wheelsDir) -or @(Get-ChildItem $wheelsDir -Filter *.whl).Count -eq 0) {
        Write-Host "  [ERROR] Windows Wheelhouse is empty or missing at $wheelsDir" -ForegroundColor Red
        $VerificationFailed = $true
    } else {
        $count = @(Get-ChildItem $wheelsDir -Filter *.whl).Count
        Write-Host "  [OK] Wheelhouse contains $count offline wheel files." -ForegroundColor Green
    }
    
    if ($VerificationFailed) {
        Write-Error "Staged dependency verification failed. Build cannot proceed."
    }

} elseif ($Mode -eq "Audit") {
    # Strictly offline licensing and compliance check
    $requiredKeys = @(
        "artifact_id", "pack_id", "required", "kind", "source_url", "source_version", 
        "source_commit", "cache_path", "target_path", "sha256", "size_bytes", 
        "license", "redistribution_status", "install_action", "verify_action", 
        "rollback_action", "notes"
    )

    foreach ($art in $Artifacts) {
        Write-Host "Auditing Semantic Integrity: $($art.artifact_id)..." -ForegroundColor Cyan
        
        # 1. Check all required properties exist
        foreach ($key in $requiredKeys) {
            $member = $art.psobject.Properties[$key]
            if ($null -eq $member) {
                Write-Host "  [ERROR] Missing required property '$key' in artifact '$($art.artifact_id)'" -ForegroundColor Red
                $AuditFailed = $true
            }
        }
        
        if ($AuditFailed) { continue }

        # 2. Check semantic properties are populated/valid
        if ([string]::IsNullOrWhiteSpace($art.artifact_id)) {
            Write-Host "  [ERROR] artifact_id is empty or whitespace" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ([string]::IsNullOrWhiteSpace($art.notes) -or $art.notes.Length -lt 10) {
            Write-Host "  [ERROR] notes are missing or too thin (must explain what/why, min 10 chars)" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ([string]::IsNullOrWhiteSpace($art.source_url) -or ($art.source_url -notlike "http*" -and $art.source_url -notlike "ftp*" -and $art.source_url -notlike "local://*")) {
            Write-Host "  [ERROR] source_url '$($art.source_url)' is not a valid URL" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ($null -eq $art.required -or $art.required.GetType().Name -ne "Boolean") {
            Write-Host "  [ERROR] required status must be a boolean" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ([string]::IsNullOrWhiteSpace($art.target_path)) {
            Write-Host "  [ERROR] target_path is empty" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ([string]::IsNullOrWhiteSpace($art.verify_action)) {
            Write-Host "  [ERROR] verify_action is empty" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ([string]::IsNullOrWhiteSpace($art.rollback_action)) {
            Write-Host "  [ERROR] rollback_action is empty" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ($art.sha256 -notmatch "^[a-fA-F0-9]{64}$") {
            Write-Host "  [ERROR] sha256 '$($art.sha256)' is not a valid 64-character SHA256 hex string" -ForegroundColor Red
            $AuditFailed = $true
        }
        if ($null -eq $art.size_bytes -or $art.size_bytes -le 0) {
            Write-Host "  [ERROR] size_bytes '$($art.size_bytes)' must be a positive integer" -ForegroundColor Red
            $AuditFailed = $true
        }
        
        Write-Host "  License: $($art.license)" -ForegroundColor Yellow
        Write-Host "  Redistribution Status: $($art.redistribution_status)" -ForegroundColor Yellow
        
        if ($art.redistribution_status -ne "allowed") {
            Write-Host "  [ERROR] Non-permissive redistribution status: $($art.redistribution_status)" -ForegroundColor Red
            $AuditFailed = $true
        }
    }
    
    if ($AuditFailed) {
        Write-Error "Compliance audit failed due to missing metadata or non-redistributable dependencies."
    } else {
        Write-Host "[OK] Compliance audit succeeded. All staged licenses and metadata fields are verified." -ForegroundColor Green
    }

} elseif ($Mode -eq "PrintSummary") {
    Write-Host "  Payload Staging Summary:" -ForegroundColor Yellow
    foreach ($art in $Artifacts) {
        $destPath = Join-Path $CacheDir $art.cache_path.Replace("staged_cache/", "")
        $status = "Missing"
        if (Test-Path $destPath) {
            $status = "Staged"
        }
        Write-Host "  - $($art.artifact_id) ($($art.kind)): $status (Required: $($art.required))" -ForegroundColor Yellow
    }
}
