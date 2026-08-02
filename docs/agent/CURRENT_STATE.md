<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_CURRENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# GoodQ4All Current Agent State

Generated from evidence `eb137833bb4fa5dd` captured at
`2026-08-02T00:00:00Z`. Do not hand-edit this file; regenerate it with
`scripts/docs/build_current_state.py` from the checked evidence snapshot.

## Authority

- Active epoch: `epoch_public_release_candidate`
- Host profile: `PUBLIC_RELEASE_CANDIDATE`
- Desktop is canonical; the laptop is a follower.
- Lifecycle state: `not_proven_complete_or_fully_promoted`. The active corpus is not proven complete or fully promoted by this capture.

## Completion and Persistence

| Evidence | Count |
|---|---:|
| Media sources | 0 |
| Distinct videos in UCF | 0 |
| UCF context frames | 0 |
| Promoted UCF frames | 0 |
| Processed media | 0 |
| Import inbox media | 0 |
| Failed media | 0 |
| Materialized scenes | 0 |
| Materialized segments | 0 |
| Embeddings | 0 |
| Knowledge-graph nodes | 0 |
| Knowledge-graph edges | 0 |
| Lifecycle transition rows | 0 |

The lifecycle ledger contains only the events shown above. Do not reconstruct
or fabricate missing historical promotion events.

## Observed Qdrant Census

Configured collection authority is derived from the active epoch. The counts,
dimensions, and status below are observations returned by Qdrant at capture.

| Modality | Exact collection | Points | Dimensions | Status |
|---|---|---:|---:|---|
| audio | `goodq_audio_epoch_public_release_candidate` | 0 | 0 | green |
| clip | `goodq_clip_epoch_public_release_candidate` | 0 | 0 | green |
| dino | `goodq_dino_epoch_public_release_candidate` | 0 | 0 | green |
| text | `goodq_text_epoch_public_release_candidate` | 0 | 0 | green |

- Non-authority Qdrant collections observed: `0`.
  They are excluded from active epoch authority and require a separate retention
  audit before any cleanup.

## Configured Runtime Versus Observed State

Configuration describes intended routing; observation describes this one
capture. A configured service is not claimed to be running unless the observed
column says so.

| Service | Observed state |
|---|---|
| goodq_api | `not_probed` |
| ollama | `not_probed` |
| qdrant | `running_loopback` |
| vllm | `not_probed` |
| wsl | `not_probed` |

- Configured GoodQ API: `http://127.0.0.1:30000`
- Configured Qdrant: `http://127.0.0.1:6333`
- Configured vLLM: not configured with model
  `None`
- Configured GoodQ Ollama: not configured with model
  `None`
- Hermes/Gemma on the GOOD-CUBE toolbelt is a separate local agent runtime and
  does not define GoodQ epoch or model authority.

## Historical Evidence



## Capture Limitations

- This is a sanitized public release receipt, not a private corpus or runtime snapshot.
- Private media, corpus counts, paths, and operational receipts are intentionally omitted.
- The public candidate must be configured and verified by each operator before ingesting media.
