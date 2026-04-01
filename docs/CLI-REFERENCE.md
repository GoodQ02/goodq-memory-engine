<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-01 -->

# GoodQ CLI Reference

**Last Updated:** April 1, 2026  
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

**Current Truth**
- owns orchestration
- writes epoch-scoped artifacts
- updates the KG in realtime
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
- print resolved runtime configuration as JSON

**Usage**

```bash
python -m cli.print_config
```

This is the fastest way to verify the effective resolved profile/path surface before a run.

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

### `python -m cli.memory backup`

Creates a backup rooted at the configured `log_dir`.

### `python -m cli.memory verify-schema`

Checks schema drift for the configured `db_path`.

### `python -m cli.memory migrate`

Runs database migration on the configured `db_path`.

### Additional Current Subcommands

The current `cli.memory` surface also includes:
- `seed-missing-assets`
- `rebuild-id-maps`
- `cleanup-placeholders`
- `register-scene-bundle`

These are maintenance/support commands, not the primary user-facing memory flow.

---

## Utilities

### `python -m cli.list_inbox`

Lists inbox contents using the resolved config/runtime paths.

### `python -m cli.list_runs`

Enumerates known runs/reruns from the runtime-facing run surfaces.

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

---

## Related Documentation

- [SYSTEM_ARCHITECTURE.md](architecture/SYSTEM_ARCHITECTURE.md)
- [INGEST_ORCHESTRATION_CONTRACT.md](architecture/INGEST_ORCHESTRATION_CONTRACT.md)
- [WSL_AUDIO_RUNTIME.md](reference/WSL_AUDIO_RUNTIME.md)
- [SCENE_MANIFEST_SPECIFICATION.md](SCENE_MANIFEST_SPECIFICATION.md)

---

## Summary

The CLI layer is now centered on:
- one canonical ingest owner
- deterministic monitoring/status helpers
- query/retrieval helpers
- a focused memory maintenance surface

If a command is not present in `cli/`, it should not be described here as active operator truth.
