# GoodQ4All Scripts Directory

**Last Updated:** November 7, 2025  
**Total Scripts:** 34 (after Phase 1-3 cleanup)  
**Purpose:** Core utility and infrastructure scripts

---

## Quick Reference

### Daily Operations
```batch
# Launch system
LAUNCH_GOODQ.bat

# Start auto-processing
START_WATCHDOG.bat

# Check status
CHECK_STATUS.bat

# Monitor progress
MONITOR_PROGRESS.bat

# View intelligence
SHOW_INTELLIGENCE.bat
```

### Health Checks
```bash
# System readiness
python scripts/system_readiness_check.py

# Model cache validation
python scripts/cache_readiness_check.py

# Database health
python scripts/check_memory_db.py
```

---

## Script Inventory

### Core Infrastructure (9 Python scripts)

**Maintenance:**
**Maintenance:**
- `clean_old_processing.py` - Automatically cleans processing directory of stale files (48h threshold)
- `rotate_logs.py` - Archives and compresses old watchdog logs (keeps 10 newest or 30 days)
**Health & Validation:**
- `system_readiness_check.py` - Primary system health check
- `cache_readiness_check.py` - Model cache validation  
- `check_memory_db.py` - Database health

**Processing:**
- `watchdog_ingest.py` - Auto-ingestion system
- `monitor_ingestion_progress.py` - Real-time progress
- `check_watchdog_status.py` - Watchdog status

**Database:**
- `clean_databases.py` - Database maintenance
- `inspect_db.py` - Interactive DB browser
- `query_db_simple.py` - Quick SQL queries
- `check_schema.py` - Schema viewer

**Diagnosis:**
- `diagnose_transcription.py` - Transcription troubleshooting

---

### Model Management (4 scripts)

- `bootstrap_models.py` - Download all models
- `pin_model_versions.py` - Lock model versions
- `validate_models.py` - Test model functionality
- `verify_model_lockdown.py` - Verify version locks

---

### Code Quality (2 scripts)

- `audit_all_exceptions.py` - Exception handling audit
- `audit_codebase.py` - Codebase analysis

---

### Configuration (3 scripts)

- `optimize_config.py` - Performance tuning
- `apply_performance_fixes.py` - Apply optimizations
- `fix_validation_issues.py` - Fix validation errors

---

### Utilities (6 scripts)

- `dataset_specs.py` - Dataset metadata
- `download_datasets.py` - Download test data
- `check_llm_availability.py` - LLM API checks

---

### PowerShell Infrastructure (7 scripts)

**System Control:**
- `command_center.ps1` - Real-time dashboard
- `mission_launch.ps1` - Process launcher
- `preflight_check.ps1` - Pre-launch validation
- `start_api.ps1` - FastAPI launcher

**Environment:**
- `prepare_step_envs.ps1` - Environment management
- `sync_env_local.ps1` - Config synchronization

**Reporting:**
- `show_intelligence_report.ps1` - Intelligence display

---

### Batch Wrappers (2 files)

- `PIN_MODEL_VERSIONS.bat` - Pin models
- `VERIFY_MODEL_LOCKDOWN.bat` - Verify locks

---

## Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| Health | 3 | System validation |
| Monitoring | 3 | Progress tracking |
| Database | 4 | DB management |
| Models | 4 | Model management |
| Diagnosis | 1 | Troubleshooting |
| Quality | 2 | Code auditing |
| Config | 3 | Optimization |
| Infrastructure | 7 | PowerShell control |
| Utilities | 5 | Support tools |

**Total:** 32 core scripts

---

## Cleanup History

**Original:** 113 scripts (scattered, redundant)  
**Phase 1:** Archived 44 historical/duplicate scripts  
**Phase 2:** Moved 15 test scripts to tests/ directory  
**Phase 3:** Archived 13 specialized/one-time scripts  
**Current:** 42 active scripts (62.8% reduction)

**Archived Location:** `L:\_ARCHIVE\goodq4all_scripts\`

---

## Usage

### Python Scripts
```bash
cd L:\goodq4all
conda activate goodq_zenml
python scripts/<script_name>.py
```

### PowerShell Scripts
```powershell
cd L:\goodq4all
powershell scripts/<script_name>.ps1
```

### Via Wrappers (Preferred)
```batch
cd L:\goodq4all
<WRAPPER_NAME>.bat
```

---

## Related Documentation

- **Main README:** `L:\goodq4all\README.md`
- **Tests:** `L:\goodq4all\tests\README.md`
- **Audit Report:** `L:\goodq4all\docs\SCRIPT_AUDIT_REPORT_2025-11-07.md`
- **Archive Index:** `L:\_ARCHIVE\goodq4all_scripts\ARCHIVE_INDEX.md`

---

**Maintained by:** GoodQ Development Team  
**Last Cleanup:** November 7, 2025  
**Next Review:** February 1, 2026
