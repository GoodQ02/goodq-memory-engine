<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# PHASE 10.2A — DEPRECATED DIRECTORY CLEANUP PLAN
**Generated:** 2025-12-07  
**Status:** ACTION PLAN ONLY — NO FILES MODIFIED YET

---

## A. DIRECTORIES IDENTIFIED

### 1. `api\_deprecated_backup_20251118_222920\`
- **Path:** `L:\goodq4all\api\_deprecated_backup_20251118_222920`
- **Contents:** `health_status.py` (1 file)
- **Size:** Small
- **Purpose:** Backup of deprecated API health endpoint

### 2. `scripts\backup\`
- **Path:** `L:\goodq4all\scripts\backup`
- **Contents:** 9 files
  - `api_server_backup_20251109_032355.py`
  - `api_server_production.py`
  - `config.yaml.backup`
  - Multiple HTML backups (index_backup_*.html)
- **Purpose:** Historical backups from UI/API iterations

### 3. `web\backup\`
- **Path:** `L:\goodq4all\web\backup`
- **Contents:** 5 files
  - Production HTML variants
  - Legacy port configuration scripts (`.LEGACY_PORT5000`, `.LEGACY_PORT8000`)
- **Purpose:** Old web interface backups

### 4. `data\config_backups\`
- **Path:** `L:\goodq4all\data\config_backups`
- **Contents:** 4 timestamped config backups
  - `config_open.yaml.backup_20251115_201437`
  - `config_open.yaml.backup_20251115_220423`
  - `config_open.yaml.backup_20251118_080843`
  - `config_open.yaml.backup_20251118_125529`
- **Purpose:** Historical config snapshots

### 5. `pipelines\ingest_multimodal.py`
- **Path:** `L:\goodq4all\pipelines\ingest_multimodal.py`
- **Status:** DEPRECATED (marked in file header)
- **Contents:** Legacy ZenML scaffold - PLACEHOLDER CODE ONLY
- **Size:** 2,427 bytes
- **Last Modified:** 11/19/2025

### 6. `pipelines\ingest_multimodal_conda.py`
- **Path:** `L:\goodq4all\pipelines\ingest_multimodal_conda.py`
- **Status:** DEPRECATED (ZenML removed)
- **Contents:** Former ZenML pipeline - NOW SUPERSEDED by `direct_ingestion.py`
- **Size:** 6,529 bytes
- **Last Modified:** 12/06/2025

### 7. `pipelines\ingest_multimodal_conda.py.backup_20251204`
- **Path:** `L:\goodq4all\pipelines\ingest_multimodal_conda.py.backup_20251204`
- **Status:** Backup file
- **Size:** 6,382 bytes

### 8. Scattered `.backup*` Files (27 files total)
- Spread across: configs/, logs/, steps/*, docs/archive/
- **Naming patterns:**
  - `*.backup_pre_gpu_refactor`
  - `*.backup_pre_vad`
  - `*.backup_before_chunking`
  - `*.backup_YYYYMMDD_HHMMSS`

---

## B. REFERENCE ANALYSIS

### 1. `api\_deprecated_backup_*`
- ✅ **No active imports found**
- ✅ **No config references**
- ✅ **Safe to archive**

### 2. `scripts\backup\`
- ✅ **No active imports**
- ⚠️ Referenced in documentation files (historical context only)
- ✅ **Safe to archive**

### 3. `web\backup\`
- ✅ **No active imports**
- ✅ **UI now served from `ui/` directory**
- ✅ **Safe to archive**

### 4. `data\config_backups\`
- ✅ **No active usage**
- ℹ️ Referenced in cleanup scripts (for informational purposes)
- ✅ **Safe to archive**

### 5. `pipelines\ingest_multimodal.py`
- ⚠️ **Referenced in:** `scripts\mission_launch.ps1` (legacy mode)
- ⚠️ **File header explicitly marks it DEPRECATED**
- ⚠️ **Contains non-functional placeholder code**
- ⚠️ **Imports old `steps.*` modules (not `goodq4all.steps.*`)**
- 🔒 **RECOMMENDATION:** Archive, update mission_launch.ps1 to remove legacy mode

### 6. `pipelines\ingest_multimodal_conda.py`
- ⚠️ **Referenced in:** `scripts\mission_launch.ps1` (pipeline mode)
- ✅ **File header marks as DEPRECATED - ZenML removed**
- ✅ **Superseded by `pipelines/direct_ingestion.py`**
- 🔒 **RECOMMENDATION:** Archive, update mission_launch.ps1

### 7. Scattered `.backup*` files
- ✅ **No imports detected**
- ✅ **Historical snapshots only**
- ✅ **Safe to archive**

---

## C. RECOMMENDED ARCHIVE STRUCTURE

```
L:\goodq4all\archive\
├── deprecated_2025_12_07\
│   ├── api\
│   │   └── _deprecated_backup_20251118_222920\
│   ├── pipelines\
│   │   ├── ingest_multimodal.py
│   │   ├── ingest_multimodal_conda.py
│   │   └── ingest_multimodal_conda.py.backup_20251204
│   ├── web_backups\
│   │   └── (contents of web\backup\)
│   ├── script_backups\
│   │   └── (contents of scripts\backup\)
│   ├── config_backups\
│   │   └── (contents of data\config_backups\)
│   └── step_backups\
│       ├── audio_diarize\
│       ├── audio_embed_clap\
│       ├── audio_emotion\
│       └── ... (all .backup* files)
```

**Archive metadata file:** `archive/deprecated_2025_12_07/MANIFEST.md`

---

## D. REQUIRED ACTIONS (PLAN ONLY)

### Phase 1: Create Archive Structure
```powershell
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\api" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\pipelines" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\web_backups" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\script_backups" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\config_backups" -ItemType Directory
New-Item -Path "L:\goodq4all\archive\deprecated_2025_12_07\step_backups" -ItemType Directory
```

### Phase 2: Move Directories
```powershell
# API deprecated backup
Move-Item "L:\goodq4all\api\_deprecated_backup_20251118_222920" "L:\goodq4all\archive\deprecated_2025_12_07\api\"

# Pipeline deprecated files
Move-Item "L:\goodq4all\pipelines\ingest_multimodal.py" "L:\goodq4all\archive\deprecated_2025_12_07\pipelines\"
Move-Item "L:\goodq4all\pipelines\ingest_multimodal_conda.py" "L:\goodq4all\archive\deprecated_2025_12_07\pipelines\"
Move-Item "L:\goodq4all\pipelines\ingest_multimodal_conda.py.backup_20251204" "L:\goodq4all\archive\deprecated_2025_12_07\pipelines\"

# Web backups
Move-Item "L:\goodq4all\web\backup\*" "L:\goodq4all\archive\deprecated_2025_12_07\web_backups\"
Remove-Item "L:\goodq4all\web\backup" -Force

# Script backups
Move-Item "L:\goodq4all\scripts\backup\*" "L:\goodq4all\archive\deprecated_2025_12_07\script_backups\"
Remove-Item "L:\goodq4all\scripts\backup" -Force

# Config backups
Move-Item "L:\goodq4all\data\config_backups\*" "L:\goodq4all\archive\deprecated_2025_12_07\config_backups\"
Remove-Item "L:\goodq4all\data\config_backups" -Force

# Individual backup files in configs/
Move-Item "L:\goodq4all\configs\*.backup*" "L:\goodq4all\archive\deprecated_2025_12_07\config_backups\"

# Step backup files
Get-ChildItem -Path "L:\goodq4all\steps" -Recurse -Filter "*.backup*" | ForEach-Object {
    $relPath = $_.FullName.Replace("L:\goodq4all\steps\", "")
    $targetDir = Split-Path "L:\goodq4all\archive\deprecated_2025_12_07\step_backups\$relPath"
    New-Item -Path $targetDir -ItemType Directory -Force
    Move-Item $_.FullName "L:\goodq4all\archive\deprecated_2025_12_07\step_backups\$relPath"
}

# Other scattered backups
Move-Item "L:\goodq4all\logs\progress.json.backup_20251112_232715" "L:\goodq4all\archive\deprecated_2025_12_07\config_backups\"
Move-Item "L:\goodq4all\docs\archive\README.md.backup_20251204" "L:\goodq4all\archive\deprecated_2025_12_07\config_backups\"
```

### Phase 3: Update References
```powershell
# Update mission_launch.ps1 to remove deprecated pipeline modes
# (Manual review required)
```

### Phase 4: Git Operations
```powershell
cd L:\goodq4all
git add archive/deprecated_2025_12_07/
git add -u  # Stage deletions
git commit -m "chore: Archive deprecated directories and backup files (Phase 10.2A)"
```

### Phase 5: Add to .gitignore
```
# Archived deprecated code (kept locally, not for repo)
archive/deprecated_*/
```

---

## E. ITEMS NEEDING MANUAL USER CONFIRMATION

### ⚠️ HIGH PRIORITY
1. **`scripts\mission_launch.ps1`**
   - Currently references deprecated pipelines
   - Needs refactoring to use `pipelines/direct_ingestion.py`
   - **ACTION:** User must confirm mission_launch.ps1 can be updated or deprecated

2. **Pipeline transition validation**
   - Confirm all active workflows use `direct_ingestion.py`
   - Confirm no external scripts depend on old pipeline names
   - **ACTION:** Run grep across external scripts/notebooks

### ℹ️ MEDIUM PRIORITY
3. **Archive retention policy**
   - How long to keep `archive/deprecated_2025_12_07/`?
   - Should it be committed to Git or .gitignored?
   - **RECOMMENDATION:** Keep locally for 1 month, then delete

---

## F. ITEMS COMPLETELY SAFE TO REMOVE

✅ **Can be archived immediately with zero risk:**

1. `api\_deprecated_backup_20251118_222920\`
2. `scripts\backup\*`
3. `web\backup\*`
4. `data\config_backups\*`
5. All 27 scattered `.backup*` files in steps/
6. `configs\*.backup*`
7. `logs\progress.json.backup*`
8. `docs\archive\README.md.backup*`

**Total files safe to archive: 40+**

---

## G. ITEMS TO KEEP (NEVER REMOVE)

🔒 **CRITICAL - DO NOT TOUCH:**

1. `pipelines/direct_ingestion.py` ✅ ACTIVE
2. `cli/run_ingestion.py` ✅ ACTIVE
3. `steps/*` (all non-backup files) ✅ ACTIVE
4. `configs/config.yaml` ✅ ACTIVE
5. `api/main.py` and `api/routes/*` ✅ ACTIVE
6. `ui/*` ✅ ACTIVE
7. All Phase 0-6 modules ✅ ACTIVE

---

## H. RISK ASSESSMENT

### 🟢 LOW RISK (Archive safely)
- All backup files
- Deprecated API/web directories
- Config backups

### 🟡 MEDIUM RISK (Requires validation)
- `pipelines/ingest_multimodal*.py` (need to update mission_launch.ps1 first)

### 🔴 HIGH RISK (Do not modify)
- Active pipeline code
- Active step modules
- configs/config.yaml

---

## I. NEXT STEPS

1. **USER DECISION REQUIRED:**
   - Review `scripts/mission_launch.ps1` usage
   - Confirm archival of deprecated pipelines
   - Approve archive structure

2. **PHASE 10.2B EXECUTION:**
   - Once approved, execute archival plan
   - Update mission_launch.ps1
   - Commit changes
   - Update .gitignore

3. **VALIDATION:**
   - Run full ingestion test
   - Verify no import errors
   - Confirm API/UI still function

---

## J. ESTIMATED IMPACT

- **Files to archive:** 40+
- **Directories to remove:** 5
- **Disk space freed:** ~50-100 KB (minimal, mostly text files)
- **Code cleanliness improvement:** HIGH
- **Risk of breaking changes:** LOW (with proper validation)

---

**END OF PHASE 10.2A ACTION PLAN**
