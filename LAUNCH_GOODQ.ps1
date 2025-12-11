# GoodQ4All Master Launcher
# Auto-healing, health-checking, production-ready launch system

param(
    [switch]$DryRun,
    [switch]$SkipHealthCheck,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ==================== CONFIGURATION ====================
$script:RootDir = "L:\goodq4all"
$script:DataRoot = "L:\_DATA\GoodQ_Data"
$script:InboxPath = "$script:DataRoot\import_inbox"
$script:QdrantURL = "http://localhost:6333"
$script:LogDir = "$script:RootDir\logs"
$script:ConfigPath = "$script:RootDir\configs\config.yaml"
$script:IssuesFound = 0
$script:IssuesAutoFixed = 0

# Colors
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Cyan = "Cyan"
$Magenta = "Magenta"
$Gray = "DarkGray"

# ==================== HELPER FUNCTIONS ====================

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor $Cyan
    Write-Host "  $Text" -ForegroundColor $Cyan
    Write-Host ("=" * 60) -ForegroundColor $Cyan
    Write-Host ""
}

function Write-StatusLine {
    param(
        [string]$Label,
        [string]$Status,
        [string]$Level = "INFO"
    )
    
    $icon = switch ($Level) {
        "SUCCESS" { "[OK]"; $Green }
        "ERROR" { "[!!]"; $Red }
        "WARN" { "[!]"; $Yellow }
        "INFO" { "[i]"; $Cyan }
        default { "[ ]"; $Gray }
    }
    
    $color = $icon[1]
    $symbol = $icon[0]
    
    Write-Host "  $symbol " -ForegroundColor $color -NoNewline
    Write-Host "$Label`: " -NoNewline
    Write-Host "$Status" -ForegroundColor $color
}

function Test-PythonEnvironment {
    Write-Host "  [Python Environment]" -ForegroundColor $Cyan
    
    try {
        $pyVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-StatusLine "Python" $pyVersion "SUCCESS"
        } else {
            Write-StatusLine "Python" "Not found" "ERROR"
            $script:IssuesFound++
        }
    } catch {
        Write-StatusLine "Python" "Not found" "ERROR"
        $script:IssuesFound++
    }
    
    try {
        $pipVersion = pip --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-StatusLine "Pip" "Installed" "SUCCESS"
        }
    } catch {
        Write-StatusLine "Pip" "Not found" "WARN"
    }
}

function Test-QdrantService {
    Write-Host "  [Qdrant Service]" -ForegroundColor $Cyan
    
    try {
        $response = Invoke-RestMethod -Uri "$script:QdrantURL/collections" -Method Get -TimeoutSec 5
        Write-StatusLine "Qdrant API" "Running at $script:QdrantURL" "SUCCESS"
        
        $collections = $response.result.collections
        if ($collections) {
            Write-StatusLine "Collections" "$($collections.Count) found" "SUCCESS"
        } else {
            Write-StatusLine "Collections" "None yet (will be created)" "INFO"
        }
        
    } catch {
        Write-StatusLine "Qdrant" "Not responding" "WARN"
        Write-Host "    Attempting to start Qdrant service..." -ForegroundColor $Yellow
        
        try {
            Start-Service -Name "GoodQ_Qdrant" -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
            
            $response = Invoke-RestMethod -Uri "$script:QdrantURL/collections" -Method Get -TimeoutSec 5
            Write-StatusLine "Qdrant" "Started successfully" "SUCCESS"
            $script:IssuesAutoFixed++
            
        } catch {
            Write-StatusLine "Qdrant" "Failed to start - manual intervention required" "ERROR"
            $script:IssuesFound++
        }
    }
}

function Test-Directories {
    Write-Host "  [Directory Structure]" -ForegroundColor $Cyan
    
    $criticalDirs = @(
        $script:DataRoot,
        $script:InboxPath,
        "$script:DataRoot\processing",
        "$script:DataRoot\processed",
        $script:LogDir
    )
    
    foreach ($dir in $criticalDirs) {
        if (Test-Path $dir) {
            Write-StatusLine (Split-Path $dir -Leaf) "Exists" "SUCCESS"
        } else {
            Write-StatusLine (Split-Path $dir -Leaf) "Missing - creating..." "WARN"
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-StatusLine (Split-Path $dir -Leaf) "Created" "SUCCESS"
            $script:IssuesAutoFixed++
        }
    }
}

function Test-ConfigFiles {
    Write-Host "  [Configuration Files]" -ForegroundColor $Cyan
    
    $configs = @(
        "$script:RootDir\configs\config.yaml",
        "$script:RootDir\configs\open_config.yaml",
        "$script:RootDir\configs\models_config.yaml"
    )
    
    foreach ($cfg in $configs) {
        if (Test-Path $cfg) {
            $size = (Get-Item $cfg).Length
            Write-StatusLine (Split-Path $cfg -Leaf) "$size bytes" "SUCCESS"
        } else {
            Write-StatusLine (Split-Path $cfg -Leaf) "Missing" "ERROR"
            $script:IssuesFound++
        }
    }
}

function Test-APIKeys {
    Write-Host "  [API Keys]" -ForegroundColor $Cyan
    
    $criticalEnvVars = @(
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY"
    )
    
    foreach ($var in $criticalEnvVars) {
        if (Test-Path "env:$var") {
            Write-StatusLine $var "Configured" "SUCCESS"
        } else {
            Write-StatusLine $var "Not set" "WARN"
        }
    }
}

function Start-LogMonitor {
    Write-Host "  Starting log monitor..." -ForegroundColor $Cyan
    
    $latestLog = Get-ChildItem "$script:LogDir\*.log" -ErrorAction SilentlyContinue | 
                 Sort-Object LastWriteTime -Descending | 
                 Select-Object -First 1
    
    if ($latestLog) {
        Write-StatusLine "Latest Log" $latestLog.Name "INFO"
        
        $monitorScript = @"
`$host.UI.RawUI.WindowTitle = 'GoodQ4All - Live Logs'
Get-Content '$($latestLog.FullName)' -Wait -Tail 50 | ForEach-Object {
    if (`$_ -match 'ERROR|CRITICAL') {
        Write-Host `$_ -ForegroundColor Red
    } elseif (`$_ -match 'WARNING|WARN') {
        Write-Host `$_ -ForegroundColor Yellow
    } elseif (`$_ -match 'SUCCESS|COMPLETE') {
        Write-Host `$_ -ForegroundColor Green
    } else {
        Write-Host `$_
    }
}
"@
        
        if (!$DryRun) {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", $monitorScript
            Write-StatusLine "Log Monitor" "Launched in new window" "SUCCESS"
        } else {
            Write-StatusLine "Log Monitor" "Skipped (dry run)" "INFO"
        }
    } else {
        Write-StatusLine "Log Monitor" "No logs found yet" "WARN"
    }
}

function Start-WatchdogService {
    Write-Host "  Starting file watchdog..." -ForegroundColor $Cyan
    
    if (!$DryRun) {
        $watchdogCmd = "python -m cli.run_ingestion watch --inbox-path `"$script:InboxPath`""
        
        Start-Process powershell -ArgumentList @(
            "-NoExit",
            "-Command",
            "cd '$script:RootDir'; `$host.UI.RawUI.WindowTitle='GoodQ4All - Watchdog'; $watchdogCmd"
        )
        
        Write-StatusLine "Watchdog" "Launched - monitoring $script:InboxPath" "SUCCESS"
    } else {
        Write-StatusLine "Watchdog" "Skipped (dry run)" "INFO"
    }
}

# ==================== MAIN EXECUTION ====================

function Main {
    Clear-Host
    
    Write-Host ""
    Write-Host "   ___               _ ___  _  _   _   _    _    " -ForegroundColor $Magenta
    Write-Host "  / __|___ ___  __| / _ \| || | /_\ | |  | |   " -ForegroundColor $Magenta  
    Write-Host " | (_ / _ \ _ \/ _  | (_) |_  _|/ _ \| |__| |__ " -ForegroundColor $Magenta
    Write-Host "  \___\___\___/\__\_|\__\_\ |_|/_/ \_\____|____|" -ForegroundColor $Magenta
    Write-Host ""
    Write-Host "  Production-Ready Multimodal AI Pipeline" -ForegroundColor $Cyan
    Write-Host ""
    
    if ($DryRun) {
        Write-Host "  MODE: DRY RUN (no services will start)" -ForegroundColor $Yellow
        Write-Host ""
    }
    
    # HEALTH CHECKS
    if (!$SkipHealthCheck) {
        Write-Header "SYSTEM HEALTH CHECK"
        
        Test-PythonEnvironment
        Test-QdrantService
        Test-Directories
        Test-ConfigFiles
        Test-APIKeys
        
        Write-Host ""
        if ($script:IssuesFound -eq 0 -and $script:IssuesAutoFixed -eq 0) {
            Write-Host "  [OK] All systems nominal" -ForegroundColor $Green
        } elseif ($script:IssuesFound -eq 0) {
            Write-Host "  [OK] All issues auto-fixed ($script:IssuesAutoFixed fixes applied)" -ForegroundColor $Green
        } else {
            Write-Host "  [!!] $script:IssuesFound critical issues found - review above" -ForegroundColor $Red
            Write-Host ""
            $continue = Read-Host "Continue anyway? (y/N)"
            if ($continue -ne 'y') {
                exit 1
            }
        }
    } else {
        Write-Host "  [!] Health checks skipped (--SkipHealthCheck)" -ForegroundColor $Yellow
    }
    
    # LAUNCH SERVICES
    Write-Header "LAUNCHING SERVICES"
    
    Start-LogMonitor
    Start-WatchdogService
    
    # SUMMARY
    Write-Header "GOODQ4ALL IS RUNNING"
    
    Write-Host "  Qdrant API:    $script:QdrantURL" -ForegroundColor $Cyan
    Write-Host "  Inbox Path:    $script:InboxPath" -ForegroundColor $Cyan
    Write-Host "  Logs:          $script:LogDir" -ForegroundColor $Cyan
    Write-Host ""
    Write-Host "  Drop video files into the inbox to begin processing" -ForegroundColor $Green
    Write-Host ""
    Write-Host "Press Ctrl+C in watchdog window to stop" -ForegroundColor $Gray
    Write-Host ""
    
    if (!$DryRun) {
        Read-Host "Press Enter to close this window"
    }
}

# RUN
Main
