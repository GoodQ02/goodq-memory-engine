<!-- DOC_BADGE: RELEASE -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-04-29 -->

# Control Recurrence v0.4.2

## Summary

`control-recurrence-v0.4.2` hardens the v0.4.1 direct-run map after the
post-seal gap audit.

This release is still read-only control recurrence observability. It does not
activate `ControlAgent`, enable healing, mutate configs, execute commands,
trigger ingestion, use LLMs, generate reports from the API, or create a second
execution path.

## Current State After Post-Seal Audit

- `control-recurrence-v0.4.1` remains the direct-run discoverability seal.
- `control-recurrence-v0.4.2` is the retry attribution and coalescing
  tightening pass.
- Current status is a read-only operational control room over existing
  recurrence artifacts.
- It is not self-healing and is not mutation-capable.
- The API does not trigger ingestion or generate recurrence reports.
- Bounded direct-run discovery limits are expected when required artifacts are
  absent; they are not control-plane boundary violations.
- Local `reports/control_recurrence/index.json` state is workspace artifact
  hygiene unless explicitly tracked.

## What Changed

- Direct canonical run roots with multiple videos now map one recurrence episode
  per `scene_ingest_results.json` item.
- Step-ledger signals prefer `video_id` before runtime `run_id`, avoiding
  cross-video attribution when multiple videos share one direct runtime run ID.
- Direct-run discovery falls back to `operator_run_metadata.json` output and
  workspace paths when standard `output/` or `workspace/` directories are not
  present.
- Recovered native retry signals can be read from captured stderr when stdout
  JSON events are unavailable.
- Duplicate recovered native retry signals are coalesced across run warnings,
  stdout runtime events, and stderr text.
- Markdown-only legacy index entries are now marked explicitly with
  `artifact_status=markdown_only` and an index warning instead of silently
  appearing as unknown complete reports.

## Commands

Direct run root:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root>
```

Durable direct-run artifact:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root> --write-md --write-json-file
```

List indexed artifacts:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json
```

## Validation

- `tests/unit/test_control_recurrence_report.py`
- `tests/unit/test_control_recurrence_recommendations.py`
- `tests/unit/test_control_recurrence_api.py`
- `tests/unit/test_control_agent_disable_invariant.py`
- `tests/unit/test_run_ingestion_content_state.py`
- targeted Phase 6 content-summary/manifest alignment test
- temp-only real direct-run smoke against the v0.4.0 one-episode forensic run

## Boundary

This release completes the read-only map hardening. The canonical ingestion
owner remains `cli/run_ingestion.py`, and the recurrence layer remains an
operator observability instrument only.
