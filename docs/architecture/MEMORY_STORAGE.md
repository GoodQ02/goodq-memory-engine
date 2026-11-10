<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-03 -->

# Memory & Storage Architecture

**Last Updated:** 2026-07-11
**Status:** ✅ Operational, with epoch-scoped SQLite + Qdrant as the active storage contract

---

## Overview

GoodQ4All uses a layered memory architecture:
- epoch-scoped SQLite for canonical relational storage
- Qdrant for canonical vector retrieval
- optional FAISS parity/fallback where configured
- scene manifests and temporal indexes as durable artifact evidence, distinct
  from active memory under isolation

This document describes the current storage contract, not historical storage experiments.

### UCF occurrence identity

`context_frames` distinguishes occurrences with the unique key
`(video_hash, epoch_id, modality, worker_name, t_start, t_end, occurrence_id)`.
The empty occurrence ID retains legacy timestamp-upsert behavior. Recording-audio
transcripts use source/scene/native-utterance identity; speaker turns use the
source/scene/turn ordinal in the retained ordered projection. Two channels or
turns with identical rounded display times therefore remain separate. Replaying
that same projection updates the existing frame and returns its actual frame ID.
The raw evidence, exact source samples where available and projection hash remain
the evidence authority; an occurrence ID is not a speaker identity claim.

The ledger initializer migrates the former timestamp-only key transactionally,
using a consistent SQLite backup before create/copy/drop/rename. Frame IDs,
payloads, statuses, timestamps, audit references, indexes/triggers and the
autoincrement high-water mark are preserved. Existing recording rows receive
IDs from their retained native utterance IDs or turn ordinals; missing required
identity fails visibly and rolls back. Previously overwritten events cannot be
recovered by schema migration alone: replay of the verified retained projection
is required. Other producers retain the empty ID and their prior semantics.

This migration is qualified in disposable candidate data only. Live migration
and coordinated writer deployment remain separate approvals; old writer SQL
cannot write the revised uniqueness key. Promotion remains human-gated and
epoch/source-scoped. **UNDO ONLY — not a verification step:** after stopping all
writers, restore the consistent pre-migration database backup together with the
compatible writer revision; do not run an old writer against the migrated store.

---

## Canonical Storage Roots

### Artifact and Epoch Root

```text
${GOODQ_DATA_ROOT}/GoodQ_Data
```

### Epoch Root

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>
```

### WSL Worker Root

```text
${GOODQ_WSL_WORKSPACE}
```

The WSL workspace is a compute extension root, not the canonical persistence root.

---

## Active Storage Systems

### 1. `memory.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
```

**Purpose**
- scene bundles
- segment rows
- embedding identity and routing metadata
- links
- summaries
- commit observability

**Core Tables**
- `scenes`
- `segments`
- `embeddings`
- `links`
- `summaries`
- `memory_commit_events`

### 2. `knowledge_graph.db`

**Location**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

**Purpose**
- entities and relationships
- structural speaker/face nodes
- scene/media linkage
- temporal events
- identity formation edges

**Core Tables**
- `nodes`
- `edges`
- `media_nodes`
- `node_media`
- `events`
- `event_nodes`

### 3. Qdrant

**Endpoint**

```text
http://localhost:6333
```

**Storage Root**

```text
${GOODQ_DATA_ROOT}/qdrant_storage
```

For the canonical desktop/config authority, Qdrant storage is a sibling of
`GoodQ_Data`. This does not equate that root with the packaged installer's
ProgramData layout; installer/package path reconciliation remains a separate
release concern.

**Canonical Collections**
- `goodq_text_epoch_<epoch>`
- `goodq_audio_epoch_<epoch>`
- `goodq_clip_epoch_<epoch>`
- `goodq_dino_epoch_<epoch>`

Qdrant is the canonical vector retrieval surface.

### 4. FAISS (Optional)

FAISS remains optional as:
- local parity
- offline fallback
- secondary vector surface where configured

It is not the canonical first-class retrieval truth.

Configured FAISS paths are epoch-scoped:

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/faiss/
├── text/faiss_text.index
├── clip/faiss_clip.index
├── dino/faiss_dino.index
├── audio/clap_id_map.sqlite
├── clip/clip_id_map.sqlite
├── dino/dino_id_map.sqlite
└── goodq_audio_<epoch>.index
```

FAISS commits must use explicit stable IDs. New HNSW indexes are wrapped in
`IndexIDMap2`, and writers must not silently downgrade from `add_with_ids` to
position-based `add`. A legacy non-IDMap FAISS file is historical evidence, not
a valid target for new strict FAISS parity writes.

### Standalone document passage embeddings

Long standalone documents use overlapping passages bounded by the active text
encoder's token window. Exact Unicode character offsets, passage text and token
counts refer to the retained extracted document text. Passage IDs include the
source/scene identity and span position; repeated text at different positions
does not share a vector identity. PDF text extraction uses content-stream order
rather than preserving horizontal column spacing. This does not establish OCR or
arbitrary table-layout fidelity.

The document remains one static scene with `[0,0]` time bounds. Its existing
`text_embed` UCF frame owns a validated `embedding_chunks` payload, with total
text length/hash and token budget. Each entry binds one Qdrant/FAISS identity.
Validation requires exact full-text coverage, consistent overlaps, unique
identities, bounded token counts and the retained source anchor. All vector
references participate in promotion, materialization, synchronization, strict
retrieval and retirement. Partial embedding failure cannot publish completed
document memory. Existing scalar records remain supported; no database schema
migration or historical re-indexing occurs automatically.

Search returns a matching passage only when its text and offsets match the
persisted full document. The inspector shows that passage separately from the
complete text and original-file link. A similarity result is supporting source
material, not a claim that an unsupported premise in the query is true.

The search response may also include `document_context_span`, derived from that
same persisted full text only after the ranked anchor has been validated. It
retains at most 1,024 Unicode characters on either side and at most 4,096 total;
the per-side allowance shrinks equally for longer anchors. Outer bounds move
inward to whitespace without removing anchor text. Anchors of 4,096 characters
or more, whole-document anchors, and invalid anchors receive no extra context.
The inspector validates exact source and anchor offsets again and labels this
plain text **Surrounding document context**. It remains separate from
`matched_document_span`; adjacent evidence is not presented as a reranked match
or a generated answer. Both blocks refresh with the query and selection.

For retained standalone document chunks, search selects evidence within each
already-ranked source by combining short-window semantic similarity and BM25
with equal reciprocal-rank fusion. It uses the existing loaded query encoder;
there is no additional model or persistent index. Request-wide limits are 32
candidate chunks and 192 windows, each at most 96 tokens with 48-token overlap.
The output remains an original stored chunk with its exact offsets; ranking
windows are not synthesized evidence. Source IDs, order, scores and metadata
are unchanged by this within-source selector, and exact-phrase passage selection
takes precedence. Document results do not receive video/audio completeness
bonuses or penalties during source fusion; those modality-specific adjustments
remain applicable to video/audio results.

The selector may retain one additional stored chunk whose best existing window
covers strictly more distinct query terms than the primary winner. Comparison
uses case-folded non-stopwords and a limited terminal-s normalization, not a
general language stemmer. It adds no encoder calls and leaves the primary winner
unchanged. The API exposes `lexical_document_span` only when its text and Unicode
offsets exactly match the same full document, it is at most 4,096 characters, and
it is not wholly contained in the already displayed primary/context range.
The inspector repeats those checks and labels plain text **Additional lexical
passage**. This is separate query-term evidence, not a generated answer or a
replacement for the semantic/BM25 anchor.

Candidate truncation and ranking failures are visible in `text_passages`
diagnostics through both text search routes and the Retro console. Failure keeps
the original retrieval. This bounded selector can miss evidence below its
candidate limit or split across adjacent chunks; it does not claim complete
question answering or combine passages into an answer.

---

## Artifact Storage

### Scene Bundle Artifacts

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/
├── audio/
├── video/
│   └── scene_manifest.json
└── temporal_index.json
```

### Run Summary

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/output/scene_ingest_results.json
```

These files are durable evidence in the memory system, not just debug
byproducts. Their presence does not by itself make their contents active or
promoted memory.

### Standalone source bundles

Standalone image, document and audio intake uses the same artifact, UCF and
promotion lifecycle. Its processing directory and retained filename are bound
to the SHA256 of the original source bytes:

```text
<configured processing>/<source_sha256>/
├── <source_sha256>.<original extension>
├── raw_result.json
├── video/scene_manifest.json
└── temporal_index.json
```

One `standalone_source` UCF anchor identifies the source scene; it does not
claim video scene detection. The scene ID uses the existing scene hash over
source SHA256 and bounds. Image and document bounds are the point `[0,0]`;
audio bounds are `[0, measured duration]`. Existing UCF modalities remain
unchanged: image anchors use `multimodal`, documents use `text`, and audio
uses `audio`. Derived image text remains `text` and visual vectors use
`multimodal`. An optional flat `source_kind` identifies these new records.

Standalone validation and promotion both bind the anchor, canonical scene ID,
manifest, retained source path and bytes. Promotion adds `source_kind` to
existing scene metadata and KG media properties; KG media type identifies the
actual source kind. The existing structural source/scene relationship vocabulary
and lifecycle scope keys remain compatible. Document extraction is preserved as
`document_text` with `document_meta` parser provenance, and indexed under FTS
`content_type=document_text`; it is not relabeled OCR or speech. Static sources
do not create speech segment rows. Images retain detailed visual outputs in the
scene keyframe; audio retains measured transcript segments and worker evidence.

These are additive metadata and FTS content values, not new SQL columns, UCF
enums or a schema migration. Missing `source_kind` keeps the legacy video
interpretation. Older artifacts and rows are unchanged. All vector types retain
the same staging, explicit promotion, outbox and terminal-state visibility gates.
Supersede/reject retires active projections without deleting retained source
artifacts. Standalone artifact presence alone never authorizes active retrieval.

---

## Governed Materialization Lifecycle

With `ingestion_isolation: true`, `scene_manifest.json` is per-video artifact
evidence. The epoch ledger is `ucf/ucf_ledger.db`. `ucf_ledger.db` is the
lifecycle and evidence authority. Isolated ingest stages UCF context frames
there and Qdrant points with exact
`ucf_promotion_status = staged`. Ingest does not directly populate active
`memory.db` or `knowledge_graph.db` in this mode.

Promotion is explicit and scope-bound:

1. Explicit `validate_ucf_frames` validation must occur first.
2. A human-gated `promote_ucf_to_memory` operation then acts on one exact
   `video_hash` plus `epoch_id` scope.
3. Promotion materializes active `memory.db` and `knowledge_graph.db` from the
   governed evidence.

Within `ucf_ledger.db`, the status mutation, transition audit, and durable
Qdrant outbox enqueue share one immediate SQLite transaction. That transaction
does not make the active SQLite stores and Qdrant one cross-store ACID unit.
Active-view cleanup after a materialization failure is compensating and
recoverable. Post-commit Qdrant status delivery and reconciliation are separate
durable, recoverable obligations.
`promotion_committed_sync_pending` therefore means the active materialization
and UCF commit succeeded while durable Qdrant status delivery is still pending.

Default active retrieval admits only promoted evidence. Explicit raw audit
queries may inspect other UCF lifecycle states without making them active.

### Exact-scene retirement

`supersede_ucf_frames` retains its epoch/video operation. The optional
`scene_id` selects one canonical scene within that exact epoch and video;
unknown, ambiguous or mismatched selectors fail before confirmation. The
scene manifest and UCF anchor must agree on source identity, bounds and aliases.

Scene retirement records versioned exact frame/vector evidence in the existing
immutable `ucf_status_transitions` audit and enqueues
`scene_retirement:<scene_id>` in the existing delivery outbox. No SQL schema
change is required. The committed ledger exclusion is authoritative even if
delivery to SQLite, KG or Qdrant is interrupted. Active readers must consult it
before serving retained artifacts, cached identity matches or summaries.
Cleanup preserves neighboring scenes and their supported shared records;
whole-video summaries containing removed evidence are invalidated. Source
files remain retained, and original-source playback remains available while
neighboring scenes survive.

Retry pending retirement through the same confirmed `supersede_ucf_frames`
request with the same three scope fields. It reuses immutable evidence rather
than creating a second retirement. `reconcile_ucf_qdrant` remains a promotion
delivery operation, not the retirement recovery command. Same-epoch producer
replay and promotion cannot restore retired scene aliases. This exclusion does
not transfer into a new corpus epoch. Retirement is a memory visibility action,
not deletion of original media or proof that every byte of derived data is gone.

The supported `cli.retrieve` FAISS projection checks exact embedding membership
in the configured epoch ledger before returning a result. A promoted scene does
not authorize an unrelated staged embedding. Scores remain attached to stable
FAISS IDs, and exact persisted scene IDs supply video/time provenance. A missing
configured ledger or mapping database is a failure, not a successful empty query.
Legacy stores without an epoch configuration or UCF provenance retain their
existing frame-link lookup behavior.

Scene-summary embeddings use the logical UCF producer `scene_summary_embed`;
frame and transcript text embeddings retain `text_embed`. Distinct producer
identities prevent equal scene spans from replacing each other's UCF records.
Historical summary records remain readable. A resumed old summary may match the
new worker tag only with matching original point identity and summary provenance;
ordinary transcript worker mismatches remain invalid. No ledger schema migration is needed.
FAISS IDs derive from the original embedding identity, which may differ from a
normalized Qdrant point key. Promotion preserves existing source metadata.

---

## Memory Integrity Doctrine

### Confidence Is Not Policy

Confidence values are metadata only. They must not silently become retrieval or memory-policy decisions without an explicit, approved policy layer.

### Audit Absence Is Not Evidence

`memory_commit_events` and retrieval observability tables are best-effort audit surfaces. Missing rows do not prove the underlying event never happened.

### Provenance Is Traceability

Provenance fields help trace a result back to storage, but they do not replace the canonical artifact or DB truth.

### Identity Must Remain Stable

Storage identity must remain deterministic. Changes to embedding identity, point identity, or stitching identity semantics risk corrupting memory continuity.

### Per-Target Commit Truth Matters

Write success must be interpreted per store. A row-level success flag is not permission to assume every possible store contains the same memory.

### Explicit FAISS IDs Are Required

When FAISS is configured, a successful FAISS commit means the vector was written
with a deterministic explicit ID and any configured SQLite ID map was updated.
Sequential FAISS row positions are not stable provenance. If an existing FAISS
index cannot accept explicit IDs, the writer must fail visibly for that FAISS
target rather than reporting a best-effort success.

### Audio Vector Success Requires Run Provenance

For CLAP audio vectors, current-run success is not proven by scene-id presence
in Qdrant. A scene counts as current-run audio-vector covered only when the
scene payload has `clap_meta.status == ok` and the Qdrant audio payload has the
same `run_id` plus required provenance fields.

Legacy audio points with missing `run_id`, stale points from another `run_id`,
and `clap_meta.status == skipped` or `error` are not current-run success.
Consumers should expose narrower states such as
`provenance_unverified_audio_vector_exists`, `legacy_audio_vector_present`,
`audio_vector_skipped`, or `audio_vector_error`.

See `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`.

---

## Identity-Aware Storage Truth

The current storage layer now includes identity formation artifacts.

### Manifest-Level Inputs

Fresh scene manifests may include:
- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`

### Separate Identity-Workflow Outputs

The KG may include:
- `speaker_pattern` nodes
- `voice_pattern_match` edges
- `identity_candidate` edges
- `identity_supported` edges
- `identity_evidence` edges

Governed UCF promotion materializes active video, scene, segment, and evidence
KG projections. It does not by itself prove or materialize the speaker-pattern
or identity edges listed above. Manifest identity fields remain inputs to the
separate governed identity-ledger and stitching workflows; their outputs become
active identity truth only when those workflows execute and persist them.

---

## Conduits And Observability

### Observability Tables

Current write/read observability surfaces include:
- `memory_commit_events`
- `retrieval_events`

These are integrity and audit tools, not reinforcement learning surfaces.

### UI-Safe Derived Conduits

Derived conduit tables remain additive and sanitized. They may expose:
- hashes and ids
- timestamps and durations
- booleans and counts
- store names
- media reference tokens

They must not expose:
- raw vectors
- absolute paths
- raw transcript payloads by default
- basement-only raw event tables

---

## Query And Routing Truth

### Read Priority

Current retrieval should treat Qdrant as the canonical vector surface, with optional FAISS fallback where configured.

### Write Targets

Non-isolated ingestion may write active SQLite scene/KG surfaces directly.
Under `ingestion_isolation: true`, ingestion instead stages UCF and Qdrant
evidence; the governed promotion operation owns active SQLite materialization.
FAISS remains an additional target only when configured.

For audio retrieval health, count Qdrant audio payloads by matching `run_id`,
not by `scene_id` alone. The supported CLAP audio provenance marker includes
`run_id`, `embedding_id`, `component`, `step`, `model`, `created_at`, and
`commit_ts_utc` when available.

### Important Constraint

Storage docs must not describe a FAISS-first world or a root-level DB world as if it were current runtime truth.

---

## Backup And Recovery

Backups should cover the configured canonical roots:

- `memory.db`
- `knowledge_graph.db`
- Qdrant snapshots

The backup target itself is operationally configurable. Epoch SQLite/artifact
truth lives under `GoodQ_Data`, while canonical desktop/config Qdrant storage
lives at the sibling root defined above.

---

## Verification Checklist

The storage contract is healthy when:

1. `memory.db` and `knowledge_graph.db` exist under the current epoch.
2. `scene_manifest.json` exists under the epoch processing tree.
3. `scene_ingest_results.json` exists under the epoch output tree.
4. successful witnesses show `qdrant_ok = true`.
5. current-run CLAP audio coverage equals scenes where `clap_meta.status == ok`
   and Qdrant audio payloads have matching `run_id` provenance.
6. fresh stitching-era runs can persist speaker voice signatures and pattern edges without breaking the scene bundle contract.

---

## Deprecated Or Non-Canonical Narratives

These should not be treated as active truth:
- root-level DB assumptions outside the epoch tree
- ChromaDB as a primary integrated store
- internal legacy `chroma` naming as proof that the runtime still depends on a real ChromaDB tier
- FAISS as the primary retrieval truth
- older `logs/scene_ingest` artifact roots
- docs that present old service-era storage assumptions as current

Historical notes can keep those details, but active operator docs should not.

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md)
- [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)
- [IDENTITY_STITCHING_CONTRACT.md](IDENTITY_STITCHING_CONTRACT.md)

---

## Summary

The current memory system is:
- epoch-scoped
- scene-centric
- SQLite-backed for relational memory and graph truth
- Qdrant-backed for canonical vector retrieval
- stitching-aware through persisted manifest and KG identity surfaces

That is the storage contract active operators and agents should reason from.
