<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-26 -->

# Pipeline Restoration Backlog

This document tracks recovered design intent and currently missing cutovers for the GoodQ4All multimodal pipeline.

It is intentionally narrow:

- restore only behavior already evidenced in repo history, current code, or validated witness runs
- preserve current canonical ingest until replacement paths are proven in shadow mode
- do not introduce new architecture during restoration

## Scope

This backlog covers four connected seams:

1. phased segmentation engine activation
2. WSL unified audio runtime contract
3. phase-aware scene alignment and temporal fusion
4. version and documentation drift that obscures the intended pipeline

## Guardrails

- `cli/run_ingestion.py` remains canonical until explicit cutover.
- `GPU_ENHANCED` and `BASELINE` must both stay truthful and runnable.
- WSL remains a compute extension, not the source of truth.
- Shadow artifacts remain comparison-only unless promoted explicitly.
- Every restoration step must preserve observability.

## Recovered Design Truths

### 1. Per-step architecture is intentional and must stay

Preserve:

- isolated step environments
- explicit GPU budgeting
- downstream steps enriching prior outputs instead of recomputing everything
- modular observability and step-level failure reporting

Evidence:

- `docs/archive/reports/GPU_CONFIGURATION_REPORT.md`
- `docs/archive/reports/VISION_GPU_OPTIMIZATION_REPORT.md`
- `docs/archive/releases/GPU_AND_PROCESS_CONTROL_SUMMARY.md`
- `docs/archive/archived_docs/POLISH_SUMMARY.md`

### 2. The phased segmentation engine was intended as an upstream backbone

Preserve:

- `SEG_P0` normalization
- `SEG_P1` VAD segmentation
- `SEG_P2` pyannote refinement
- `SEG_P3` smart chunk building
- `SEG_P4` heavy audio enrichment
- `SEG_P5` chunk-aware scene alignment
- `SEG_P6` final integration

Evidence:

- `docs/archive/reports/PHASED_SEGMENTATION_ENGINE_IMPLEMENTATION_REPORT.md`
- `docs/archive/reports/session_summaries/PR_SUMMARY.md`
- `docs/archive/reports/phase_reports/PHASE_9_FINAL_STATUS_REPORT.md`
- `docs/technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md`
- `docs/technical/SESSION_SUMMARY_2025-12-05.md`

### 3. WSL unified audio was intended to be WSL-first with Windows fallback

Preserve:

- one unified WSL worker for heavy audio
- clean structured JSON output
- transcription-first behavior
- Windows fallback when WSL is degraded
- `HF_TOKEN` env-first token handling

Evidence:

- `docs/guides/wsl2/PIPELINE_UPGRADE.md`
- `docs/guides/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md`
- `docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md`
- `docs/archive/reports/WSL2_AUDIO_SUMMARY.md`
- `docs/archive/releases/RELEASE_NOTES_v1.4.0.md`

### 4. The stable GPU matrix is conservative, not bleeding-edge

Preserve:

- Windows `torch 2.5.1 / torchvision 0.20.1 / torchaudio 2.5.1 / cu121`
- WSL unified audio on the same conservative `2.5.1+cu121` lane

Evidence:

- `docs/archive/reports/GOODCUBE_STAGE6_WSL_PYTORCH_REPORT.md`
- `snapshots/canonical_windows_wsl_20260228_220227/wsl_pip_freeze.txt`
- `snapshots/canonical_windows_wsl_20260228_220227/conda_env_list.txt`

## Already Restored

### A. Shadow segmentation path is runnable again

Current state:

- `SEG_P0` to `SEG_P6` shadow execution is restored in isolation
- shadow artifacts are contract-frozen
- shadow metrics exist for comparison
- shadow audio can overlay live Phase 6 audio inputs without changing scene authority

Primary implementation:

- `docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`
- `steps/audio/segmentation/orchestrator.py`
- `cli/run_ingestion.py`

### B. WSL runtime truth is reconnected

Current state:

- `process_audio.py` is config-driven again
- WSL bridge surfaces processor error detail on nonzero exit
- preflight exposes readiness states instead of a single fuzzy result
- bootstrap and doctor now reflect those richer states

Primary implementation:

- `wsl2_audio/process_audio.py`
- `scripts/wsl2_audio_bridge.py`
- `scripts/wsl_audio_preflight.py`
- `scripts/bootstrap_verify.py`
- `cli/goodq_doctor.py`

### C. Reference docs are being de-drifted

Current state:

- active `docs/reference` content is being cleaned to remove dead flags, dead commands, and dead links
- current WSL runtime truth now has a dedicated reference page

Primary implementation:

- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/reference/PLATFORM_SUPPORT.md`
- `docs/reference/indexes/ENVIRONMENT_INDEX.md`

## Not Yet Implemented

### P0. Authoritative phased segmentation cutover

Current state:

- `cli/run_ingestion.py` supports `segmentation.activation=shadow`
- `cli/run_ingestion.py` still rejects authoritative mode with `segmentation_authoritative_not_enabled`

Needed:

1. promote shadow outputs into an authoritative ingest path behind an explicit flag
2. preserve rollback to current scene-first ingest
3. keep metrics and comparison surfaces available during cutover

### P0. Phase 5 scene comparison and decision

Current state:

- `video_scene_segmentation` is still registered in `cli/step_runner.py`
- current canonical ingest still uses the live scene path rather than `SEG_P5` as authority

Needed:

1. run `SEG_P5` scene alignment in shadow against the current scene backend
2. compare scene counts, transcript-bearing scenes, speaker coverage, and alignment quality
3. cut over only if the chunk-aware path wins on witness runs

### P0. True `SEG_P6` temporal index promotion

Current state:

- shadow artifacts stop short of a true authoritative `temporal_index.json`
- current live Phase 6 remains the authoritative fusion layer

Needed:

1. define the promotion boundary from shadow `metadata/segmentation.json` into live temporal fusion
2. produce a true shadow temporal index for side-by-side comparison
3. promote only after artifact parity and completeness checks pass

### P1. WSL version contract unification

Current state:

- preflight recommends `2.5.1+cu121`
- `wsl2_audio/setup_wsl2_audio.sh` still installs unpinned `torch torchvision torchaudio`
- `wsl2_audio/requirements-locked.txt` still reflects a `2.8.0` lane
- `scripts/install_pipeline_wsl.py` still reflects an older `2.3.1+cu121` lane

Needed:

1. choose one canonical WSL matrix
2. align installer, lockfile, setup script, and preflight
3. revalidate WSL transcription and optional diarization on that single matrix

### P1. Legacy Windows diarization quarantine or alignment

Current state:

- `steps/audio_diarize/step.py` still carries stale model defaults such as `pyannote/speaker-diarization@2.1`
- that path is not canonical, but it remains a drift risk

Needed:

1. either align the legacy lane to the model registry and current compatibility story
2. or explicitly quarantine it from active operator surfaces

### P1. WSL service-era intelligence reconciliation

Current state:

- `wsl2_audio/audio_service.py` still preserves richer service-era logic
- `wsl2_audio/process_audio.py` is the canonical runtime worker

Needed:

1. keep only the service-era behaviors that are still evidenced and useful
2. avoid reviving the old queue/service architecture as a second competing runtime
3. treat the service-era code as reference logic unless explicitly promoted

## Drift To Quarantine

Do not restore blindly:

- `GOODQ_ENABLE_GPU`
- `GOODQ_ENABLE_WSL_AUDIO`
- `torch 2.9.1 + CUDA 12.8` WSL guidance
- invalid diarization model id `pyannote/speaker-diarization@2.1`
- stale quick refs that depend on `conda activate`
- dead artifact locations under legacy `logs/scene_ingest`

## Evidence Search Targets Still Worth Hunting

Best remaining historical targets:

1. any snapshot containing `pipelines/ingest_multimodal_conda.py`
2. any snapshot containing `configs/segmentation_config.json`
3. any run bundle containing all of:
   - `audio/segmentation.json`
   - `metadata/segmentation_enhanced.json`
   - `video/scene_manifest.json`
   - `temporal_index.json`
4. anything tied to commit `246e97d`

## Working Priority Order

1. authoritative segmentation activation in `cli/run_ingestion.py`
2. `SEG_P5` scene shadow comparison
3. true shadow temporal-index comparison
4. WSL matrix unification
5. legacy diarization quarantine or alignment
6. final documentation cleanup after runtime cutovers are settled

## Definition Of Done

The restoration work is complete when all of the following are true:

- canonical ingest can run with phased segmentation as an authoritative upstream path
- WSL audio remains WSL-first with truthful Windows fallback
- chunk-aware scene alignment has been either promoted or explicitly rejected based on witness metrics
- `temporal_index.json` is produced from the restored contract, not from disconnected shadow-only artifacts
- operator docs describe the live system rather than a mixture of live and historical contracts
