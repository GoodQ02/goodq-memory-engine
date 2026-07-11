<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_CURRENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# GoodQ4All Current Agent State

Generated from evidence `2923b9a7ca972db2` captured at
`2026-07-11T13:08:29Z`. Do not hand-edit this file; regenerate it with
`scripts/docs/build_current_state.py` from the checked evidence snapshot.

## Authority

- Active epoch: `epoch_2026_07_05_home_memory_clean_01`
- Host profile: `GPU_ENHANCED`
- Desktop is canonical; the laptop is a follower.
- Lifecycle state: `complete_and_fully_promoted`. This capture proves the active corpus complete and fully promoted; it is not an ingestion target.

## Completion and Persistence

| Evidence | Count |
|---|---:|
| Media sources | 12 |
| Distinct videos in UCF | 12 |
| UCF context frames | 75,094 |
| Promoted UCF frames | 75,094 |
| Processed media | 12 |
| Import inbox media | 0 |
| Failed media | 0 |
| Materialized scenes | 1,648 |
| Materialized segments | 16,535 |
| Embeddings | 8,736 |
| Knowledge-graph nodes | 93,293 |
| Knowledge-graph edges | 1,928,045 |
| Lifecycle transition rows | 1 |

The lifecycle ledger contains only the events shown above. Do not reconstruct
or fabricate missing historical promotion events.

## Observed Qdrant Census

Configured collection authority is derived from the active epoch. The counts,
dimensions, and status below are observations returned by Qdrant at capture.

| Modality | Exact collection | Points | Dimensions | Status |
|---|---|---:|---:|---|
| audio | `goodq_audio_epoch_2026_07_05_home_memory_clean_01` | 1,453 | 512 | green |
| clip | `goodq_clip_epoch_2026_07_05_home_memory_clean_01` | 2,913 | 768 | green |
| dino | `goodq_dino_epoch_2026_07_05_home_memory_clean_01` | 2,913 | 1024 | green |
| text | `goodq_text_epoch_2026_07_05_home_memory_clean_01` | 4,292 | 384 | green |

## Configured Runtime Versus Observed State

Configuration describes intended routing; observation describes this one
capture. A configured service is not claimed to be running unless the observed
column says so.

| Service | Observed state |
|---|---|
| goodq_api | `timeout` |
| ollama | `reachable` |
| qdrant | `running_loopback` |
| vllm | `not_probed_non_loopback` |
| wsl | `not_probed` |

- Configured GoodQ API: `http://127.0.0.1:30000`
- Configured Qdrant: `http://127.0.0.1:6333`
- Configured vLLM: redacted (non-loopback configured) with model
  `Qwen2.5-0.5B-Instruct`
- Configured GoodQ Ollama: `http://127.0.0.1:11434/v1` (loopback) with model
  `llama3.2:latest`
- Hermes/Gemma on the GOOD-CUBE toolbelt is a separate local agent runtime and
  does not define GoodQ epoch or model authority.

## Historical Evidence

- [July promotion witness](../agent/birth_certificate.md) — historical evidence; not active authority.
- [June family-film pilot](../agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md) — historical evidence; not active authority.
- [sealed basement-era handoff](../archive/HANDOFF_BASEMENT_PHASE.md) — historical evidence; not active authority.

## Capture Limitations

- Service observations are a point-in-time snapshot and do not start stopped services.
- WSL was intentionally not probed because that can change runtime state.
- Configured loopback URLs show routing intent; listener bindings were not independently audited.
- Historical lifecycle events were not reconstructed; the ledger is reported as found.
- Hermes, OpenViking, and Nanobot are GOOD-CUBE-local adapters, not GoodQ epoch authority.
