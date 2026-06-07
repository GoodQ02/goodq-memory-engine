# GoodQ Control Recurrence Comparison

- Generated at: `2026-04-28T00:32:48.358711+00:00`
- Baseline run ID: `20260424_003250_season1_recompare_witness`
- Candidate run ID: `20260424_182406_season2_fresh_witness`
- Mode: `read_only_observability_comparison`

## Runs
- Baseline: `20260424_003250_season1_recompare_witness`
- Candidate: `20260424_182406_season2_fresh_witness`
- Total recurrence signals: `4` -> `54` (delta `50`)

## Recommendation
- Status: `WARN`
- Highest category: `actionable`
- Reasons:
  - highest candidate recurrence category is actionable
  - informational skipped conditions increased sharply: insufficient_diverse_speech
  - new watch/actionable/blocking families: diarization_unavailable, native_crash_retry:0xC0000409

## Category Counts
| Category | Baseline Families | Candidate Families | Family Delta | Baseline Signals | Candidate Signals | Signal Delta |
|---|---:|---:|---:|---:|---:|---:|
| informational | 2 | 4 | 2 | 2 | 33 | 31 |
| watch | 0 | 1 | 1 | 0 | 15 | 15 |
| actionable | 1 | 2 | 1 | 2 | 6 | 4 |
| blocking | 0 | 0 | 0 | 0 | 0 | 0 |

## Recovered / Unrecovered / Skipped Counts
| Outcome | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| recovered | 2 | 6 | 4 |
| unrecovered | 0 | 0 | 0 |
| skipped | 2 | 48 | 46 |
| unknown | 0 | 0 | 0 |

## Phase 6 Health
- Status: `improved`
- Healthy episodes: `1` -> `12` (delta `11`)

## Qdrant Health
- Status: `improved`
- Healthy episodes: `1` -> `12` (delta `11`)

## New / Increased / Resolved Families
### New Families
- `audio_silent`
- `diarization_unavailable`
- `native_crash_retry:0xC0000409`
- `too_short`

### Increased Families
| Family | Category | Baseline | Candidate | Delta |
|---|---|---:|---:|---:|
| insufficient_diverse_speech | informational | 1 | 24 | 23 |
| diarization_unavailable | watch | 0 | 15 | 15 |
| native_crash_retry:0xC0000409 | actionable | 0 | 4 | 4 |
| no_text | informational | 1 | 5 | 4 |
| audio_silent | informational | 0 | 2 | 2 |
| too_short | informational | 0 | 2 | 2 |

### Resolved Families
- none

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
