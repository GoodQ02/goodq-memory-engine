<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-10 -->

# Ingest Orchestration Contract

This document defines the execution authority, cutover model, and adapter
rules for the canonical GoodQ ingestion path.

It exists to close a long-standing gap between:

- orchestration in `cli/run_ingestion.py`
- isolated step execution in `cli/step_runner.py`
- semantic fusion in segmentation, Phase 6, and memory persistence

The system already has the engines. This contract defines how they are allowed
to plug into the canonical ingest path.

## Scope

This contract applies to:

- `cli/run_ingestion.py`
- `pipelines/direct_ingestion.py`
- `cli/step_runner.py`
- `steps/common/config_loader.py`
- `steps/common/memory.py`
- `steps/video/scene_visual_embeddings.py`
- `steps/video/cross_modal_harmonizer.py`
- the phased segmentation engine under `steps/audio/segmentation/`

This contract does not replace the artifact schema contract in
`docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`.

## Authority Model

### 1. Canonical execution owner

`cli/run_ingestion.py` is the canonical execution owner.

It owns:

- runtime config resolution
- profile and runtime contract enforcement
- scene loop ownership
- step ordering
- persistence boundaries
- Phase 6 triggering
- cutover decisions

No step module owns pipeline orchestration.

### 2. Convergence entrypoints

Programmatic and wrapper entrypoints converge downward into the same canonical
runner:

- `pipelines/direct_ingestion.py` is a thin wrapper around `cli/run_ingestion.py`
- `cli.watchdog` is an orchestration surface, not an alternate ingest engine
- launchers and wrappers may start ingestion, but they do not redefine pipeline order

### 2a. API mutation boundary

The active API does not currently own ingest orchestration.

Rules:

1. `POST /api/system/ingest` must remain disabled unless it can act as a controlled facade over the canonical watchdog / CLI runtime.
2. The active API may expose a narrow ingest facade only if it:
   - validates a single supported local file
   - writes a durable request record
   - stages the file into the canonical inbox
   - returns a request handle
   - resolves status from the request ledger outward into watchdog/runtime artifacts
3. Any ingest API surface must be:
   - explicit
   - confirmation-gated
   - policy-driven
   - budgeted
   - checkpointed
   - auditable
4. An ingest route must hand work into the canonical runtime path rather than introducing a second ingest engine.
5. `POST /api/system/reindex` and `POST /api/system/reload` remain operator-only until a real policy-driven control plane exists for those maintenance actions.

### 3. Step system role

`cli/step_runner.py` is the isolated step execution surface.

It owns:

- step-name to callable mapping
- env-isolated execution
- config handoff into step callables
- structured result emission

It does not own:

- scene loop decisions
- persistence authority
- cutover decisions
- phase activation policy

### 4. Persistence authority

`steps/common/memory.py` defines the persistence boundary for scene materialization.

The canonical runner must remain responsible for:

- `ensure_scene(...)`
- `scene_has_materialized(...)`
- `register_scene_bundle(...)`

Steps may produce data, but they do not decide whether a scene is canonical,
materialized, or persisted as a bundle.

### 4a. Progressive checkpoint truth

`progressive_ingestion_state.json` is a schema-v2 recovery record. Its
`windows` map retains one record per window index. Every window names exactly
these persistence targets:

- `memory_db`
- `knowledge_graph`
- `vectors`
- `scene_manifest`
- `temporal_index`

Each target has one status: `committed`, `not_applicable`, or `failed`. A window
is resumable only when its own `window_status` is `committed`, all five targets
are present, and none is `failed`.

Target status must come from persistence evidence, not from reaching the end of
the window loop:

- `memory_db` and `knowledge_graph` use read-only scene-presence probes when
  those stores are enabled for the run.
- `vectors` means the canonical Phase 6 Qdrant scene-vector target. It requires
  persisted successful Phase 6 commit evidence for every window scene in
  `scene_manifest.json`. It is `not_applicable` when Phase 6 retrieval is
  disabled.
- `scene_manifest` requires every window scene in the parseable manifest.
- `temporal_index` requires a parseable artifact when Phase 6b is applicable.

Under `ingestion_isolation: true`, active `memory.db` and knowledge-graph writes
are deliberately suppressed, so those targets are `not_applicable`. Recovery
must rehydrate skipped scenes from `scene_manifest.json` and must not open or
create `memory.db` merely to resume.

Resume re-runs the applicable read-only persistence and artifact probes before
trusting a schema-v2 record. It is per exact verified window index: a failed or
now-stale window is re-evaluated even if a later window committed, and
rehydrated plus newly processed scene outputs are restored to timeline order
before the manifest is written. Legacy boolean checkpoints have insufficient
persistence evidence and are ignored; their windows are re-evaluated and
replaced by schema v2 rather than migrated by assumption.

Final cleanup uses the same evidence gate. The checkpoint may be deleted only
when Phase 6 is complete and a fresh re-probe verifies every current window as
committed with exactly the five targets above and no failed target. Qdrant
completion alone is not sufficient to discard recovery evidence.

## Config Loading Contract

Runtime configuration is loaded once near process start and passed downward.

Rules:

1. Entry points may call `load_configs()`.
2. Non-entry-point runtime modules must accept `cfg` and must not re-load config.
3. Step modules are passive consumers of config.
4. Cutover behavior must be controlled by config, not by hidden module-local logic.

Canonical references:

- `steps/common/config_loader.py`
- `docs/architecture/CONFIG_LOADING_CONTRACT.md`

## Scene-First Invariant

Scenes are the atomic unit of ingest.

That means:

- scene detection or scene production must happen before canonical persistence
- per-scene artifacts must remain attributable to one scene boundary
- alternative engines may enrich or replace upstream scene/audio preparation only
  through explicit orchestration cutover

No alternate engine may silently bypass scene persistence or Phase 6 consumption.

## Agent Repair Behavior

Agent-driven runtime changes must preserve the scene-first invariant.

Required behavior:

1. isolate one concrete seam
2. trace it to one code path or one contract mismatch
3. implement the smallest viable repair
4. validate at scene level or focused contract level first
5. widen to a full witness only after the smaller validation passes

Agent actions must not:

- bundle unrelated fixes into one runtime pass
- bypass scene-first validation
- alter persistence or Phase 6 contracts casually
- treat eval anchors or public references as runtime truth overrides

This repair behavior is elaborated in
`docs/architecture/AGENT_DECISION_PROTOCOL.md`.

## Phase Activation Contract

### Current canonical sequence

The current canonical runner owns this high-level order:

1. resolve config and runtime contracts
2. identify candidate video inputs
3. detect or materialize scene boundaries
4. run per-scene step execution
5. persist scene bundles
6. trigger Phase 6a visual embeddings
7. trigger Phase 6b cross-modal harmonization

### Phase 6 trigger rule

Phase 6 runs only when both are true:

- `phase6.enabled` is true
- scenes exist for the current video

Phase 6 consumes persisted scene and audio artifacts. It does not decide how
those artifacts were produced.

## Cutover Model

All engine substitution must follow one of three explicit modes.

### `off`

Meaning:

- canonical ingest path only
- no shadow comparison
- no alternate-engine promotion

Current example:

- `segmentation.activation = "off"`

### `shadow`

Meaning:

- alternate engine may run side-by-side
- derived artifacts may be written
- metrics may be emitted
- canonical scene persistence and Phase 6 authority remain unchanged unless a
  documented overlay exception is enabled

Current example:

- `segmentation.activation = "shadow"`
- optional `segmentation.shadow_audio_overlay = true`

### `authoritative`

Meaning:

- alternate engine becomes upstream truth for the defined seam
- canonical runner still owns execution and persistence
- rollback path must remain explicit

Current status:

- reserved but not yet enabled for the phased segmentation engine
- `cli/run_ingestion.py` currently returns
  `segmentation_authoritative_not_enabled`

## Adapter Rules

Engine cutover is allowed only through explicit adapters.

Adapters must:

- be pure transforms with no side effects
- accept canonical input structures from the runner
- emit documented artifact shapes
- preserve scene identity and timestamps
- preserve enough information for persistence and Phase 6

Adapters must not:

- write directly to memory stores behind the runner's back
- self-promote a derived artifact into canonical authority
- hide fallback decisions

## Supported Substitution Seams

### 1. Audio enrichment seam

Allowed:

- WSL-first audio with Windows fallback
- shadow audio overlay for Phase 6 inputs

Not allowed:

- hidden WSL-only failure paths that drop transcripts without structured downgrade

### 2. Scene production seam

Allowed:

- shadow comparison between legacy scene detect and `SEG_P5`
- later authoritative cutover if metrics justify it

Not allowed:

- replacing scene authority inside a step module without a runner-level mode switch

### 3. Temporal fusion seam

Allowed:

- shadow production of fusion-ready artifacts
- later promotion into authoritative `temporal_index.json` generation

Not allowed:

- bypassing Phase 6 persistence rules

## Current Exceptions

The only current cutover exception is the shadow audio overlay:

- `segmentation.activation = "shadow"`
- `segmentation.shadow_audio_overlay = true`

In this mode:

- shadow audio artifacts may feed the live Phase 6 harmonizer
- scene authority remains owned by the canonical ingest path
- this is not a full segmentation cutover

## Observability Requirements

Every orchestration decision that changes behavior must be observable.

Required surfaces include:

- runtime profile state
- selected audio backend and downgrade reason
- scene materialization state
- shadow summary and shadow metrics
- Phase 6 completion or skip reason

No cutover or fallback may be implicit.

## Persistence Requirements For Any Future Authoritative Cutover

Before an alternate engine can become authoritative, all of the following must
be true:

1. the runner still owns execution order
2. `ensure_scene(...)` and `register_scene_bundle(...)` still define persistence
3. Phase 6 consumes the promoted artifacts without hidden path rewrites
4. rollback to the prior canonical path is config-driven
5. observability remains at least as strong as the current path

## Current Practical Reading

In plain terms:

- `run_ingestion.py` owns decisions
- `step_runner.py` owns isolated execution
- steps are passive
- memory persistence is authoritative
- Phase 6 is a consumer of scene/audio artifacts, not a cutover authority
- alternate engines may only enter through explicit `off` / `shadow` / `authoritative`
  orchestration modes

## Related Contracts

- `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- `docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`
- `docs/technical/PIPELINE_RESTORATION_BACKLOG.md` (historical backlog reference only)
- `docs/architecture/PHASE6_MULTIMODAL_FUSION.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
