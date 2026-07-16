<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-05-F1 Retrieval Model-Cache Selection

## Decision

Select text and visual retrieval model-cache resolution as the next bounded
repair. Nominal retrieval currently passes remote model identifiers to Sentence
Transformers and Transformers without a pinned local snapshot or a local-only
flag. A missing cache can therefore cause network or cache activity before a
read returns.

The repair will add one pure cached-snapshot inspector and switch only the text
and CLIP query encoders to exact registry-pinned local snapshots. The four
retrieval routes remain `automatic_mutation` because telemetry and SQLite
effects remain open.

## No-Repeat Reconciliation

The branch is clean after these completed authority checkpoints:

- Qdrant query cannot create a missing collection;
- ingest-status construction and lookup cannot create storage; and
- summary video-job status uses a non-creating, lock-free reader with compatible
  Windows action-job replacement.

This selection does not reopen those seams. It also does not repeat the
already-local-only CLAP retrieval loader or ingestion model loaders.

## Fresh Candidate Comparison

### Text and visual model/cache resolution — selected

`MultimodalSearchEngine` currently calls:

- `SentenceTransformer("all-MiniLM-L6-v2")`; and
- CLIP processor/model `from_pretrained()` with
  `openai/clip-vit-large-patch14`.

A fake-loader witness under offline environment flags proved that both sources
were non-existent relative identifiers. Neither call received an absolute local
snapshot, registry revision, explicit cache root, or `local_files_only=True`.

The registry already pins exact revisions for both models. The engine already
receives an explicit `paths.models_cache` authority, and the CLAP retrieval
loader already demonstrates graceful local-only degradation. This makes the
owner and rollback boundary narrow and deterministic.

### Retrieval telemetry — deferred policy seam

All four retrieval routes converge on `QdrantClient.query()`, which writes
retrieval-event SQLite rows after successful hits and may append a JSONL
fallback when SQLite is locked. Temporary witnesses proved both writes.

The audit also found that engine construction does not propagate the configured
JSONL-fallback policy or log directory to the emitter. A configured disabled
fallback was therefore ignored, and fallback output used the database parent.

Telemetry is intentional audit data, and the routes are already truthfully
classified `automatic_mutation`. Repair requires a product decision: preserve
telemetry with authoritative propagation, or add an explicit passive mode and a
separate write authority. Do not make that decision implicitly inside the model
loader repair.

### Summary and retrieval SQLite — deferred contract seams

Ordinary SQLite connections remain in summary dashboard/entity/video
projections and retrieval FTS/KG enrichment. Temporary Windows witnesses proved:

- ordinary connect creates an absent database;
- `mode=ro` rejects writes and sees committed live-WAL rows;
- `mode=ro` may create or update WAL coordination sidecars; and
- `immutable=1` can miss committed WAL content.

A shared primitive may eventually encode the read capability, but summary and
retrieval must remain separate checkpoints. Live-WAL truth versus zero-sidecar
purity is an explicit contract choice, not a URI substitution to hide inside
this seam.

## Current Library Contract

Context7 resolved current primary documentation for both libraries:

- [SentenceTransformer constructor](https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html)
  states that an on-disk path loads locally, another identifier may be
  downloaded, and `local_files_only` defaults to false.
- [Transformers offline mode](https://github.com/huggingface/transformers/blob/main/docs/source/en/installation.md)
  documents loading an existing local directory with
  `local_files_only=True` to avoid Hub access.

The current calls do not meet either local-only contract.

## Provisioner Boundary

The existing `ensure_model_cached(..., offline=True)` function is not a passive
inspector. A temporary cached-hit witness created `logs/model_downloads.log`;
an offline miss appended a second line. The function also owns download locks,
directories, and online snapshot provisioning.

The retrieval path must therefore not call or import the existing provisioner.
That module conditionally appends the repository `vendor` directory to global
`sys.path` during import, so placing a nominally pure inspector there would
still mutate process state. Add a separate side-effect-free cache-inspector
module that:

- accepts an explicit models root and registry key;
- reads the exact registry repository and revision;
- checks only that exact Hugging Face snapshot directory;
- validates the already-present snapshot files;
- returns the existing resolved path or `None`; and
- never creates a directory, changes environment variables, acquires a lock,
  downloads, scans an arbitrary newest snapshot, or writes a download log.

Passing the engine's explicit models-cache root also avoids the existing
`GOODQ_MODELS_ROOT` versus `GOODQ_MODELS_DIR` precedence drift.

## Exact Implementation Boundary

Production scope:

- `steps/common/model_cache_inspector.py`: add the pure exact-snapshot
  inspector without importing the provisioner or mutating process state;
- `retrieval/multimodal_search.py`: use it only in `_load_text_model()` and
  `_load_clip_model()`; and
- focused tests for resolver purity and both loaders.

The seeded calls must be:

- `SentenceTransformer(<absolute snapshot>, local_files_only=True)`;
- `CLIPProcessor.from_pretrained(<absolute snapshot>, local_files_only=True)`;
  and
- `CLIPModel.from_pretrained(<absolute snapshot>, use_safetensors=True,
  local_files_only=True)`.

Missing cache preserves the current graceful unavailable/zero-vector behavior.

Frozen outside this rollback:

- registry contents and revisions;
- download/provisioning functions and logs;
- audio retrieval and ingestion loaders;
- retrieval telemetry and SQLite;
- route and response contracts;
- route-effect classifications and census; and
- dependencies or active environment packages.

## Mutation-Sensitive RED

1. With an absent temporary models root, call both loaders and prove:

   - no library loader is called; and
   - the full temporary tree remains absent.

2. Seed only each exact registry revision in a temporary Hugging Face snapshot
   layout, snapshot paths/bytes/sizes/timestamps, then prove:

   - each fake loader receives the absolute exact snapshot;
   - every loader receives `local_files_only=True`;
   - CLIP retains `use_safetensors=True`; and
   - the entire temporary tree remains unchanged.

3. Fresh-import the inspector while snapshotting `sys.path`, and poison
   `log_download_event`, directory creation, network/download functions, and
   arbitrary-snapshot fallback so any process mutation or accidental
   provisioner use fails immediately.

A wrong implementation using `ensure_model_cached(..., offline=True)` must fail
the tree oracle because it creates the download log.

## Verification and Drift Receipts

The selection used only source traces, fake loaders, temporary roots, and
temporary SQLite fixtures. No live endpoint, model, network, configured cache,
configured data root, Qdrant process, ingestion, identity surface, WSL
distribution, public checkout, or frozen mixed checkout was exercised.

Two independent drifts were verified and assigned outside this seam:

- three search-route test modules fail collection because their dynamic loader
  executes a dataclass module before registering it in `sys.modules`; and
- live `goodq_core` has Sentence Transformers `5.6.0` and Transformers `5.12.1`
  while the baseline locks pin `5.3.0` and `5.4.0`; Hugging Face Hub matches at
  `1.8.0`.

Neither drift authorizes a test-harness patch, dependency change, or environment
rebuild inside this selection or its implementation.

Independent selection review found and closed one planning defect before this
checkpoint: the first draft placed the inspector in the provisioner module and
therefore missed its import-time `sys.path` mutation. The corrected boundary is
a new side-effect-free module plus an explicit fresh-import process-state
oracle.

## Route-Effect Truth

The mounted operation census remains:

| Effect | Count |
|---|---:|
| `passive_read` | 41 |
| `request_staging` | 1 |
| `automatic_mutation` | 10 |
| `curated_mutation` | 8 |
| `process_execution` | 9 |
| **Mounted method/path operations** | **69** |

## First Implementation Gate

Add the absent-cache and exact-seeded-cache tests first. The current loaders must
fail on remote identifiers, missing local-only flags, or unexpected loader
invocation. Only after a mutation-sensitive RED may the pure resolver and two
loader changes be implemented.
