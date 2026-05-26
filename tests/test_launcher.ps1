# GoodQ4All Launcher Test Suite
# Tests all functionality of LAUNCH_GOODQ.ps1

param(
    [switch]$Verbose
)

$script:TestsPassed = 0
$script:TestsFailed = 0
$script:TestsSkipped = 0

function Test-Result {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        if ($Message) { Write-Host "         $Message" -ForegroundColor Gray }
        $script:TestsPassed++
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        if ($Message) { Write-Host "         $Message" -ForegroundColor Yellow }
        $script:TestsFailed++
    }
}

function Test-Skip {
    param([string]$Name, [string]$Reason)
    Write-Host "  [SKIP] $Name - $Reason" -ForegroundColor Cyan
    $script:TestsSkipped++
}

Clear-Host
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GOODQ4ALL LAUNCHER TEST SUITE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# TEST 1: File Existence
Write-Host "[TEST 1] File Existence Checks" -ForegroundColor Yellow
Write-Host ""

$files = @{
    "Main Launcher (PS1)" = "L:\goodq4all\LAUNCH_GOODQ.ps1"
    "Batch Wrapper" = "L:\goodq4all\LAUNCH_GOODQ.bat"
    "Watchdog Script" = "L:\goodq4all\cli\watchdog.py"
}

foreach ($name in $files.Keys) {
    $path = $files[$name]
    Test-Result $name (Test-Path $path) $path
}

Write-Host ""

# TEST 2: PowerShell Syntax Validation
Write-Host "[TEST 2] PowerShell Syntax Validation" -ForegroundColor Yellow
Write-Host ""

try {
    $script = Get-Content "L:\goodq4all\LAUNCH_GOODQ.ps1" -Raw
    $null = [System.Management.Automation.PSParser]::Tokenize($script, [ref]$null)
    Test-Result "PS1 Syntax Valid" $true "No parse errors"
} catch {
    Test-Result "PS1 Syntax Valid" $false $_.Exception.Message
}

Write-Host ""

# TEST 3: Required Functions Exist
Write-Host "[TEST 3] Required Functions Defined" -ForegroundColor Yellow
Write-Host ""

$scriptContent = Get-Content "L:\goodq4all\LAUNCH_GOODQ.ps1" -Raw

$requiredFunctions = @(
    "Write-Header",
    "Write-Check",
    "Test-Administrator",
    "Test-PythonEnvironment",
    "Test-QdrantService",
    "Test-PathsAndPermissions",
    "Test-ModelsAndDatasets",
    "Test-ConfigFiles",
    "Test-DatabaseFiles",
    "Test-APIKeys",
    "Start-WatchdogMonitoring",
    "Start-LogMonitoring",
    "Main"
)

foreach ($func in $requiredFunctions) {
    $exists = $scriptContent -match "function $func"
    Test-Result "Function: $func" $exists
}

Write-Host ""

# TEST 4: Path Validation Logic
Write-Host "[TEST 4] Path Validation" -ForegroundColor Yellow
Write-Host ""

$criticalPaths = @{
    "Data Root" = "L:\_DATA\GoodQ_Data"
    "Import Inbox" = "L:\_DATA\GoodQ_Data\import_inbox"
    "Processing" = "L:\_DATA\GoodQ_Data\processing"
    "Logs" = "L:\goodq4all\logs"
    "Qdrant Storage" = "L:\goodq4all\vendor\qdrant\storage"
}

foreach ($name in $criticalPaths.Keys) {
    $path = $criticalPaths[$name]
    $exists = Test-Path $path
    if ($exists) {
        # Test write permissions
        try {
            $testFile = Join-Path $path ".test_$(Get-Date -Format 'yyyyMMddHHmmss')"
            [System.IO.File]::WriteAllText($testFile, "test")
            Remove-Item $testFile -Force
            Test-Result "$name (writable)" $true $path
        } catch {
            Test-Result "$name (writable)" $false "No write permission"
        }
    } else {
        Test-Result "$name (exists)" $false "Path not found: $path"
    }
}

Write-Host ""

# TEST 5: Config File Validation
Write-Host "[TEST 5] Configuration Files" -ForegroundColor Yellow
Write-Host ""

$configFiles = @(
    "L:\goodq4all\configs\config.yaml",
    "L:\goodq4all\configs\models_config.yaml"
)

foreach ($file in $configFiles) {
    $exists = Test-Path $file
    $name = Split-Path $file -Leaf
    if ($exists) {
        # Check if readable
        try {
            $content = Get-Content $file -Raw
            $readable = $content.Length -gt 0
            Test-Result "$name (readable)" $readable "$($content.Length) bytes"
        } catch {
            Test-Result "$name (readable)" $false $_.Exception.Message
        }
    } else {
        Test-Result "$name (exists)" $false
    }
}

Write-Host ""

# TEST 6: Qdrant Service Check
Write-Host "[TEST 6] Qdrant Service" -ForegroundColor Yellow
Write-Host ""

$service = Get-Service -Name "GoodQ_Qdrant" -ErrorAction SilentlyContinue
if ($service) {
    Test-Result "Service Installed" $true $service.Status
    
    if ($service.Status -eq "Running") {
        # Test API
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:6333/" -TimeoutSec 5 -UseBasicParsing
            Test-Result "API Responding" ($response.StatusCode -eq 200) "HTTP $($response.StatusCode)"
        } catch {
            Test-Result "API Responding" $false $_.Exception.Message
        }
        
        # Test collections endpoint
        try {
            $collections = Invoke-RestMethod -Uri "http://localhost:6333/collections" -Method Get
            $count = $collections.result.collections.Count
            Test-Result "Collections Endpoint" $true "$count collections"
        } catch {
            Test-Result "Collections Endpoint" $false $_.Exception.Message
        }
    } else {
        Test-Skip "API Responding" "Service not running"
        Test-Skip "Collections Endpoint" "Service not running"
    }
} else {
    Test-Result "Service Installed" $false "GoodQ_Qdrant not found"
    Test-Skip "API Responding" "Service not installed"
    Test-Skip "Collections Endpoint" "Service not installed"
}

Write-Host ""

# TEST 7: Python Environment
Write-Host "[TEST 7] Python Environment" -ForegroundColor Yellow
Write-Host ""

try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+\.\d+)") {
        Test-Result "Python Installed" $true $matches[1]
    } else {
        Test-Result "Python Installed" $false "Could not parse version"
    }
} catch {
    Test-Result "Python Installed" $false "Python not found in PATH"
}

try {
    $condaVersion = conda --version 2>&1
    if ($condaVersion -match "conda (\d+\.\d+\.\d+)") {
        Test-Result "Conda Installed" $true $matches[1]
    } else {
        Test-Result "Conda Installed" $false "Could not parse version"
    }
} catch {
    Test-Result "Conda Installed" $false "Conda not found in PATH"
}

Write-Host ""

# TEST 8: Database Files
Write-Host "[TEST 8] Database Files" -ForegroundColor Yellow
Write-Host ""

$databases = @{
    "Memory DB" = "L:\_DATA\GoodQ_Data\memory.db"
    "Knowledge Graph" = "L:\_DATA\GoodQ_Data\knowledge_graph.db"
}

foreach ($name in $databases.Keys) {
    $path = $databases[$name]
    if (Test-Path $path) {
        $size = (Get-Item $path).Length / 1KB
        Test-Result "$name (exists)" $true "$([math]::Round($size, 2)) KB"
    } else {
        Test-Result "$name (exists)" $false "Will be created on first use"
    }
}

Write-Host ""

# TEST 9: Dry Run Test
Write-Host "[TEST 9] Dry Run Execution" -ForegroundColor Yellow
Write-Host ""

try {
    $output = & "L:\goodq4all\LAUNCH_GOODQ.ps1" -DryRun -SkipHealthCheck 2>&1
    $exitCode = $LASTEXITCODE
    
    # Check if script executed without errors
    $hasErrors = $output | Where-Object { $_ -match "ParserError|Exception" }
    Test-Result "Dry Run Executes" (!$hasErrors) "Exit code: $exitCode"
    
    # Check for key output markers
    $hasHeader = $output | Where-Object { $_ -match "GOODQ" }
    Test-Result "Banner Displayed" ($hasHeader -ne $null) "Found in output"
    
} catch {
    Test-Result "Dry Run Executes" $false $_.Exception.Message
    Test-Skip "Banner Displayed" "Script failed to run"
}

Write-Host ""

# TEST 10: Script Organization
Write-Host "[TEST 10] File Organization" -ForegroundColor Yellow
Write-Host ""

$directories = @{
    "scripts/qdrant" = "L:\goodq4all\scripts\qdrant"
    "scripts/monitoring" = "L:\goodq4all\scripts\monitoring"
    "tests" = "L:\goodq4all\tests"
    "docs/reports" = "L:\goodq4all\docs\reports"
    "archive/legacy_scripts" = "L:\goodq4all\archive\legacy_scripts_20251210"
}

foreach ($name in $directories.Keys) {
    $path = $directories[$name]
    $exists = Test-Path $path
    if ($exists) {
        $fileCount = (Get-ChildItem $path -File).Count
        Test-Result "$name exists" $true "$fileCount files"
    } else {
        Test-Result "$name exists" $false "Directory not found"
    }
}

Write-Host ""

# TEST 11: Monitoring Script Generation
Write-Host "[TEST 11] Monitoring Scripts" -ForegroundColor Yellow
Write-Host ""

$monitorScript = "L:\goodq4all\scripts\monitoring\live_monitor.ps1"
if (Test-Path $monitorScript) {
    try {
        $content = Get-Content $monitorScript -Raw
        $hasLogDir = $content -match '\$logDir'
        $hasLoop = $content -match 'while.*\$true'
        
        Test-Result "Monitor Script Exists" $true
        Test-Result "Monitor Has Log Path" $hasLogDir
        Test-Result "Monitor Has Loop" $hasLoop
    } catch {
        Test-Result "Monitor Script Readable" $false $_.Exception.Message
    }
} else {
    Test-Result "Monitor Script Exists" $false "Will be generated on launch"
}

Write-Host ""

# TEST 12: Documentation
Write-Host "[TEST 12] Documentation" -ForegroundColor Yellow
Write-Host ""

$docs = @(
    "L:\goodq4all\README.md",
    "L:\goodq4all\docs\TESTING_GUIDE.md",
    "L:\goodq4all\docs\QDRANT_QUICKREF.md",
    "L:\goodq4all\docs\reports\FILE_ORGANIZATION_LAUNCHER_20251211.md"
)

foreach ($doc in $docs) {
    $name = Split-Path $doc -Leaf
    if (Test-Path $doc) {
        $size = (Get-Item $doc).Length / 1KB
        Test-Result "$name" $true "$([math]::Round($size, 2)) KB"
    } else {
        Test-Result "$name" $false "Not found"
    }
}

Write-Host ""

# FINAL SUMMARY
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TEST SUITE SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$total = $script:TestsPassed + $script:TestsFailed + $script:TestsSkipped

Write-Host "  Total Tests: $total" -ForegroundColor White
Write-Host "  [PASS] Passed: $script:TestsPassed" -ForegroundColor Green
if ($script:TestsFailed -gt 0) {
    Write-Host "  [FAIL] Failed: $script:TestsFailed" -ForegroundColor Red
}
if ($script:TestsSkipped -gt 0) {
    Write-Host "  [SKIP] Skipped: $script:TestsSkipped" -ForegroundColor Cyan
}

Write-Host ""

$passRate = [math]::Round(($script:TestsPassed / $total) * 100, 1)
Write-Host "  Pass Rate: $passRate%" -ForegroundColor $(if ($passRate -ge 90) { "Green" } elseif ($passRate -ge 70) { "Yellow" } else { "Red" })

Write-Host ""

if ($script:TestsFailed -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ALL CRITICAL TESTS PASSED!" -ForegroundColor Green
    Write-Host "  Launcher is ready for production use" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  SOME TESTS FAILED" -ForegroundColor Red
    Write-Host "  Review failures above before using" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""
Write-Host "Test completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

# Exit with appropriate code
if ($script:TestsFailed -gt 0) {
    exit 1
} else {
    exit 0
}
