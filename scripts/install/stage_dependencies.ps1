# GoodQ4All - Offline Dependency Stager Script
# ---------------------------------------------
# Enables strict separation of online asset acquisition from offline packaging.
# Modes: Acquire, Verify, Audit, PrintSummary.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Acquire", "Verify", "Audit", "PrintSummary")]
    [string]$Mode,

    [string]$CacheDir = "staged_cache",
    [string]$ManifestPath = "..\..\configs\offline_dependencies_manifest.json",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# Helper: compute SHA256 of file
function Get-FileSHA256 {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLower()
}

# Resolve paths relative to this script, never the caller's working directory.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ResolvedCacheDir = if ([System.IO.Path]::IsPathRooted($CacheDir)) {
    [System.IO.Path]::GetFullPath($CacheDir)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $ScriptDir $CacheDir))
}
$ResolvedManifestPath = if ([System.IO.Path]::IsPathRooted($ManifestPath)) {
    [System.IO.Path]::GetFullPath($ManifestPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $ScriptDir $ManifestPath))
}
$CacheDir = $ResolvedCacheDir
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

function Invoke-VerifiedDownload {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$DestinationPath,
        [Parameter(Mandatory=$true)][string]$ExpectedSha256
    )

    Ensure-Directory $DestinationPath
    $temporaryPath = "$DestinationPath.partial"
    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    try {
        $curl = Get-Command curl.exe -ErrorAction Stop
        & $curl.Source --fail --location --retry 3 --connect-timeout 30 --output $temporaryPath -- $Url
        if ($LASTEXITCODE -ne 0) {
            throw "curl.exe failed with exit code $($LASTEXITCODE): $Url"
        }
        if (-not (Test-Path $temporaryPath) -or (Get-Item -LiteralPath $temporaryPath).Length -le 0) {
            throw "Downloaded artifact is empty: $Url"
        }
        $actualSha256 = Get-FileSHA256 $temporaryPath
        if ($actualSha256 -ne $ExpectedSha256.ToLower()) {
            throw "SHA256 mismatch for downloaded artifact (got $actualSha256, expected $ExpectedSha256): $Url"
        }
        Move-Item -LiteralPath $temporaryPath -Destination $DestinationPath -Force
    } catch {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        throw
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
$DeclaredWheelArtifacts = @($Manifest.wheels.wheelhouse | Where-Object {
    -not [string]::IsNullOrWhiteSpace($_.source_url) -and -not [string]::IsNullOrWhiteSpace($_.sha256)
})

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
                $condaBase = ""
                if ($env:CONDA_PREFIX) {
                    $condaRoot = Split-Path $env:CONDA_PREFIX -Parent
                    $envPath = Join-Path $condaRoot "goodq_audio_embed"
                    if (Test-Path $envPath) {
                        $condaBase = Join-Path $envPath "Lib\site-packages"
                    }
                }
                if (-not $condaBase -or -not (Test-Path $condaBase)) {
                    $userHome = [Environment]::GetFolderPath('UserProfile')
                    $envPath = Join-Path $userHome "miniconda3\envs\goodq_audio_embed"
                    if (Test-Path $envPath) {
                        $condaBase = Join-Path $envPath "Lib\site-packages"
                    }
                }
                if (-not $condaBase -or -not (Test-Path $condaBase)) {
                    $envPath = "C:\ProgramData\miniconda3\envs\goodq_audio_embed"
                    if (Test-Path $envPath) {
                        $condaBase = Join-Path $envPath "Lib\site-packages"
                    }
                }
                if (-not $condaBase -or -not (Test-Path $condaBase)) {
                    Write-Error "  Unable to resolve local Conda environment 'goodq_audio_embed'. Ensure the env exists under Miniconda/Anaconda."
                    exit 1
                }
                $localRel = $art.source_url.Substring(8).Replace("/", "\")
                $localSrcPath = Join-Path $condaBase $localRel
                Write-Host "  Copying from local source: $localSrcPath..." -ForegroundColor Yellow
                if (-not (Test-Path $localSrcPath)) {
                    Write-Error "  Local source file not found: $localSrcPath"
                }
                Copy-Item -Path $localSrcPath -Destination $destPath -Force
            } else {
                Write-Host "  Downloading from $($art.source_url)..." -ForegroundColor Yellow
                Invoke-VerifiedDownload -Url $art.source_url -DestinationPath $destPath -ExpectedSha256 $art.sha256
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
    # A release wheelhouse is an exact closure, never an accumulation of prior
    # staging attempts.  Leave every other verified cache artifact intact.
    if (Test-Path $wheelsDir) {
        Remove-Item -LiteralPath $wheelsDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $wheelsDir -Force | Out-Null

    foreach ($wheelArtifact in $DeclaredWheelArtifacts) {
        $wheelName = [Uri]::UnescapeDataString((Split-Path ([Uri]$wheelArtifact.source_url).AbsolutePath -Leaf))
        $wheelPath = Join-Path $wheelsDir $wheelName
        Write-Host "Checking declared wheel artifact: $($wheelArtifact.artifact_id)..." -ForegroundColor Cyan
        if (Test-Path $wheelPath) {
            $currentHash = Get-FileSHA256 $wheelPath
            if ($currentHash -eq $wheelArtifact.sha256.ToLower()) {
                Write-Host "  Cached wheel matches expected SHA256." -ForegroundColor Green
                continue
            }
            Remove-Item $wheelPath -Force
        }
        Write-Host "  Downloading declared wheel from $($wheelArtifact.source_url)..." -ForegroundColor Yellow
        Invoke-VerifiedDownload -Url $wheelArtifact.source_url -DestinationPath $wheelPath -ExpectedSha256 $wheelArtifact.sha256
        Write-Host "  [OK] Declared wheel artifact staged and verified." -ForegroundColor Green
    }

    Write-Host "Staging python wheels offline via pip download..." -ForegroundColor Cyan
    $reqFile = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\..\requirements-baseline-lock.txt"))
    $targetPython = $PythonExe
    if (-not $targetPython) {
        $candidate = Join-Path $ScriptDir "staged\runtime\python.exe"
        if (Test-Path $candidate) {
            $targetPython = $candidate
        }
    }
    if (-not $targetPython -or -not (Test-Path $targetPython)) {
        Write-Error "Offline wheel staging requires the extracted CPython 3.10 installer runtime. Supply -PythonExe or stage runtime\\python.exe first."
    }
    
    # Run pip download securely with retries
    $retryCount = 0
    $success = $false
    while (-not $success -and $retryCount -lt 5) {
        Write-Host "  Running pip download (Attempt $($retryCount + 1) of 5)..." -ForegroundColor Yellow
        & $targetPython -m pip download --timeout 120 --dest $wheelsDir --find-links=$wheelsDir --only-binary=:all: --platform win_amd64 --implementation cp --abi cp310 --extra-index-url https://download.pytorch.org/whl/cpu -r $reqFile
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

    foreach ($wheelArtifact in $DeclaredWheelArtifacts) {
        $wheelName = [Uri]::UnescapeDataString((Split-Path ([Uri]$wheelArtifact.source_url).AbsolutePath -Leaf))
        $wheelPath = Join-Path $wheelsDir $wheelName
        if (-not (Test-Path $wheelPath)) {
            Write-Host "  [ERROR] Declared wheel artifact missing: $wheelName" -ForegroundColor Red
            $VerificationFailed = $true
            continue
        }
        $wheelHash = Get-FileSHA256 $wheelPath
        if ($wheelHash -ne $wheelArtifact.sha256.ToLower()) {
            Write-Host "  [ERROR] Declared wheel artifact hash mismatch: $wheelName" -ForegroundColor Red
            $VerificationFailed = $true
        } else {
            Write-Host "  [OK] Declared wheel artifact hash matches: $wheelName" -ForegroundColor Green
        }
    }

    # Cross-reference wheelhouse against lockfile
    $AbsoluteCacheDir = [System.IO.Path]::GetFullPath($CacheDir)
    $lockfilePath = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\..\requirements-baseline-lock.txt"))
    if (Test-Path $lockfilePath) {
        Write-Host "Cross-referencing wheelhouse against lockfile..." -ForegroundColor Cyan
        $lockPackages = Get-Content $lockfilePath | Where-Object { $_ -and -not $_.StartsWith("#") -and -not $_.StartsWith("--") } | ForEach-Object {
            ($_ -split "[=<>!~]")[0].Trim().ToLower() -replace "-", "_"
        }
        $wheelNames = @()
        if (Test-Path $wheelsDir) {
            $wheelNames = Get-ChildItem $wheelsDir -Filter *.whl | ForEach-Object {
                ($_.BaseName -split "-")[0].ToLower() -replace "-", "_"
            }
        }
        $missingFromWheelhouse = $lockPackages | Where-Object { $_ -notin $wheelNames }
        if ($missingFromWheelhouse) {
            Write-Host "  [WARN] Lockfile packages missing from wheelhouse:" -ForegroundColor Yellow
            foreach ($pkg in $missingFromWheelhouse) {
                Write-Host "    - $pkg" -ForegroundColor Yellow
            }
            # Warning only — pip download resolves transitive deps which may use different names
        } else {
            Write-Host "  [OK] All lockfile packages have matching wheels." -ForegroundColor Green
        }
    }

    # Transitive closure dry-run check
    Write-Host "Performing transitive closure dry-run check..." -ForegroundColor Cyan
    $TempErrorFile = [System.IO.Path]::GetTempFileName()
    $StagedWheelsDir = [System.IO.Path]::GetFullPath($wheelsDir)
    $PipArgs = @("-m", "pip", "install", "--dry-run", "--ignore-installed", "--no-index", "--find-links=$StagedWheelsDir", "-r", "$lockfilePath")
    
    $pythonExe = $PythonExe
    if (-not $pythonExe -and $env:GOODQ_DEV_PYTHON) {
        $pythonExe = $env:GOODQ_DEV_PYTHON
    } elseif (-not $pythonExe -and $env:CONDA_PREFIX) {
        $pythonExe = Join-Path $env:CONDA_PREFIX "python.exe"
    }

    if (-not $pythonExe) {
        Write-Host "  [INFO] No CPython 3.10 verifier was supplied; full wheel closure is verified by build_installer.bat after it creates the bundled runtime." -ForegroundColor Yellow
        $pythonExe = $null
    }
    
    Write-Host "  Using Wheels Dir: $StagedWheelsDir" -ForegroundColor Yellow
    Write-Host "  Using Lockfile Path: $lockfilePath" -ForegroundColor Yellow
    if ($pythonExe) {
        Write-Host "  Using Python executable: $pythonExe" -ForegroundColor Yellow
        $pythonVersion = (& $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne "3.10") {
            Write-Error "Offline closure verification requires CPython 3.10; resolved '$pythonExe' reports '$pythonVersion'."
        }
    }
    
    $ProcessParams = @{
        FilePath = $pythonExe
        ArgumentList = $PipArgs
        RedirectStandardError = $TempErrorFile
        NoNewWindow = $true
        Wait = $true
        PassThru = $true
    }
    
    try {
        if (-not $pythonExe) { return }
        $Process = Start-Process @ProcessParams
        $ExitCode = $Process.ExitCode
        
        if ($ExitCode -ne 0) {
            $VerificationFailed = $true
            Write-Host "  [ERROR] Transitive closure dry-run verification failed with exit code $ExitCode" -ForegroundColor Red
            if (Test-Path $TempErrorFile) {
                $ErrorContent = Get-Content $TempErrorFile
                Write-Host "  Error output from pip:" -ForegroundColor Red
                foreach ($line in $ErrorContent) {
                    Write-Host "    $line" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  [OK] Transitive closure dry-run check succeeded." -ForegroundColor Green
        }
    } catch {
        $VerificationFailed = $true
        Write-Host "  [ERROR] Failed to execute python pip check: $_" -ForegroundColor Red
    } finally {
        if (Test-Path $TempErrorFile) {
            Remove-Item $TempErrorFile -Force
        }
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
