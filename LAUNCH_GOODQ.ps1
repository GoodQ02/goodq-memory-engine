# GoodQ4All Master Launcher
# Auto-healing, health-checking, production-ready launch system

param(
    [switch]$DryRun,
    [switch]$SkipHealthCheck,
    [switch]$Verbose,
    [switch]$ForceReprocess,
    [switch]$StartIngestion
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Safe-by-default: if the operator did not explicitly request ingestion, default to dry-run.
if (-not $PSBoundParameters.ContainsKey('DryRun') -and -not $StartIngestion) {
    $DryRun = $true
}

# ==================== CONFIGURATION ====================
$script:RootDir = $PSScriptRoot
$script:DataRoot = "L:\_DATA\GoodQ_Data"
$script:InboxPath = "$script:DataRoot\import_inbox"
$script:QdrantURL = "http://localhost:6333"
$script:LogDir = "$script:RootDir\logs"
$script:ConfigPath = "$script:RootDir\configs\config.yaml"
$script:ProcessingRoot = "$script:DataRoot\processing"
$script:MemoryDbPath = "$script:DataRoot\memory.db"
$script:KnowledgeGraphDbPath = "$script:DataRoot\knowledge_graph.db"
$script:FaissDir = "$script:DataRoot\faiss"
$script:FaissAudioPath = "$script:FaissDir\goodq_audio.index"
$script:IssuesFound = 0
$script:IssuesAutoFixed = 0

. (Join-Path $PSScriptRoot "scripts\\_lib\\interpreter_bindings.ps1")
$script:CondaExe = Get-GoodQCondaExe
$script:CoreEnv = "goodq_core"
$script:WslDistro = Get-GoodQWslDistro

function Normalize-WinPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    return ($Path -replace '/', '\')
}

function Load-ConfigSnapshot {
    try {
        $prevPyPath = $env:PYTHONPATH
        $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($prevPyPath)) { $script:RootDir } else { "$script:RootDir;$prevPyPath" }
        Push-Location $script:RootDir

        # NOTE: Use single quotes inside Python source so Windows PowerShell argument passing doesn't strip embedded quotes.
        $py = "from steps.common.config_loader import load_configs; import json; cfg=load_configs({}); print(json.dumps({'paths': cfg.get('paths', {}), 'qdrant': cfg.get('qdrant', {})}))"
        $raw = & $script:CondaExe run -n $script:CoreEnv --no-capture-output python -c $py 2>&1
        $exit = $LASTEXITCODE
        if ($exit -ne 0 -or $null -eq $raw -or ($raw -is [System.Array] -and $raw.Count -eq 0) -or ($raw -isnot [System.Array] -and [string]::IsNullOrWhiteSpace([string]$raw))) {
            if ($Verbose) { Write-StatusLine "Config Snapshot" "Unavailable (conda run exit=$exit)" "INFO" }
            return $null
        }

        $rawText = if ($raw -is [System.Array]) { ($raw -join "`n") } else { [string]$raw }

        # load_configs() may emit warnings; take the last non-empty line as the JSON payload.
        $lines = @($rawText -split "\r?\n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
        if (-not $lines -or $lines.Count -eq 0) { return $null }
        $json = $null
        for ($i = $lines.Count - 1; $i -ge 0; $i--) {
            $ln = $lines[$i]
            if ($ln.StartsWith("{") -and $ln.EndsWith("}")) { $json = $ln; break }
        }
        if ([string]::IsNullOrWhiteSpace($json)) {
            if ($Verbose) { Write-StatusLine "Config Snapshot" "Unavailable (no JSON payload)" "INFO" }
            return $null
        }
        return ($json | ConvertFrom-Json)
    } catch {
        if ($Verbose) { Write-StatusLine "Config Snapshot" "Unavailable ($($_.Exception.Message))" "INFO" }
        return $null
    } finally {
        Pop-Location
        $env:PYTHONPATH = $prevPyPath
    }
}

function Apply-ConfigSnapshot {
    $snap = Load-ConfigSnapshot
    if (-not $snap) { return }

    $p = $snap.paths
    if ($p) {
        if ($p.data_root) { $script:DataRoot = Normalize-WinPath $p.data_root }
        if ($p.import_inbox) { $script:InboxPath = Normalize-WinPath $p.import_inbox }
        if ($p.log_dir) { $script:LogDir = Normalize-WinPath $p.log_dir }
        if ($p.processing) { $script:ProcessingRoot = Normalize-WinPath $p.processing }
        if ($p.db_path) { $script:MemoryDbPath = Normalize-WinPath $p.db_path }
        if ($p.knowledge_graph_db) { $script:KnowledgeGraphDbPath = Normalize-WinPath $p.knowledge_graph_db }
        if ($p.faiss_dir) { $script:FaissDir = Normalize-WinPath $p.faiss_dir }
        if ($p.faiss_audio_path) { $script:FaissAudioPath = Normalize-WinPath $p.faiss_audio_path }
    }

    $q = $snap.qdrant
    if ($q -and $q.host) { $script:QdrantURL = [string]$q.host }
    if ($q -and $q.collections) { $script:QdrantCollections = $q.collections }

    # Propagate bindings as env vars (read-only hints; best-effort).
    $env:GOODQ_WSL_DISTRO = $script:WslDistro
    if ($script:MemoryDbPath) { $env:GOODQ_DB_PATH = $script:MemoryDbPath }
    if ($script:KnowledgeGraphDbPath) { $env:GOODQ_KG_DB_PATH = $script:KnowledgeGraphDbPath }
    if ($script:ProcessingRoot) { $env:GOODQ_PROCESSING_ROOT = $script:ProcessingRoot }
    if ($script:FaissDir) { $env:GOODQ_FAISS_DIR = $script:FaissDir }
    if ($script:FaissAudioPath) { $env:GOODQ_FAISS_AUDIO_PATH = $script:FaissAudioPath }
    if ($script:QdrantURL) { $env:GOODQ_QDRANT_URL = $script:QdrantURL }
    if ($script:QdrantCollections) {
        if ($script:QdrantCollections.clip) { $env:GOODQ_QDRANT_COLLECTION_CLIP = [string]$script:QdrantCollections.clip }
        if ($script:QdrantCollections.dino) { $env:GOODQ_QDRANT_COLLECTION_DINO = [string]$script:QdrantCollections.dino }
        if ($script:QdrantCollections.text) { $env:GOODQ_QDRANT_COLLECTION_TEXT = [string]$script:QdrantCollections.text }
        if ($script:QdrantCollections.audio) { $env:GOODQ_QDRANT_COLLECTION_AUDIO = [string]$script:QdrantCollections.audio }
    }

    if ($Verbose) { Write-StatusLine "Config Snapshot" "Applied (processing=$script:ProcessingRoot)" "SUCCESS" }
}

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
        $pyVersion = & $script:CondaExe run -n $script:CoreEnv python --version 2>&1
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
        $pipVersion = & $script:CondaExe run -n $script:CoreEnv python -m pip --version 2>&1
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
    
    $processingDir = if ($script:ProcessingRoot) { $script:ProcessingRoot } else { "$script:DataRoot\\processing" }
    $faissDir = if ($script:FaissDir) { $script:FaissDir } else { "$script:DataRoot\\faiss" }
    $dbDir = if ($script:MemoryDbPath) { Split-Path $script:MemoryDbPath -Parent } else { $script:DataRoot }

    $criticalDirs = @(
        $script:DataRoot,
        $script:InboxPath,
        $processingDir,
        "$script:DataRoot\processed",
        $faissDir,
        $dbDir,
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

function Start-IngestionService {
    Write-Host "  Starting ingestion pipeline..." -ForegroundColor $Cyan
    
    if (!$StartIngestion) {
        Write-StatusLine "Ingestion" "Not started (safe mode; pass -StartIngestion to run)" "INFO"
        return
    }

    if (!$DryRun) {
        # Build ingestion command with optional force flag
        $ingestCmd = "& `"$script:CondaExe`" run -n $script:CoreEnv --no-capture-output python -m cli.run_ingestion --input-dir `"$script:InboxPath`" --verbose"
        if ($ForceReprocess) {
            $ingestCmd += " --force"
        }
        
        Start-Process powershell -ArgumentList @(
            "-NoExit",
            "-Command",
            "cd '$script:RootDir'; `$host.UI.RawUI.WindowTitle='GoodQ4All - Ingestion Monitor'; $ingestCmd"
        )
        
        Write-StatusLine "Ingestion" "Launched - processing from $script:InboxPath" "SUCCESS"
    } else {
        Write-StatusLine "Ingestion" "Skipped (dry run)" "INFO"
    }
}

# ==================== MAIN EXECUTION ====================

function Main {
    try { Clear-Host } catch { }
    
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

    # Bind runtime paths/collections from canonical config (best-effort) and propagate as env vars.
    Apply-ConfigSnapshot

    # Optional explicit env overrides (if set, prefer env over config for this launcher run).
    if ($env:GOODQ_WSL_DISTRO) { $script:WslDistro = $env:GOODQ_WSL_DISTRO }
    if ($env:GOODQ_DB_PATH) { $script:MemoryDbPath = Normalize-WinPath $env:GOODQ_DB_PATH }
    if ($env:GOODQ_KG_DB_PATH) { $script:KnowledgeGraphDbPath = Normalize-WinPath $env:GOODQ_KG_DB_PATH }
    if ($env:GOODQ_PROCESSING_ROOT) { $script:ProcessingRoot = Normalize-WinPath $env:GOODQ_PROCESSING_ROOT }
    if ($env:GOODQ_FAISS_DIR) { $script:FaissDir = Normalize-WinPath $env:GOODQ_FAISS_DIR }
    if ($env:GOODQ_FAISS_AUDIO_PATH) { $script:FaissAudioPath = Normalize-WinPath $env:GOODQ_FAISS_AUDIO_PATH }
    if ($env:GOODQ_QDRANT_URL) { $script:QdrantURL = $env:GOODQ_QDRANT_URL }

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
    Start-IngestionService
    
    # SUMMARY
    Write-Header "GOODQ4ALL IS RUNNING"
    
    Write-Host "  Qdrant API:    $script:QdrantURL" -ForegroundColor $Cyan
    Write-Host "  Inbox Path:    $script:InboxPath" -ForegroundColor $Cyan
    Write-Host "  Processing:    $script:ProcessingRoot" -ForegroundColor $Cyan
    Write-Host "  Memory DB:     $script:MemoryDbPath" -ForegroundColor $Cyan
    Write-Host "  FAISS Audio:   $script:FaissAudioPath" -ForegroundColor $Cyan
    if ($script:QdrantCollections) {
        Write-Host "  Collections:   clip=$($script:QdrantCollections.clip) dino=$($script:QdrantCollections.dino) text=$($script:QdrantCollections.text) audio=$($script:QdrantCollections.audio)" -ForegroundColor $Cyan
    }
    Write-Host "  Logs:          $script:LogDir" -ForegroundColor $Cyan
    Write-Host ""
    if ($StartIngestion -and -not $DryRun) {
        Write-Host "  Ingestion started: watch the 'Ingestion Monitor' window for live progress" -ForegroundColor $Green
    } else {
        Write-Host "  Ingestion not started (safe mode). Start explicitly with -StartIngestion." -ForegroundColor $Yellow
    }
    Write-Host ""
    
    if (!$DryRun) {
        Read-Host "Press Enter to close this window"
    }
}

# RUN
Main
