<#
.SYNOPSIS
    Post-install integrity validation for GoodQ4All offline installer.
.DESCRIPTION
    Three-gate validation:
    Gate 1: File Integrity - verify critical files exist
    Gate 2: Launcher Manifest - run LAUNCH_GOODQ.exe --verify-manifest-only
    Gate 3: Version Consistency - compare goodq_version.py vs install_receipt.json
.PARAMETER InstallDir
    Root directory of the GoodQ4All installation.
    Defaults to $env:ProgramFiles\GoodQ4All
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\GoodQ4All",
    [ValidateSet("PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")]
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"
$results = @{ gates = @(); pass = $true; install_dir = $InstallDir }
$profilePath = Join-Path $InstallDir "configs\installer_profile.txt"
if (-not $Profile -and (Test-Path -LiteralPath $profilePath)) {
    $Profile = (Get-Content -LiteralPath $profilePath -Raw).Trim()
}
if (-not $Profile) { $Profile = "PUBLIC_CPU_BASELINE" }
if ($Profile -notin @("PUBLIC_CPU_BASELINE", "PUBLIC_GPU_ENHANCED", "PERSONAL_AIR_GAP")) {
    throw "Unknown installer profile in verification target: $Profile"
}
$results.profile = $Profile
$modelPackRoot = Join-Path $env:ProgramData "GoodQ4All\models"

# --- Gate 1: File Integrity ---
$gate1 = @{ name = "file_integrity"; pass = $true; errors = @() }
$criticalFiles = @(
    "runtime\python.exe",
    "LAUNCH_GOODQ.exe",
    "goodq_version.py",
    "qdrant\qdrant.exe",
    "ffmpeg\ffmpeg.exe",
    "ffmpeg\ffprobe.exe",
    "ffmpeg\LICENSE.txt",
    "ffmpeg\SOURCE_URL.txt",
    "configs\config.yaml",
    "configs\model_download_manifest.json",
    "configs\model_download_manifest.json.sig",
    "configs\selected_capabilities.json",
    "configs\selected_capabilities.json.sig",
    "poppler\pdftotext.exe",
    (Join-Path $modelPackRoot "model_packs\object_detection_cpu\models\opencv_zoo\object_detection_nanodet_2022nov.onnx")
)
if ($Profile -ne "PUBLIC_CPU_BASELINE") {
    $criticalFiles += @(
        (Join-Path $modelPackRoot "model_packs\object_detection_gpu\models\opencv_zoo\object_detection_yolox_2022nov.onnx")
    )
}
foreach ($f in $criticalFiles) {
    $fullPath = if ([IO.Path]::IsPathRooted($f)) { $f } else { Join-Path $InstallDir $f }
    if (-not (Test-Path $fullPath)) {
        $gate1.pass = $false
        $gate1.errors += "Missing: $f"
        Write-Host "  [FAIL] Missing: $f" -ForegroundColor Red
    } else {
        Write-Host "  [OK]   $f" -ForegroundColor Green
    }
}
if (-not $gate1.pass) { $results.pass = $false }
$results.gates += $gate1

# --- Gate 1b: Bundled Media Runtime ---
$gate1b = @{ name = "media_runtime"; pass = $true; errors = @() }
foreach ($tool in @("ffmpeg", "ffprobe")) {
    $toolPath = Join-Path $InstallDir ("ffmpeg\{0}.exe" -f $tool)
    try {
        & $toolPath -version *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "exit code $LASTEXITCODE"
        }
        Write-Host "  [OK]   Bundled $tool runtime executes" -ForegroundColor Green
    } catch {
        $gate1b.pass = $false
        $gate1b.errors += "Bundled $tool runtime failed: $_"
        Write-Host "  [FAIL] Bundled $tool runtime failed: $_" -ForegroundColor Red
    }
}
if (-not $gate1b.pass) { $results.pass = $false }
$results.gates += $gate1b

# --- Gate 1bb: Bundled Document Runtime ---
$gate1bb = @{ name = "document_runtime"; pass = $true; errors = @() }
$pdftotextPath = Join-Path $InstallDir "poppler\pdftotext.exe"
$pdftotextStdout = Join-Path ([IO.Path]::GetTempPath()) ("goodq4all-pdftotext-{0}.stdout" -f [guid]::NewGuid())
$pdftotextStderr = Join-Path ([IO.Path]::GetTempPath()) ("goodq4all-pdftotext-{0}.stderr" -f [guid]::NewGuid())
try {
    $pdftotextProcess = Start-Process -FilePath $pdftotextPath -ArgumentList "-v" -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $pdftotextStdout -RedirectStandardError $pdftotextStderr
    if ($pdftotextProcess.ExitCode -ne 0) {
        $diagnostic = if (Test-Path -LiteralPath $pdftotextStderr) {
            (Get-Content -LiteralPath $pdftotextStderr -Raw).Trim()
        } else {
            "no stderr captured"
        }
        throw "exit code $($pdftotextProcess.ExitCode): $diagnostic"
    }
    Write-Host "  [OK]   Bundled Poppler pdftotext runtime executes" -ForegroundColor Green
} catch {
    $gate1bb.pass = $false
    $gate1bb.errors += "Bundled Poppler pdftotext runtime failed: $_"
    Write-Host "  [FAIL] Bundled Poppler pdftotext runtime failed: $_" -ForegroundColor Red
} finally {
    Remove-Item -LiteralPath $pdftotextStdout, $pdftotextStderr -Force -ErrorAction SilentlyContinue
}
if (-not $gate1bb.pass) { $results.pass = $false }
$results.gates += $gate1bb

# --- Gate 1c: OCR Runtime ---
$gate1c = @{ name = "ocr_runtime"; pass = $true; errors = @() }
$pythonPath = Join-Path $InstallDir "runtime\python.exe"
$tesseractPath = Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"
try {
    & $pythonPath -c "import pytesseract; print(pytesseract.__version__)" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "pytesseract import returned exit code $LASTEXITCODE"
    }
    Write-Host "  [OK]   Python pytesseract binding imports" -ForegroundColor Green
} catch {
    $gate1c.pass = $false
    $gate1c.errors += "Python pytesseract binding failed: $_"
    Write-Host "  [FAIL] Python pytesseract binding failed: $_" -ForegroundColor Red
}
try {
    & $tesseractPath --version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "exit code $LASTEXITCODE"
    }
    Write-Host "  [OK]   Tesseract OCR runtime executes" -ForegroundColor Green
} catch {
    $gate1c.pass = $false
    $gate1c.errors += "Tesseract OCR runtime failed: $_"
    Write-Host "  [FAIL] Tesseract OCR runtime failed: $_" -ForegroundColor Red
}
if (-not $gate1c.pass) { $results.pass = $false }
$results.gates += $gate1c

# --- Gate 1d: Sealed object-detection baseline ---
$gate1d = @{ name = "object_detection_payload"; pass = $true; errors = @() }
$nanodetPath = Join-Path $modelPackRoot "model_packs\object_detection_cpu\models\opencv_zoo\object_detection_nanodet_2022nov.onnx"
$expectedNanoDet = "4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186"
$yoloxPath = Join-Path $modelPackRoot "model_packs\object_detection_gpu\models\opencv_zoo\object_detection_yolox_2022nov.onnx"
$expectedYoloX = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
try {
    if ((Get-FileHash -LiteralPath $nanodetPath -Algorithm SHA256).Hash.ToLower() -ne $expectedNanoDet) {
        throw "NanoDet SHA256 mismatch"
    }
    & $pythonPath -c "import cv2; cv2.dnn.readNet(r'$nanodetPath'); print('NanoDet ready')" *> $null
    if ($LASTEXITCODE -ne 0) { throw "OpenCV DNN could not load NanoDet" }
    if ($Profile -ne "PUBLIC_CPU_BASELINE") {
        if ((Get-FileHash -LiteralPath $yoloxPath -Algorithm SHA256).Hash.ToLower() -ne $expectedYoloX) {
            throw "YOLOX SHA256 mismatch"
        }
        & $pythonPath -c "import cv2; cv2.dnn.readNet(r'$yoloxPath'); print('YOLOX ready')" *> $null
        if ($LASTEXITCODE -ne 0) { throw "OpenCV DNN could not load YOLOX" }
        Write-Host "  [OK]   Sealed NanoDet and YOLOX payloads verify and load" -ForegroundColor Green
    } else {
        Write-Host "  [OK]   Sealed NanoDet payload verifies and loads (CPU profile)" -ForegroundColor Green
    }
} catch {
    $gate1d.pass = $false
    $gate1d.errors += "Object-detection baseline failed: $_"
    Write-Host "  [FAIL] Object-detection baseline failed: $_" -ForegroundColor Red
}
if (-not $gate1d.pass) { $results.pass = $false }
$results.gates += $gate1d

# --- Gate 1e: Complete selected profile payload ---
$gate1e = @{ name = "selected_profile_payload"; pass = $true; errors = @() }
try {
    & $pythonPath (Join-Path $InstallDir "scripts\install\verify_profile_model_payload.py") --install-dir $InstallDir --models-root $modelPackRoot *> $null
    if ($LASTEXITCODE -ne 0) { throw "profile capability verification returned exit code $LASTEXITCODE" }
    Write-Host "  [OK]   Every selected model and lexicon payload resolves from the installed offline cache" -ForegroundColor Green
} catch {
    $gate1e.pass = $false
    $gate1e.errors += "Selected profile payload failed: $_"
    Write-Host "  [FAIL] Selected profile payload failed: $_" -ForegroundColor Red
}
if (-not $gate1e.pass) { $results.pass = $false }
$results.gates += $gate1e

# --- Gate 2: Launcher Manifest Verification ---
$gate2 = @{ name = "launcher_manifest"; pass = $true; errors = @() }
$launcherPath = Join-Path $InstallDir "LAUNCH_GOODQ.exe"
if (Test-Path $launcherPath) {
    try {
        $proc = Start-Process -FilePath $launcherPath -ArgumentList "--verify-manifest-only" -Wait -PassThru -NoNewWindow -RedirectStandardOutput "$env:TEMP\verify_out.tmp" -RedirectStandardError "$env:TEMP\verify_err.tmp"
        if ($proc.ExitCode -ne 0) {
            $gate2.pass = $false
            $gate2.errors += "Launcher manifest verification returned exit code $($proc.ExitCode)"
            Write-Host "  [FAIL] Launcher manifest verification failed (exit $($proc.ExitCode))" -ForegroundColor Red
        } else {
            Write-Host "  [OK]   Launcher manifest verification passed" -ForegroundColor Green
        }
    } catch {
        $gate2.pass = $false
        $gate2.errors += "Could not run launcher: $_"
        Write-Host "  [FAIL] Could not execute launcher: $_" -ForegroundColor Red
    }
} else {
    $gate2.pass = $false
    $gate2.errors += "Launcher binary not found"
    Write-Host "  [SKIP] Launcher binary not found - skipping manifest gate" -ForegroundColor Yellow
}
if (-not $gate2.pass) { $results.pass = $false }
$results.gates += $gate2

# --- Gate 3: Version Consistency ---
$gate3 = @{ name = "version_consistency"; pass = $true; errors = @() }
$versionPyPath = Join-Path $InstallDir "goodq_version.py"
$receiptPath = Join-Path $InstallDir "data\install_receipt.json"
if (-not (Test-Path $receiptPath)) {
    $receiptPath = "$env:ProgramData\GoodQ4All\install_receipt.json"
}
try {
    $versionLine = Get-Content $versionPyPath | Where-Object { $_ -match 'GOODQ_VERSION\s*=\s*"([^"]+)"' }
    $sourceVersion = $Matches[1]
} catch {
    $sourceVersion = $null
    $gate3.errors += "Could not parse goodq_version.py"
}
if (Test-Path $receiptPath) {
    try {
        $receipt = Get-Content $receiptPath -Raw | ConvertFrom-Json
        $receiptVersion = $receipt.version
    } catch {
        $receiptVersion = $null
        $gate3.errors += "Could not parse install_receipt.json"
    }
} else {
    $receiptVersion = $null
    $gate3.errors += "install_receipt.json not found"
}
if ($sourceVersion -and $receiptVersion) {
    if ($sourceVersion -ne $receiptVersion) {
        $gate3.pass = $false
        $gate3.errors += "Version mismatch: goodq_version.py=$sourceVersion, receipt=$receiptVersion"
        Write-Host "  [FAIL] Version mismatch: source=$sourceVersion receipt=$receiptVersion" -ForegroundColor Red
    } else {
        Write-Host "  [OK]   Version consistent: $sourceVersion" -ForegroundColor Green
    }
} else {
    $gate3.pass = $false
    Write-Host "  [WARN] Could not compare versions" -ForegroundColor Yellow
}
if (-not $gate3.pass) { $results.pass = $false }
$results.gates += $gate3

# --- Summary ---
$results | ConvertTo-Json -Depth 4
if ($results.pass) {
    Write-Host "`n[PASS] All verification gates passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n[FAIL] One or more verification gates failed." -ForegroundColor Red
    exit 1
}
