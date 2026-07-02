# Runtime Path Authority Report

> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS

- Generated: 2026-07-02T01:39:04.527953+00:00
- Canonical authority: `steps.common.config_loader.load_configs()` -> `configs/config.yaml`
- Active runtime HIGH findings: 0
- Legacy/diagnostic MEDIUM findings: 54
- Test/docs LOW findings: 133

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
- `cli/monitor_ingestion.py`
- `cli/system_status.py`
- `steps/video/scene_visual_embeddings.py`
- `steps/video/cross_modal_harmonizer.py`
- `steps/audio_transcribe/step.py`
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
- `scripts/monitor_ingestion.py`
- `scripts/monitor_ingestion_realtime.py`
- `scripts/monitor_ingestion_progress.py`
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
| MEDIUM | Legacy and diagnostic scripts still contain historical path references | `scripts/analyze_unified_kg.py`, `scripts/apply_scene_summaries.py`, `scripts/audit_vision_pipeline.py`, `scripts/bootstrap_install.py`, `scripts/bootstrap_models.py` | No primary runtime impact, but ad hoc operator runs could still observe old roots. |
| LOW | Tests and docs still contain historical path references | `tests/agents/test_mini_agent_client.py`, `tests/e2e/test_staged_ingestion_harness.py`, `tests/integration/test_ucf_audio_logging.py`, `tests/integration/test_ucf_ingestion.py`, `tests/integration/test_ucf_multi_source.py` | Audit noise only; no production runtime impact. |

## Recommended Canonical Runtime Authority

The current safest runtime authority is `steps.common.config_loader.load_configs()` backed by `configs/config.yaml`. The active runtime entrypoints and helper modules audited here now derive data root, inbox, processing, logs, databases, watchdog paths, Qdrant storage, and final scene artifacts from that authority rather than from repo-relative or environment-derived root defaults.

## Residual Legacy Examples

- `scripts/analyze_unified_kg.py`: L:/_DATA
- `scripts/apply_scene_summaries.py`: L:/_DATA
- `scripts/audit_vision_pipeline.py`: GOODQ_DATA_ROOT
- `scripts/bootstrap_install.py`: GOODQ_DATA_ROOT
- `scripts/bootstrap_models.py`: GOODQ_DATA_ROOT
- `scripts/bootstrap_verify.py`: GOODQ_DATA_ROOT
- `scripts/build_identity_ledger.py`: L:\_DATA
- `scripts/check_qdrant.py`: L:/_DATA
- `scripts/clean_old_processing.py`: L:/_DATA
- `scripts/diagnose_gpu_issue.py`: L:/_DATA
- `scripts/diagnostics/episode_reference_eval.py`: L:/_DATA, GOODQ_DATA_ROOT
- `scripts/diagnostics/FULL_SYSTEM_AUDIT.py`: L:/_DATA, L:/goodq4all/config.yaml
- `scripts/download_datasets.py`: GOODQ_DATA_ROOT
- `scripts/extract_test_frame.py`: L:/_DATA
- `scripts/final_validation_report.py`: L:/_DATA
- `scripts/generate_goodq4all_agent_status.py`: GOODQ_DATA_ROOT
- `scripts/inspect_db.py`: L:/_DATA
- `scripts/install/LAUNCH_GOODQ.go`: GOODQ_DATA_ROOT
- `scripts/install/staged/vendor/qdrant/config.yaml`: GOODQ_DATA_ROOT
- `scripts/internal/analyze_unified_kg.py`: L:/_DATA

## Test / Docs Examples

- `tests/agents/test_mini_agent_client.py`: GOODQ_DATA_ROOT
- `tests/e2e/test_staged_ingestion_harness.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_audio_logging.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_ingestion.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_multi_source.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_regression.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_retrieval_bridge.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_retrieval_bridge_stress.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_validator.py`: GOODQ_DATA_ROOT
- `tests/integration/test_ucf_vector_integrity.py`: L:/_DATA, GOODQ_DATA_ROOT
- `tests/integration/test_ucf_visual_logging.py`: GOODQ_DATA_ROOT
- `tests/legacy/integration_harnesses/test_ingestion_verbose.py`: L:/_DATA
- `tests/legacy/integration_harnesses/test_scene_comprehensive.py`: L:/_DATA
- `tests/legacy/integration_harnesses/verify_clip.py`: L:\_DATA
- `tests/legacy/root_harnesses/test_analytics_query.py`: with open('config.yaml'
- `tests/legacy/root_harnesses/test_analytics_sample.py`: with open('config.yaml'
- `tests/legacy/root_harnesses/test_audio_diarize_optimized.py`: L:\_DATA
- `tests/legacy/root_harnesses/test_diarization_chunking.py`: L:\_DATA
- `tests/legacy/root_harnesses/test_full_pipeline_llm.py`: L:/_DATA
- `tests/legacy/root_harnesses/test_llm_integration.py`: L:/_DATA
