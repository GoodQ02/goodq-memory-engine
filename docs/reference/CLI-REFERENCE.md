<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-10 -->

# GoodQ CLI Reference

**Last Updated:** July 10, 2026
**Status:** Runtime-conditional; verify behavior from current config, artifacts, and health checks

This document is the active command-surface reference for the `cli/` package. It describes the current supported CLI layer, not historical launch paths.

---

## Core Processing

### `python -m cli.run_ingestion`

**Purpose**
- canonical multimodal ingest entry point

**Usage**

```bash
python -m cli.run_ingestion --input-dir <path> [OPTIONS]
```

**Important Options**
- `--input-dir`
- `--output`
- `--workspace`
- `--max-videos`
- `--max-scenes`
- `--scene-threshold`
- `--min-scene-seconds`
- `--force` / `--force-reprocess`
- `--verbose`
- `--step-timeout`
- `--chunk-size` (default `300.0` seconds)
- `--chunk-overlap` (default `10.0` seconds)

**Progressive Ingestion & Interruption Resumption**
- **Sliding Windows**: Video files are partitioned into timeline-sliced progressive analysis windows.
- **Durable Checkpoints**: Schema-v2 `progressive_ingestion_state.json` retains each window and records `committed`, `not_applicable`, or `failed` for memory DB, knowledge graph, Phase 6 vectors, scene manifest, and temporal index.
- **Evidence Gate**: SQLite/graph scenes and parseable artifacts are probed; the vector target requires persisted successful Phase 6/Qdrant evidence in the scene manifest.
- **Interruption Recovery**: Resume re-probes current persistence before skipping an exact window. Failed or stale windows are retried even when later windows committed.
- **Cleanup Gate**: The checkpoint is removed only after every current window re-probes as committed across all five targets; Qdrant completion alone does not clear recovery evidence.
- **Isolation Safety**: With `ingestion_isolation: true`, memory DB and knowledge graph are `not_applicable`; resume reads the scene manifest without opening or creating `memory.db`.
- **Legacy Replacement**: Old boolean checkpoints are not trusted or layered into v2. Their windows are re-evaluated and the checkpoint is replaced.

**Current Truth**
- owns orchestration
- writes epoch-scoped artifacts
- updates active SQLite/KG only when ingestion isolation is disabled
- invokes Phase 6

**Primary Outputs**

```text
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing/<video_name>/
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/output/scene_ingest_results.json
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
```

---

### `python -m cli.watchdog`

**Purpose**
- monitor the configured inbox and trigger ingest for new files

**Usage**

```bash
python -m cli.watchdog
```

**Current Truth**
- resolves inbox and processing paths from config/runtime paths
- runs deterministically without implicitly enabling Control Agent
- persists explicit control-plane state when no injected LLM client is present

---

### `python -m cli.ucf_promotion`

**Purpose**
- inspect promotion readiness without mutation
- request a scope-bound confirmation token
- execute promotion only in a later, explicit command
- surface a locally committed promotion whose Qdrant projection is still pending
- reconcile only that durable pending projection through a fresh approval token

The configured `paths.db_dir` is authoritative. The requested `--epoch-id`
must match that configured epoch, and both approval and execution require one
exact `video_hash` plus `epoch_id` scope.

**Inspect (read-only)**

```powershell
conda run -n goodq_core python -m cli.ucf_promotion inspect --epoch-id <epoch_id>
```

Add `--video-hash <video_hash>` to inspect one scope. A scope is promotable only
when it contains validated frames and no staged frames.

**Approve (issues a token; does not promote)**

```powershell
conda run -n goodq_core python -m cli.ucf_promotion approve --epoch-id <epoch_id> --video-hash <video_hash>
```

**Execute (consumes the separately issued token)**

```powershell
$env:GOODQ_CONFIRMATION_TOKEN = '<confirmation_token>'
conda run -n goodq_core python -m cli.ucf_promotion execute --epoch-id <epoch_id> --video-hash <video_hash>
Remove-Item Env:GOODQ_CONFIRMATION_TOKEN
```

`--confirmation-token` is also supported, but the environment variable avoids
placing the short-lived token directly in the process command line. Tokens are
single-use, expire after ten minutes, and are bound to the exact approved scope.
No command both issues and consumes a token.

If local promotion commits but verified Qdrant payload delivery does not, execute
returns nonzero with `promotion_committed_sync_pending`. The local ledger retains
an exact-scope pending outbox row; rerunning promotion is not the recovery path.

**Approve Qdrant reconciliation (issues a fresh token)**

```powershell
conda run -n goodq_core python -m cli.ucf_promotion reconcile-approve --epoch-id <epoch_id> --video-hash <video_hash>
```

**Execute Qdrant reconciliation**

```powershell
$env:GOODQ_CONFIRMATION_TOKEN = '<reconciliation_token>'
conda run -n goodq_core python -m cli.ucf_promotion reconcile-execute --epoch-id <epoch_id> --video-hash <video_hash>
Remove-Item Env:GOODQ_CONFIRMATION_TOKEN
```

Reconciliation retries only the exact pending Qdrant projection. It does not
repeat the lifecycle transition or materialization. The pending state clears
only after exact-video payloads are read back with the promoted status.

---

## Monitoring & Status

### `python -m cli.system_status`

**Purpose**
- quick health and environment snapshot

**Current Checks**
- Python and dependency availability
- config loadability
- configured directories
- recent ingest outputs from the current processing root

This command is a lightweight health surface, not a full readiness audit.

### `python -m cli.monitor_ingestion`

**Purpose**
- inspect the latest watchdog log and current processing directory state

**Current Truth**
- reads the runtime `log_dir`
- reads the runtime `processing` root
- does not launch new ingest work

### `python -m cli.print_config`

**Purpose**
- print sanitized resolved runtime configuration as operator JSON

**Usage**

```bash
python -m cli.print_config
```

This is the fastest way to verify the effective resolved profile/path surface before a run.
Secrets are always redacted, and stdout is valid JSON by default. Local path values are
tokenized for display unless `--include-local-values` is supplied; that option still
redacts all secret-bearing values. There is no supported raw-secret print mode.

### `python -m cli.control_recurrence_report`

**Purpose**
- read-only control recurrence and comparison report for operator observability

**Boundary**
- not healing yet
- does not activate or instantiate `ControlAgent`
- does not enable auto-healing
- does not mutate configs
- does not use LLMs
- does not alter or bypass `cli/run_ingestion.py`

**Truth Surfaces**
- `step_runs.jsonl`
- run warnings
- `scene_ingest_results.json`
- `scene_manifest.json`
- `temporal_index.json`
- `experiment_log.json`
- `operator_run_metadata.json` plus captured ingestion stdout/stderr events for direct canonical run roots that do not have a wrapper `experiment_log.json`; shared stdout events are scoped by persisted video/scene identity before recurrence aggregation

**Usage**

Single-run recurrence report:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness
```

Direct canonical run-root recurrence report:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root>
```

Comparison report as JSON:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --json
```

Markdown operator artifact using the default output directory:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --write-md
```

Markdown with an explicit output directory:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --output-dir reports/control_recurrence
```

Durable markdown + JSON artifacts and index update:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --write-json-file
```

List indexed recurrence artifacts:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports
```

List indexed recurrence artifacts as JSON:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json
```

Deterministic operator recommendation draft for an indexed durable report:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_182406_season2_fresh_witness
```

Recommendation draft as JSON:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness --json
```

Derived read-only trend over indexed durable JSON reports:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --trend --json
```

**Outputs**
- human-readable summary by default
- stable JSON with `--json`
- deterministic markdown with `--write-md`
- durable JSON artifact with `--write-json-file`
- durable artifact index at `reports/control_recurrence/index.json`
- deterministic read-only inspection draft with `--recommendations-for <report_id>`
- derived read-only trend summary with `--trend`
- default markdown path:
  - single run: `reports/control_recurrence/<run_id>.md`
  - comparison: `reports/control_recurrence/<baseline_run_id>__vs__<candidate_run_id>.md`
- default JSON artifact path:
  - single run: `reports/control_recurrence/<run_id>.json`
  - comparison: `reports/control_recurrence/<baseline_run_id>__vs__<candidate_run_id>.json`

**Current Truth**
- groups persisted recurrence signals by run, episode/video, step, status, reason, error family, scene, and recovery outcome
- classifies recurrence families as `informational`, `watch`, `actionable`, or `blocking`
- emits read-only operator hints and inspection targets
- indexes durable report artifacts for API/UI/Codex discovery without regenerating reports in list mode
- marks legacy markdown-only index entries explicitly with `artifact_status=markdown_only`
- supports direct canonical run roots with one or more videos, including metadata-described output/workspace paths
- drafts deterministic operator inspection steps from existing durable JSON reports without executing commands, healing, mutating configs, triggering ingestion, or generating reports
- derives conservative trends only from `reports/control_recurrence/index.json` and durable JSON artifacts referenced by that index
- reports Phase 6 and Qdrant health without inferring beyond persisted artifacts
- must apply the audio-vector provenance contract for CLAP/Qdrant coverage:
  current-run audio vector success requires `clap_meta.status == ok` plus a
  Qdrant audio payload with matching `run_id`; scene-id-only matches are not
  current-run proof

---

## Query & Retrieval

### `python -m cli.retrieve`

**Purpose**
- vector similarity retrieval across the active retrieval surfaces

**Usage**

```bash
python -m cli.retrieve "<search query>" [OPTIONS]
```

**Common Options**
- `--top-k`
- `--modality`
- `--threshold`

**Current Truth**
- Qdrant is canonical
- FAISS may participate only where configured as parity/fallback

### `python -m cli.nl_query`

**Purpose**
- natural-language query over the current memory/KG layer

**Usage**

```bash
python -m cli.nl_query "<question>"
```

This is a query helper surface, not a separate memory authority.

---

## Memory Commands

### `python -m cli.memory health-check`

Runs memory diagnostics against the active epoch `memory.db`.
If the legacy `lib.memory_management` package is absent, this command now fails visibly with an explicit compatibility message.

### `python -m cli.memory backup`

Creates a backup rooted at the configured `log_dir`.
If the legacy `lib.memory_management` package is absent, this command now fails visibly with an explicit compatibility message.

### `python -m cli.memory verify-schema`

Checks schema drift for the configured `db_path`.
If the legacy `lib.memory_management` package is absent, this command now fails visibly with an explicit compatibility message.

### `python -m cli.memory migrate`

Runs database migration on the configured `db_path`.
If the legacy `lib.memory_management` package is absent, this command now fails visibly with an explicit compatibility message.

### Additional Current Subcommands

The current `cli.memory` surface also includes:
- `seed-missing-assets`
- `rebuild-id-maps`
- `cleanup-seed-sentinels`
- `register-scene-bundle`

These are maintenance/support commands, not the primary user-facing memory flow.

---

## Utilities

### `python -m cli.list_inbox`

Lists inbox contents using the resolved config/runtime paths.

### `python -m cli.list_runs`

Retired compatibility shell.

Current truth:
- the old runtime-facing run index backing module is gone
- this command now fails visibly instead of pretending the surface still exists
- use persisted runtime artifacts or the active read-only API/runtime surfaces instead

### `python -m cli.test_ingestion`

Runs a smoke-style ingest validation.

### `python -m cli.step_runner`

Runs a single step in isolation for debugging or targeted validation.

This remains a debugging surface, not the orchestration owner.

---

## Configuration Truth

All CLI commands resolve runtime paths and behavior from `configs/config.yaml` plus environment overlays.

Important effective path families include:

```yaml
paths:
  import_inbox: ${GOODQ_DATA_ROOT}/GoodQ_Data/import_inbox
  processing: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/processing
  db_path: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/memory.db
  knowledge_graph_db: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/knowledge_graph.db
  log_dir: ${GOODQ_DATA_ROOT}/GoodQ_Data/epochs/<epoch>/logs
```

Qdrant remains the canonical vector endpoint:

```yaml
qdrant:
  enabled: true
  host: http://localhost:6333
```

---

## Verification Checklist

The CLI truth is healthy when:

1. `cli.run_ingestion` writes into the epoch tree.
2. `cli.system_status` can load config and inspect recent outputs.
3. `cli.monitor_ingestion` reads the active runtime log and processing roots.
4. `cli.print_config` reflects the effective resolved profile/path truth.
5. `cli.memory` subcommands operate against the configured epoch database paths.
6. `cli.control_recurrence_report` reads existing run artifacts without activating healing or mutating runtime state.
7. `cli.ucf_promotion inspect`, `approve`, and `execute` remain separate and
   reject a requested epoch that differs from the configured runtime epoch.
8. `cli.ucf_promotion reconcile-approve` and `reconcile-execute` remain separate,
   require a fresh exact-scope token, and operate only on a durable pending
   Qdrant projection.

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [INGEST_ORCHESTRATION_CONTRACT.md](../architecture/INGEST_ORCHESTRATION_CONTRACT.md)
- [WSL_AUDIO_RUNTIME.md](WSL_AUDIO_RUNTIME.md)
- [SCENE_MANIFEST_SPECIFICATION.md](../architecture/SCENE_MANIFEST_SPECIFICATION.md)

---

## Summary

The CLI layer is now centered on:
- one canonical ingest owner
- one separated, scope-bound UCF promotion and projection-recovery path
- deterministic monitoring/status helpers
- read-only control recurrence reporting
- query/retrieval helpers
- a focused memory maintenance surface

If a command is not present in `cli/`, it should not be described here as active operator truth.
