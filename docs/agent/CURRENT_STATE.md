<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_CURRENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-07-29 -->

# GoodQ4All Current Agent State

Generated from evidence `615a7c4bbcb84c87` captured at
`2026-07-29T205357Z`. Do not hand-edit this file; regenerate it with
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
| Knowledge-graph nodes | 93,308 |
| Knowledge-graph edges | 1,929,056 |
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

- Non-authority Qdrant collections observed: `0`.
  They are excluded from active epoch authority and require a separate retention
  audit before any cleanup.

## Configured Runtime Versus Observed State

Configuration describes intended routing; observation describes this one
capture. A configured service is not claimed to be running unless the observed
column says so.

| Service | Observed state |
|---|---|
| goodq_api | `tcp_reachable` |
| ollama | `reachable` |
| qdrant | `running_loopback` |
| vllm | `stopped_or_unavailable` |
| wsl | `not_probed` |

- Configured GoodQ API: `http://127.0.0.1:30000`
- Configured Qdrant: `http://127.0.0.1:6333`
- Configured vLLM: `http://127.0.0.1:38005/v1` (loopback) with model
  `Llama-3.2-1B-Instruct`
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
