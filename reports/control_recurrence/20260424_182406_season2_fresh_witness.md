# GoodQ Control Recurrence Report

- Generated at: `2026-04-28T00:32:32.503971+00:00`
- Run ID: `20260424_182406_season2_fresh_witness`
- Mode: `read_only_observability`

## Run
- Run root(s): `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness`
- Episodes: `12`
- Signals: `54`

## Recommendation
- Status: `WARN`
- Highest category: `actionable`
- Reasons:
  - highest recurrence category is actionable
  - top families at highest category: native_crash_retry:0xC0000409 (actionable, count=4), native_subprocess_crash:0xC0000409 (actionable, count=2)

## Category Counts
| Category | Families | Signals |
|---|---:|---:|
| informational | 4 | 33 |
| watch | 1 | 15 |
| actionable | 2 | 6 |
| blocking | 0 | 0 |

## Recovered / Unrecovered / Skipped Counts
| Outcome | Count |
|---|---:|
| recovered | 6 |
| unrecovered | 0 |
| skipped | 48 |
| unknown | 0 |

## Phase 6 Health
- Status: `healthy`
- Healthy: `True`
- Episodes healthy: `12` / `12`

## Qdrant Health
- Status: `healthy`
- Episodes healthy: `12` / `12`

## Top Recurrence Families
| Family | Count | Category | Operator Hints | Inspection Targets |
|---|---:|---|---|---|
| insufficient_diverse_speech | 24 | informational | Confirm this remains informational by checking speaker_voice_signature_meta and final Phase 6/Qdrant health. | speaker_voice_signature_meta; phase6_qdrant_truth; temporal_index.json segments |
| diarization_unavailable | 15 | watch | Inspect WSL audio readiness, diarization_status, diarization_error, and whether speaker_count/dominant_speaker_id persisted. | WSL audio readiness; diarization_status; diarization_error; speaker_count; dominant_speaker_id; temporal_index.json |
| no_text | 5 | informational | No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output. | temporal_index.json segments; scene_ingest_results.json modality_status; phase6_qdrant_truth |
| native_crash_retry:0xC0000409 | 4 | actionable | Inspect affected step distribution, stderr/error tails, retry/fallback outcome, and whether final scene output survived. | step_runs.jsonl affected step distribution; step_runs.jsonl error tails; run.warnings; recovery_outcome; scene_ingest_results.json; phase6_qdrant_truth |
| audio_silent | 2 | informational | No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output. | temporal_index.json segments; scene_ingest_results.json modality_status; phase6_qdrant_truth |
| native_subprocess_crash:0xC0000409 | 2 | actionable | Inspect affected step distribution, stderr/error tails, retry/fallback outcome, and whether final scene output survived. | step_runs.jsonl affected step distribution; step_runs.jsonl error tails; run.warnings; recovery_outcome; scene_ingest_results.json; phase6_qdrant_truth |
| too_short | 2 | informational | No action unless count increases sharply or correlates with unhealthy Phase 6/Qdrant output. | temporal_index.json segments; scene_ingest_results.json modality_status; phase6_qdrant_truth |

## Blocking Signals
No blocking recurrence families found.

## Read-Only Disclaimer
This operator artifact is read-only. It was generated from persisted runtime truth surfaces only: `step_runs.jsonl`, `experiment_log.json`, `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`.

It does not activate ControlAgent, enable healing, mutate configs, touch `cli/run_ingestion.py`, use LLMs, or recommend broad reruns as the first action.
