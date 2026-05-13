<!-- DOC_BADGE: RELEASE -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# Control Recurrence v0.5 Public Preview Alignment

## Verdict

Control Recurrence is code-backed on the public preview branch as a read-only
operational memory layer through the v0.4.2 report/index/recommendation
surface. The v0.5 trend surface is not live on this branch unless the running
tree contains `lib/control_recurrence_trend.py`, the `--trend` CLI flag, and
`GET /api/control-recurrence/reports/trend`.

The latest formal tag remains `control-recurrence-v0.4.2`. Development-line
work after that tag may add v0.5 trend behavior and related observer
hardening, but this public preview document must not be treated as proof that
those surfaces are mounted in the published build.

## What Is Finished

- Single-run and comparison recurrence reports over persisted run artifacts.
- Durable markdown and JSON report artifact writing when explicitly requested.
- `reports/control_recurrence/index.json` discovery and listing.
- Read-only API access to indexed reports, latest report, markdown content, and
  deterministic recommendation drafts.
- Deterministic operator recommendation drafts from existing durable JSON
  reports.
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
- expose trend mode unless the code files and routes named above are present
- touch `cli/run_ingestion.py`

## Current Commands

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports
curl http://127.0.0.1:30000/api/control-recurrence/reports/latest
```

## What Remains

- Porting or promoting the v0.5 trend implementation should be a separate
  release-management action with code, API route, CLI flag, and tests reviewed
  together.
- A formal `control-recurrence-v0.5.0` tag should only be made after that
  implementation is present on the release branch being tagged.
- UI work may consume the read-only API and CLI artifacts, but must not add
  action buttons, rerun controls, mutation controls, or hidden execution paths.
- Local untracked `reports/control_recurrence/` artifacts remain workspace
  evidence unless intentionally promoted.

This means the public preview recurrence layer can observe, index, compare, and
recommend inspection over existing reports, but it still has no hands. Trend
language should remain development-line or proposed unless the trend code is
present in the published branch.
