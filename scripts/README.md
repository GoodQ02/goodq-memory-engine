# GoodQ4All Scripts Directory

This directory contains the core operational scripts for GoodQ4All.

## 🚀 Launch Scripts (BAT files in root)

**Primary Launch:**
- `LAUNCH_GOODQ.bat` - Main launcher with health checks, CUDA setup, and services
- `LAUNCH_GOODQ_SIMPLE.bat` - Quick launch without full checks

**Watchdog:**
- `START_WATCHDOG.bat` - Start file monitoring service
- `MONITOR_WATCHDOG.bat` - View watchdog logs
- `CHECK_WATCHDOG.bat` - Check watchdog status

**Management:**
- `STOP_GOODQ.bat` - Stop all GoodQ services
- `RUN_HEALTH_CHECK.bat` - Run system health check

## 📋 Active Scripts

### System Management
- `prepare_step_envs.ps1` - Create/update all conda environments
- `emergency_conda_repair.ps1` - Repair broken conda environments
- `enable_cuda.ps1` - Enable CUDA in specific environments
- `lock_envs.ps1` - Lock environment dependencies
- `set_env_vars.ps1` - Set environment variables
- `sync_env_local.ps1` - Sync .env.local with system variables

### Health & Monitoring
- `mission_health_check.ps1` - Pre-flight health check
- `mission_launch.ps1` - Launch with monitoring
- `command_center.ps1` - Real-time dashboard
- `watchdog_status.ps1` - Watchdog monitoring
- `system_readiness_check.py` - Comprehensive readiness check
- `cache_readiness_check.py` - Verify model/dataset cache
- `quick_health_check.py` - Fast health check
- `monitor_overnight.py` - Monitor long-running ingestion

### Model & Data Management
- `bootstrap_models.py` - Download and verify models
- `pin_model_versions.py` - Pin model versions
- `verify_model_lockdown.py` - Verify model pins
- `dataset_specs.py` - Dataset specifications
- `download_datasets.py` - Download datasets

### Database & Memory
- `check_memory_db.py` - Inspect memory database
- `check_production_status.py` - Check production status
- `clear_databases.py` - Clear all databases
- `test_memory_context.py` - Test memory context
- `test_knowledge_graph.py` - Test knowledge graph

### Ingestion & Processing
- `watchdog_ingest.py` - File monitoring and auto-ingestion
- `file_watchdog.py` - Legacy watchdog (use watchdog_ingest.py)

### Testing & Validation
- `sanity_suite.ps1` - Quick sanity checks
- `audit_pipeline_bugs.py` - Audit pipeline for bugs
- `validate_models.py` - Validate model functionality
- `validate_models_isolated.py` - Validate in isolated envs
- `test_audio_steps.ps1` - Test audio pipeline
- `test_audio_emotion_step.ps1` - Test audio emotion step
- `quick_test_storage.py` - Test storage systems

### Utilities
- `audit_env.ps1` - Audit environment configuration
- `ci_verify.ps1` - CI verification script
- `organize_l_drive.ps1` - Organize L:\ drive structure
- `start_api.ps1` - Start FastAPI server

## 📦 Model Pinning

Run these in order to lock down models:
1. `PIN_MODEL_VERSIONS.bat` - Pin all model versions
2. `VERIFY_MODEL_LOCKDOWN.bat` - Verify pins are in place

## 🗃️ Archived Scripts

Obsolete scripts are archived in `_archive/old_scripts_*` directories.
These are kept for reference but not actively used.

## 💡 Quick Reference

**First Time Setup:**
`powershell
.\prepare_step_envs.ps1
.\PIN_MODEL_VERSIONS.bat
`

**Daily Launch:**
`bat
LAUNCH_GOODQ.bat
`

**Start Auto-Ingestion:**
`bat
START_WATCHDOG.bat
`

**Check Status:**
`bat
RUN_HEALTH_CHECK.bat
`

**Stop Everything:**
`bat
STOP_GOODQ.bat
`
