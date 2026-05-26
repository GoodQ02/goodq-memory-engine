<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-03-04 -->

# WITNESS_RUN_004 — Golden Baseline (`baseline_ingest_contract_v1`)

## Purpose
Capture the canonical determinism witness after audio runtime contract hardening and backend attribution tightening. This document designates a frozen comparison point for future runtime/library drift checks.

## Baseline Designation
- Baseline label: `baseline_ingest_contract_v1`
- Determinism verdict: `PASS`
- Source summary artifact: `logs/diagnostics/witness_f_determinism_summary_20260304_012430.json`

## Run Context
- Input video: `samples/ingestion/09. 2002 - 2003.mp4`
- Profile: `GPU_ENHANCED`
- Forced re-ingestion: enabled (`--force`)
- Scope limiter: `--max-videos 1`
- Execution mode: two consecutive runs, same session, no env/package mutation between runs

## Evidence Artifacts
- Run 1 artifact: `logs/diagnostics/witness_f_determinism_run1_20260304_012430.json`
- Run 1 log: `logs/diagnostics/witness_f_determinism_run1_20260304_012430.log`
- Run 2 artifact: `logs/diagnostics/witness_f_determinism_run2_20260304_012430.json`
- Run 2 log: `logs/diagnostics/witness_f_determinism_run2_20260304_012430.log`
- Summary verdict: `logs/diagnostics/witness_f_determinism_summary_20260304_012430.json`

## Determinism Matrix (Run 1 vs Run 2)

| Field | Run 1 | Run 2 | Match |
| --- | ---: | ---: | :---: |
| `scenes_total` | `19` | `19` | `true` |
| `transcript_scenes` | `19` | `19` | `true` |
| `text_embed_ok_scenes` | `19` | `19` | `true` |
| `audio_embed_ok_scenes` | `19` | `19` | `true` |
| `qdrant clip` | `19` | `19` | `true` |
| `qdrant dino` | `19` | `19` | `true` |
| `qdrant text` | `0` | `0` | `true` |
| `qdrant audio` | `0` | `0` | `true` |
| `audio_backend_selected` | `wsl` | `wsl` | `true` |
| `audio_backend_effective` | `wsl` | `wsl` | `true` |
| `audio_backend_downgraded` | `false` | `false` | `true` |
| `audio_backend_events_count` | `0` | `0` | `true` |

## Contract Integrity Signals
- Backend contract remained stable across both runs:
  - selected backend: `wsl`
  - effective backend: `wsl`
  - downgrade flag: `false`
  - downgrade events: none
- No divergence observed in scene counts, transcript coverage, or vector collection deltas.

## Scope and Claim Boundaries
This witness **does claim**:
- repeatable ingest determinism for the canonical sample under identical runtime conditions,
- stable selected/effective audio backend attribution under healthy WSL execution,
- stable vision/text/audio scene-level embedding success counts for this witness scenario.

This witness **does not claim**:
- cross-machine determinism,
- distributed runtime support,
- universal multimodal density for all historical collections.

## Reuse Guidance
Use `baseline_ingest_contract_v1` as the reference before and after any change touching:
- Torch/CUDA stack,
- FFmpeg/torchaudio/audio decoding,
- sentence-transformers / CLAP dependencies,
- WSL bridge configuration,
- runtime contract or backend attribution logic.
