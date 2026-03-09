# Season 1 Witness Run

Date: 2026-03-09

## Summary

This document records the formal witness run for the Seinfeld Season 1 control set after the runtime authority cleanup, WSL audio contract alignment, semantic normalization work, retrieval alignment work, and CLAP observability fix.

The run was executed from a clean canonical epoch state and supervised end to end with a stall watchdog on the active ingestion process and the canonical `step_runs.jsonl` heartbeat.

## Input Set

- `samples/ingestion/Sein_Experiment/01x01 - Good News, Bad News.mp4`
- `samples/ingestion/Sein_Experiment/01x02 - The Stakeout.mp4`
- `samples/ingestion/Sein_Experiment/01x03 - The Robbery.mp4`
- `samples/ingestion/Sein_Experiment/01x04 - Male Unbonding.mp4`
- `samples/ingestion/Sein_Experiment/01x05 - The Stock Tip.mp4`

## Runtime Baseline

- Git SHA: `853f4d04d1edf7770ac122718d3f83822b48e753`
- Run ID: `ca15d80b-80b1-4207-b25c-ed8bd477336f`
- Audio path: WSL2 unified audio
- WSL workspace: `~/goodq_audio`
- Vector store: Qdrant collections for the active epoch
- Memory stores: canonical epoch `memory.db` and `knowledge_graph.db`

## Clean-State Protocol

Before the witness run:

- canonical epoch SQLite stores were removed
- canonical epoch processing, logs, FAISS, and output state were cleared
- the four active epoch Qdrant collections were dropped

This ensured the witness run rebuilt the control set from empty authoritative stores.

## Result

The witness run completed successfully with no process stall and no processing-error scenes.

### Core Metrics

| Metric | Value |
| --- | --- |
| Episodes processed | 5 |
| Scenes processed | 185 |
| Transcript-bearing scenes | 182 |
| Transcript coverage | 98.4% |
| Empty scenes | 3 |
| Processing-error scenes | 0 |
| WSL audio scenes | 185 / 185 |
| Step-run rows | 2972 |
| Non-`ok` step rows | 3 |

### Qdrant Counts

| Collection | Points |
| --- | --- |
| clip | 185 |
| dino | 185 |
| text | 182 |
| audio | 184 |

### Knowledge Graph Counts

| Metric | Value |
| --- | --- |
| Nodes | 310 |
| Edges | 315 |

Node profile:

- `scene=185`
- `person=76`
- `location=22`
- `temporal_context=15`
- `entity=10`
- `audio_event=1`
- `concept=1`

Edge profile:

- `appears_in=169`
- `interacts_with=86`
- `co_occurs=35`
- `located_in=25`

## Per-Episode Coverage

| Episode | Scenes | Transcript Scenes | Empty Scenes |
| --- | --- | --- | --- |
| `01x01 - Good News, Bad News` | 33 | 32 | 1 |
| `01x02 - The Stakeout` | 39 | 38 | 1 |
| `01x03 - The Robbery` | 36 | 36 | 0 |
| `01x04 - Male Unbonding` | 38 | 38 | 0 |
| `01x05 - The Stock Tip` | 39 | 38 | 1 |

The three empty scenes are short end-cap style segments and remained non-fatal.

## Optional-Step Exceptions

Three optional-step failures were recorded explicitly and did not halt ingestion:

1. `sentiment` on episode 1 scene 27
2. `audio_embed_clap` on episode 5 scene 7
3. `sentiment` on episode 5 scene 33

These were persisted both as scene-level metadata and as explicit non-`ok` rows in the canonical `step_runs.jsonl` log.

The `audio_embed_clap` miss is especially important because this run confirms the observability fix:

- the scene remained `content_state=signal`
- `clap_meta.status=error` was preserved on the scene payload
- `step_runs.jsonl` recorded the failure with `reason=optional_step_failed`
- the row also carried `embedding_emitted=false`

This means the missing audio vector no longer appears invisible to operators.

## Witness Verdict

This run qualifies as a formal witness run for the current release baseline.

Why:

- canonical runtime authority held throughout the run
- WSL audio routing was stable across the full season
- no process stall occurred under supervision
- no scene entered `processing_error`
- optional enrichments failed safely and visibly
- vector persistence and KG persistence remained coherent at season scale

## Remaining Non-Blocking Constraints

- two optional `sentiment` failures still occurred
- one optional `audio_embed_clap` failure still occurred
- speaker-aware relations remain limited because `speaker_count` is still not a strong signal in this control slice

These are release notes, not release blockers, for the witness baseline.
