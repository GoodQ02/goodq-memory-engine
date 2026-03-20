# GoodQ Quick Reference Card

**Version 1.2.0** | **Last Updated:** October 6, 2025

---

## 🚀 Essential Commands

### Launch GoodQ
```powershell
# ONE-CLICK: Double-click the launcher
LAUNCH_GOODQ.bat

# Command Center only (no API)
LAUNCH_GOODQ_SIMPLE.bat

# PowerShell with options
pwsh scripts/launch_goodq_full.ps1 -HealthCheckFirst

# Stop all services
STOP_GOODQ.bat
# OR
pwsh scripts/stop_goodq_services.ps1
```

### Health & Status
```powershell
# Full health check
pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq

# System readiness
python scripts/system_readiness_check.py

# Cache validation
python scripts/cache_readiness_check.py

# Environment audit
pwsh scripts/audit_env.ps1

# Index reconciliation
pwsh scripts/reconcile_indices.ps1
```

### Ingestion
```powershell
# Quick test (1 video, 2 scenes)
pwsh scripts/ingest_videos_lite.ps1 -InputDir samples/ingestion -VerboseSteps

# Custom limits
pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -MaxVideos 3 -MaxScenes 5

# Full ingestion (no limits)
python cli/run_ingestion.py --input-dir "<GOODQ_DATA_ROOT>/videos" --workspace logs/full_run --verbose

# Mission launch (full stack)
pwsh scripts/mission_launch.ps1 -Mode pipeline
```

### Monitoring
```powershell
# System snapshot
python -m cli.system_status

# Watchdog / inbox status
python scripts/utils/check_watchdog_status.py

# View recent logs
Get-Content <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl -Tail 50

# Find errors
Get-Content <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl | Select-String '"status":"error"'

# Performance analysis
Get-Content <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl -Tail 1000 | 
    ForEach-Object { $_ | ConvertFrom-Json } | 
    Group-Object step | 
    ForEach-Object { 
        [PSCustomObject]@{
            Step = $_.Name
            AvgMS = ($_.Group | Measure-Object duration_ms -Average).Average
            Count = $_.Count
        }
    } | Sort-Object AvgMS -Descending
```

### Environment Management
```powershell
# List environments
conda env list | Select-String "goodq"

# Recreate environment
pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -Steps <step> -LinkProject

# Lock environments
pwsh scripts/lock_envs.ps1

# Verify locks
pwsh scripts/lock_envs.ps1 -Verify

# Enable CUDA
pwsh scripts/enable_cuda.ps1 -Env goodq_<step>
```

---

## 📁 Key File Locations

| Item | Path |
|------|------|
| **Config** | `<project_root>/configs/config_open.yaml` |
| **Logs** | `<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl` |
| **Database** | `<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/memory.db` |
| **FAISS Indices** | `<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/*.index` |
| **Models** | `<GOODQ_DATA_ROOT>/models/` |
| **Lock Files** | `<project_root>/envs/locks/*.lock.txt` |
| **Scripts** | `<project_root>/scripts/` |

---

## 🗄️ Database Queries

### SQLite
```powershell
sqlite3 <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/memory.db
```

```sql
-- Count scenes
SELECT COUNT(*) FROM scenes;

-- Recent videos
SELECT video_hash, COUNT(*) as scenes, MIN(created_at) as first_seen
FROM scenes GROUP BY video_hash ORDER BY first_seen DESC LIMIT 10;

-- Processing status
SELECT status, COUNT(*) FROM scene_bundles GROUP BY status;
```

### FAISS Search (Python)
```python
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

index = faiss.read_index("<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/faiss_text.index")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

query = "find scenes with dogs"
query_vec = model.encode([query]).astype('float32')
distances, indices = index.search(query_vec, k=10)
```

---

## ⚙️ Environment Variables

```powershell
# Core paths
$env:HF_HOME = "<GOODQ_DATA_ROOT>/models"
$env:TORCH_HOME = "<GOODQ_DATA_ROOT>/models"
$env:HF_HUB_ENABLE_HF_TRANSFER = "1"

# Auth tokens
$env:PYANNOTE_TOKEN = "hf_..."
$env:HF_TOKEN = "hf_..."
$env:OPENAI_API_KEY = "sk-..." # Optional

# Set persistently
pwsh scripts/set_env_vars.ps1 -Vars @{HF_HOME="<GOODQ_DATA_ROOT>/models"} -Persist
```

---

## 🔧 Troubleshooting

### Environment not found
```powershell
pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -Steps <missing> -LinkProject
```

### CUDA out of memory
```powershell
pwsh scripts/ingest_videos_lite.ps1 -MaxScenes 1
# OR
python -c "import torch; torch.cuda.empty_cache()"
```

### PyAnnote auth error
```powershell
$env:PYANNOTE_TOKEN = "hf_your_token"
pwsh scripts/set_env_vars.ps1 -Vars @{PYANNOTE_TOKEN="hf_..."} -Persist
```

### Slow performance
```powershell
# Check for deduplication
Get-Content <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl -Tail 100 | Select-String "skipped"

# Reconcile indices
pwsh scripts/reconcile_indices.ps1
```

---

## 📊 Performance Metrics

| Metric | First Run | With Dedupe | Improvement |
|--------|-----------|-------------|-------------|
| **Duration** | 158s | 38s | 76% faster |
| **Steps** | 60 | 35 | 25 skipped |
| **GPU Use** | 85% | 45% | Reduced |

---

## 🎯 Quick Workflows

### Daily Processing
```powershell
1. pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq
2. Copy videos to <project_root>/import_inbox
3. pwsh scripts/ingest_videos_lite.ps1 -InputDir import_inbox -VerboseSteps
4. python -m cli.system_status
5. Move processed videos to archive
```

### Weekly Maintenance
```powershell
# Clean old logs
Get-ChildItem <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/*.jsonl | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
    Remove-Item

# Verify environments
pwsh scripts/audit_env.ps1

# Reconcile indices
pwsh scripts/reconcile_indices.ps1
```

### Monthly Backup
```powershell
$date = Get-Date -Format "yyyy-MM-dd"
$backup = "<GOODQ_DATA_ROOT>/backups/GoodQ/$date"
New-Item -ItemType Directory -Path $backup -Force

Copy-Item <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/*.db $backup/
Copy-Item <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/*.index $backup/
Copy-Item <GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/data/memory_db/*.sqlite $backup/

Write-Host "Backup complete: $backup"
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [User Guide](../../guides/general/USER_GUIDE.md) | Getting started & usage |
| [Architecture](../../architecture/SYSTEM_ARCHITECTURE.md) | Technical deep dive |
| [Diagrams](../../architecture/diagrams/PIPELINE_FLOW.md) | Visual reference |
| [History](../../archive/PROJECT_HISTORY.md) | Project timeline |
| [Lock Files](../../../envs/locks/README.md) | Environment management |

---

## 🆘 Getting Help

**Common Issues:**
1. Check [User Guide Troubleshooting](../../guides/general/USER_GUIDE.md#troubleshooting)
2. Review [Project History](../../archive/PROJECT_HISTORY.md) for context
3. Check logs: `<GOODQ_DATA_ROOT>/GoodQ_Data (See LEGACY_PATHS_DEPRECATED.md)/logs/step_runs.jsonl`
4. Run diagnostics: `pwsh scripts/mission_health_check.ps1`

**Generate Diagnostic Bundle:**
```powershell
pwsh scripts/run_full_dry_run.ps1
# Creates export in logs/run_exports/<timestamp>
```

---

*Quick Reference - Version 1.2.0 - October 6, 2025*
