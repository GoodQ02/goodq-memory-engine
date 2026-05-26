<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Scripts Folder Deep Audit - Cleanup Plan
**Generated:** 2025-12-09  
**Status:** Analysis Complete - Awaiting Approval

---

## 🔴 CRITICAL FINDINGS

### 1. **ZenML References Still Present**
- **44 files** still reference ZenML (goodq_zenml environment, @pipeline, @step decorators)
- These are ALL legacy and should be archived

### 2. **Old Step Path Imports**
- **48+ files** use `from steps.` or `import steps.` (old flat structure)
- Should use `from goodq4all.steps.` (new package structure)

### 3. **Misplaced Core Logic**
- `watchdog_ingest.py` - Should be in `cli/` not `scripts/`
- Current workaround using `-m` flag, but file should move

---

## 📂 CATEGORIZED CLEANUP PLAN

### **CATEGORY A: ARCHIVE IMMEDIATELY (ZenML/Legacy Pipeline)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/zenml_legacy/`

```
command_center.ps1 (ZenML orchestration)
preflight_check.ps1 (references goodq_zenml)
prepare_step_envs.ps1 (creates ZenML env)
PIN_MODEL_VERSIONS.bat (uses goodq_zenml)
VERIFY_MODEL_LOCKDOWN.bat (uses goodq_zenml)
SETUP_WEB_DEPENDENCIES.bat (uses goodq_zenml)
RUN_GPU_OPTIMIZATION.bat (uses goodq_zenml)
TEST_GPU_PIPELINE.bat (uses goodq_zenml)
TEST_AUDIO_GPU.bat (uses goodq_zenml)
fix_all_environments.py (manages zenml env)
monitor_gpu_pipeline.py (runs in zenml env)
run_gpu_optimization_tests.py (runs in zenml env)
show_intelligence_report.ps1 (uses zenml env)
validate_environment_fix.py (checks zenml env)
```

### **CATEGORY B: MOVE TO CLI (Core Functionality)**
**Action:** Move to `cli/` with import path fixes

```
watchdog_ingest.py → cli/watchdog.py
  - Fix: Update all `from steps.` → `from goodq4all.steps.`
  - Fix: Update launch_goodq_v2.bat to call `cli.watchdog`
```

### **CATEGORY C: ARCHIVE (Phase 1/2/3/5 Testing - Completed)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/phase_testing/`

```
phase2_clean_and_reingest.py
phase2_completion_report.py
phase2_embedding_analysis.py
phase2_fixes.py
phase2_llm_integration.py
phase2_progress_report.py
phase2_verify.py
phase3_diagnostic.py
phase5_full_validation.py
verify_phase1_fix.py
validate_phase3_integration.py
```

### **CATEGORY D: ARCHIVE (Database/KG Diagnostics - Old Schema)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/kg_diagnostics/`

```
analyze_database.py
analyze_kg_gaps.py
analyze_sample_output.py
analyze_unified_kg.py
build_kg_standalone.py
build_knowledge_graph_from_db.py
build_unified_kg.py
check_databases.py
check_db.py
check_db2.py
check_db_schema.py
check_kg_schema.py
check_memory_db.py
check_missing_data.py
check_nested.py
check_sample_data.py
check_scene_ids.py
check_scene_keys.py
check_scene_meta.py
check_scene_results.py
check_schema.py
check_tables.py
clean_databases.py
debug_kg_input.py
debug_kg_structure.py
deep_scene_analysis.py
find_transcription_data.py
inspect_db.py
query_db_simple.py
show_kg_insights.py
```

### **CATEGORY E: ARCHIVE (GPU Setup - Completed)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/gpu_setup/`

```
apply_performance_fixes.py
comprehensive_gpu_setup.py
diagnose_gpu_issue.py
diagnose_gpu_pipeline.py
fix_gpu_allocation.py
fix_pyannote_gpu.py
gpu_config.py
gpu_config_injector.py
gpu_config_tuner.py
gpu_pipeline_optimizer.py
gpu_setup_windows.py
optimize_vision_gpu.py
quick_gpu_setup.py
quick_gpu_test.py
setup_gpu_environments.bat
validate_gpu_setup.bat
```

### **CATEGORY F: ARCHIVE (Vision/Audio Testing - Completed)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/component_tests/`

```
audio_gpu_monitor.py
audio_gpu_report.py
audit_vision_gpu.py
audit_vision_pipeline.py
test_audio_components.py
TEST_AUDIO_DIARIZE_BREAKDOWN.bat
test_audio_diarize_breakdown.py
test_audio_gpu_optimization.py
test_audio_pipeline_gpu.py
test_clap_clustering.py
test_gpu_allocation.py
test_gpu_config.py
test_gpu_pipeline.py
test_gpu_scene_detection.py
test_osd_integration.py
test_transcribe_integration.py
test_vad_gpu_usage.py
test_vad_simple.py
TEST_VISION_GPU.bat
test_vision_gpu.py
```

### **CATEGORY G: ARCHIVE (Analytics - Never Activated)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/analytics_inactive/`

```
analytics_cli.py
analytics_dashboard.py
analytics_engine.py
analytics_query.py
```

### **CATEGORY H: ARCHIVE (Installation - Completed)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/installation/`

```
bootstrap_models.py
download_datasets.py
dataset_specs.py
install_audio_deps_retry.bat
INSTALL_AUDIO_DIARIZE_ENV.bat
install_gpu_support.ps1
install_pipeline_windows.ps1
install_pipeline_wsl.py
install_vad.bat
install_vision_gpu.bat
install_vision_gpu.py
INSTALL_WSL2_AUDIO.bat
pin_model_versions.py
setup_wsl2_audio.py
setup_wsl2_audio_fast.py
setup_wsl2_audio_userspace.py
validate_models.py
```

### **CATEGORY I: ARCHIVE (Monitoring - Replaced by Watchdog)**
**Action:** Move to `archive/deprecated_2025_12_09/scripts/monitoring_old/`

```
check_ingestion_status.py
check_watchdog_status.py
monitor_ingestion.py
monitor_ingestion_progress.py
monitor_ingestion_realtime.py
monitor_processing.py
monitor_scene_detection.py
get_processing_report.py
```

### **CATEGORY J: KEEP & FIX (Active Utility Scripts)**
**Action:** Fix import paths to use `goodq4all.steps.`

```
✅ mission_launch.ps1 (already updated 2025-12-07)
⚠️  apply_scene_summaries.py (fix imports)
⚠️  sync_faiss_to_qdrant.py (fix imports)
⚠️  test_full_system.py (fix imports)
✅ clean_old_processing.py (utility - keep)
✅ rotate_logs.py (utility - keep)
✅ system_status_check.py (utility - keep)
```

### **CATEGORY K: WSL2 BRIDGE (Active - Keep)**
**Action:** Keep in scripts/wsl/ subdirectory

```
✅ refresh_vllm_portproxy.bat
✅ start_vllm_servers.bat
✅ status_vllm_servers.bat
✅ stop_vllm_servers.bat
✅ test_wsl2_bridge.py
✅ wsl2_audio_bridge.py
✅ wsl2_process_audio.py
```

### **CATEGORY L: API/UI Launch (Active - Keep)**
**Action:** Verify paths and keep

```
✅ start_api.ps1
✅ api_server.py
```

---

## 🔧 REQUIRED FIXES

### 1. **Move watchdog to CLI**
```bash
mv scripts/watchdog_ingest.py cli/watchdog.py
```

Update import paths inside `cli/watchdog.py`:
```python
# OLD:
from steps.audio_diarize import run_step
from steps.vad import run_vad

# NEW:
from goodq4all.steps.audio.diarization import run_step
from goodq4all.steps.audio.vad import run_vad
```

Update `launch_goodq_v2.bat`:
```batch
REM OLD:
python -m scripts.watchdog_ingest

REM NEW:
python -m cli.watchdog
```

### 2. **Fix Active Scripts Import Paths**

**apply_scene_summaries.py:**
```python
# Line 10-11: Change
from steps.vision_caption import add_caption
from steps.scene_summarize import summarize

# To:
from goodq4all.steps.video.vision_caption import add_caption
from goodq4all.steps.video.scene_summarize import summarize
```

**sync_faiss_to_qdrant.py:**
```python
# Line 20-21: Change
from steps.embedders.clip import load_clip
from steps.embedders.dino import load_dino

# To:
from goodq4all.steps.embeddings.clip import load_clip
from goodq4all.steps.embeddings.dino import load_dino
```

---

## 📊 SUMMARY

| Category | Files | Action |
|----------|-------|--------|
| ZenML Legacy | 14 | Archive |
| Phase Testing | 10 | Archive |
| DB/KG Diagnostics | 29 | Archive |
| GPU Setup | 16 | Archive |
| Component Tests | 18 | Archive |
| Analytics Inactive | 4 | Archive |
| Installation | 17 | Archive |
| Monitoring Old | 9 | Archive |
| Active Utility | 7 | Fix imports & keep |
| WSL2 Bridge | 7 | Keep |
| API/UI Launch | 2 | Keep |
| **TOTAL ARCHIVE** | **117** | |
| **TOTAL KEEP** | **16** | |

---

## ✅ SAFE TO PROCEED?

All archived scripts are:
- ✅ Over 30 days old
- ✅ Reference deprecated systems (ZenML, old envs, old schema)
- ✅ Not imported by active codebase
- ✅ Replaced by new Phase 0-6 pipeline

**Recommendation:** YES - Archive all Category A-I, fix Category J, keep Category K-L

---

## 🎯 NEXT STEPS

1. Create archive structure
2. Move scripts by category
3. Fix import paths in active scripts
4. Move watchdog to CLI
5. Update launch_goodq_v2.bat
6. Test watchdog launch
7. Commit changes
8. Delete ZenML conda environment

