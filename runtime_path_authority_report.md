# Runtime Path Authority Report

- Generated: 2026-03-08T17:58:42.871570+00:00
- Canonical authority: `steps.common.config_loader.load_configs()` -> `configs/config.yaml`
- Active runtime HIGH findings: 0
- Legacy/diagnostic MEDIUM findings: 42
- Test/docs LOW findings: 357

## Runtime Path Authority Map

### Category: Canonical
- `steps/common/config_loader.py`
- `configs/config.yaml`

### Category: Secondary
- `configs/paths.py`

### Category: Active Runtime Surfaces
- `LAUNCH_GOODQ.ps1`
- `cli/run_ingestion.py`
- `cli/watchdog.py`
- `cli/graph_query.py`
- `cli/monitor_ingestion.py`
- `cli/system_status.py`
- `steps/video/scene_visual_embeddings.py`
- `steps/video/cross_modal_harmonizer.py`
- `steps/audio_emotion/step.py`
- `steps/audio_transcribe/step.py`
- `steps/audio_diarize/step.py`
- `steps/image_caption/step.py`
- `steps/object_detect/step.py`
- `steps/sentiment/step.py`
- `steps/sentiment/step_fixed.py`
- `steps/common/conda_runner.py`
- `steps/common/memory_writer.py`
- `scripts/qdrant/START_QDRANT.bat`
- `scripts/qdrant/INSTALL_QDRANT_SERVICE.bat`
- `scripts/analytics_cli.py`
- `scripts/analytics_dashboard.py`
- `scripts/analytics_query.py`
- `scripts/build_knowledge_graph_from_db.py`
- `scripts/build_kg_standalone.py`
- `scripts/build_unified_kg.py`
- `scripts/api_server.py`
- `scripts/monitor_ingestion.py`
- `scripts/monitor_ingestion_realtime.py`
- `scripts/monitor_ingestion_progress.py`
- `scripts/utils/check_ingestion_status.py`
- `scripts/utils/check_watchdog_status.py`

## Active Runtime Verification

| Status | Area | File | Detail |
|---|---|---|---|
| PASS | active_runtime | `core runtime surfaces` | No forbidden fallback tokens detected in audited active runtime files. |
| PASS | config_contract | `configs/config.yaml` | Canonical runtime path keys are present, including Qdrant and watchdog path bindings. |

## Conflict Table

| Conflict Class | Status | Notes |
|---|---|---|
| Multiple runtime root definitions in active entrypoints | CLEAR | Active entrypoints now resolve through canonical config helpers. |
| Repo-relative inbox/log/workspace defaults | CLEAR | `run_ingestion` and `watchdog` defaults were moved behind canonical config resolution. |
| Artifact duplication across workspace vs processing | CLEAR | Final scene manifests and temporal index now persist under `paths.processing`. |
| Qdrant storage outside config authority | CLEAR | Qdrant startup scripts resolve storage via canonical config. |

## Risk Assessment

| Risk Level | Issue | Example Files | Runtime Impact |
|---|---|---|---|
| LOW | Active runtime authority | `cli/run_ingestion.py`, `cli/watchdog.py`, `LAUNCH_GOODQ.ps1` | Canonical config authority is consistent across audited runtime surfaces. |
| MEDIUM | Legacy and diagnostic scripts still contain historical path references | `scripts/analyze_unified_kg.py`, `scripts/apply_scene_summaries.py`, `scripts/bootstrap_models.py`, `scripts/bootstrap_verify.py`, `scripts/clean_old_processing.py` | No primary runtime impact, but ad hoc operator runs could still observe old roots. |
| LOW | Tests and docs still contain historical path references | `tests/integration/test_ingestion_verbose.py`, `tests/integration/test_scene_comprehensive.py`, `tests/integration/verify_clip.py`, `tests/README.md`, `tests/test_analytics_query.py` | Audit noise only; no production runtime impact. |

## Recommended Canonical Runtime Authority

The current safest runtime authority is `steps.common.config_loader.load_configs()` backed by `configs/config.yaml`. The active runtime entrypoints and helper modules audited here now derive data root, inbox, processing, logs, databases, watchdog paths, Qdrant storage, and final scene artifacts from that authority rather than from repo-relative or environment-derived root defaults.

## Residual Legacy Examples

- `scripts/analyze_unified_kg.py`: L:/_DATA
- `scripts/apply_scene_summaries.py`: L:/_DATA
- `scripts/bootstrap_models.py`: GOODQ_DATA_ROOT
- `scripts/bootstrap_verify.py`: GOODQ_DATA_ROOT
- `scripts/clean_old_processing.py`: L:/_DATA
- `scripts/diagnose_gpu_issue.py`: L:/_DATA
- `scripts/diagnostics/FULL_SYSTEM_AUDIT.py`: L:/_DATA, L:/goodq4all/config.yaml
- `scripts/extract_test_frame.py`: L:/_DATA
- `scripts/final_validation_report.py`: L:/_DATA
- `scripts/inspect_db.py`: L:/_DATA
- `scripts/monitor_scene_detection.py`: L:/_DATA
- `scripts/optimize_config.py`: L:/goodq4all/config.yaml
- `scripts/phase2_completion_report.py`: L:/_DATA
- `scripts/phase2_embedding_analysis.py`: L:/_DATA
- `scripts/phase2_fixes.py`: L:/_DATA, L:/goodq4all/config.yaml
- `scripts/phase2_progress_report.py`: L:/_DATA
- `scripts/phase2_verify.py`: L:/_DATA, L:/goodq4all/config.yaml
- `scripts/phase5_full_validation.py`: L:/_DATA
- `scripts/preflight_check.ps1`: GOODQ_DATA_ROOT
- `scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat`: GOODQ_DATA_ROOT

## Test / Docs Examples

- `tests/integration/test_ingestion_verbose.py`: L:/_DATA
- `tests/integration/test_scene_comprehensive.py`: L:/_DATA
- `tests/integration/verify_clip.py`: L:\_DATA
- `tests/README.md`: L:\_DATA
- `tests/test_analytics_query.py`: with open('config.yaml'
- `tests/test_analytics_sample.py`: with open('config.yaml'
- `tests/test_audio_diarize_fix.py`: L:/goodq4all/config.yaml
- `tests/test_audio_diarize_optimized.py`: L:\_DATA
- `tests/test_diarization_chunking.py`: L:\_DATA
- `tests/test_full_pipeline_llm.py`: L:/_DATA
- `tests/test_launcher.ps1`: L:\_DATA
- `tests/test_llm_integration.py`: L:/_DATA
- `tests/test_phase2_verification.py`: L:/_DATA
- `tests/test_phase3_llm_integration.py`: L:/_DATA, with open('config.yaml'
- `tests/test_phase3_standalone.py`: L:/goodq4all/config.yaml
- `tests/test_phase4_audio.py`: L:/_DATA
- `tests/test_phase6.py`: L:/_DATA
- `tests/test_phase6_harness.py`: L:\_DATA
- `tests/test_phase7_analytics.py`: with open('config.yaml'
- `tests/test_pipeline_gpu.py`: with open("config.yaml"
