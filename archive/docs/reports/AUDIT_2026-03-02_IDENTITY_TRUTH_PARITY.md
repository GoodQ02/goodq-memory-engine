# Audit Change Report — Identity, Truth, and Scene Parity

Date: 2026-03-02  
Scope: Canonical `video_id` semantics, harmonizer truth-source alignment, deterministic scene-level vector parity.

## Commit Set

1. `7a49f45` — `fix(identity): canonicalize video_id across kg and scene vector payloads`
2. `bcb4d37` — `fix(harmonizer): align modality payloads with commit-event truth`
3. `2bc9210` — `fix(ingest): propagate canonical video_id and enforce scene parity determinism`

## Why These Changes Were Made

- Identity drift risk existed across layers (`video_hash`, stem-based IDs, and mixed payload semantics).
- Harmonizer could emit modality booleans from commit truth while still materializing artifact-derived transcript/audio payloads.
- Scene-level parity had a determinism seam where attempted writes could degrade to non-boolean/null-like outcomes in downstream artifacts.

## What Was Changed

### 1) Canonical Identity Semantics

- Enforced canonical semantic `video_id` (hash-based) across:
  - KG scene updates
  - scene bundle vector payloads
  - Phase 6 scene embedding orchestration and return payloads
- Preserved compatibility aliases where required (for existing consumers still reading `video_hash`).

### 2) Harmonizer Truth Consolidation

- Set commit-event truth as authoritative for audio/transcript modality presence when available.
- If commit truth indicates not committed, suppresses scene transcript/audio payload materialization for that scene.
- Emits explicit warnings when artifact presence conflicts with commit truth.
- Prevents split-brain truth states in temporal index segments.

### 3) Scene-Level Parity Determinism

- Added deterministic resolver for scene store statuses:
  - If `vector_points_attempted == 0`: status = `"not_attempted"`
  - If `vector_points_attempted > 0`: status must be boolean (`true`/`false`)
- Persisted scene-level parity fields into `scene_manifest` handoff:
  - `vector_points_attempted`
  - `qdrant_ok`
  - `faiss_ok`

## Verification Evidence (Redacted/Safe)

- Python syntax check:
  - `python -m py_compile` succeeded for modified modules.
- Focused unit test slice:
  - `tests/unit/test_phase6_audio_artifact_path_unified.py`
  - `tests/unit/test_phase6_truth_invariant.py`
  - `tests/unit/test_vector_parity_artifact_persistence.py`
  - Result: `3 passed`

## Operational Notes

- No dependency upgrades.
- No architectural refactor.
- No fallback routing changes.
- No secret-bearing artifacts added.

