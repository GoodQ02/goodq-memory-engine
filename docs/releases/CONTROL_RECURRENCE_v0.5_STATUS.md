<!-- DOC_BADGE: RELEASE -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# Control Recurrence v0.5 Source Status

## Verdict

Control Recurrence is source-complete as a read-only operational memory layer
for pre-UI use.

The latest formal tag remains `control-recurrence-v0.4.2`. The active source
after that tag adds v0.5 trend behavior and related observer hardening, but it
does not add healing, mutation, ingestion authority, or ControlAgent
activation.

## What Is Finished

- Single-run and comparison recurrence reports over persisted run artifacts.
- Durable markdown and JSON report artifact writing when explicitly requested.
- `reports/control_recurrence/index.json` discovery and listing.
- Read-only API access to indexed reports, latest report, markdown content, and
  deterministic recommendation drafts.
- Deterministic operator recommendation drafts from existing durable JSON
  reports.
- Conservative trend summaries from the recurrence index and indexed durable
  JSON reports only.
- Step latency summaries from existing `step_runs.jsonl` `duration_ms` rows.
- Optional enrichment coverage and environment summaries from existing
  recurrence input rows.
- Direct-run discovery and shared-runtime event scoping without creating a
  second ingestion path.
- Recovered native retry attribution and coalescing across persisted observer
  surfaces.

## Boundary

The recurrence layer remains read-only. It does not:

- activate or import `ControlAgent`
- enable healing
- mutate configs
- execute commands
- use LLMs
- trigger ingestion
- generate reports from the API
- scan raw run roots from trend mode
- reconstruct trend data from markdown-only artifacts
- touch `cli/run_ingestion.py`

## Current Commands

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --trend --json
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports
curl http://127.0.0.1:30000/api/control-recurrence/reports/latest
curl http://127.0.0.1:30000/api/control-recurrence/reports/trend
```

## What Remains

- A formal `control-recurrence-v0.5.0` tag is optional and should only be made
  as an explicit release-management action.
- UI work may consume the read-only API and CLI artifacts, but must not add
  action buttons, rerun controls, mutation controls, or hidden execution paths.
- Local untracked `reports/control_recurrence/` artifacts remain workspace
  evidence unless intentionally promoted.

This means the recurrence layer is done for the portability/bootstrap phase: it
can observe, index, compare, recommend inspection, and trend existing reports,
but it still has no hands.
