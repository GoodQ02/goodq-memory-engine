<!-- DOC_BADGE: DESIGN -->
<!-- DOC_STATUS: IMPLEMENTED_CONTRACT -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# Control Recurrence Trend Design

## Status And Scope

Status: implemented as a read-only derived trend contract.

This document defined the future read-only `control_recurrence_trend` layer.
That layer now exists in the active source as `lib/control_recurrence_trend.py`,
`python -m cli.control_recurrence_report --trend`, and
`GET /api/control-recurrence/reports/trend`.

The trend layer is a derived operator memory surface over existing control
recurrence artifacts. It must not become a second recurrence engine, a healing
system, an ingestion trigger, or a mutation-capable control plane.

The active implementation is source-complete for pre-UI consumption, but it is
not a new authority over recurrence truth. It derives only from
`reports/control_recurrence/index.json` and indexed durable JSON artifacts.
The latest formal control-recurrence tag remains `control-recurrence-v0.4.2`;
v0.5 trend behavior is documented in
[`CONTROL_RECURRENCE_v0.5_STATUS.md`](CONTROL_RECURRENCE_v0.5_STATUS.md).

## Purpose

The purpose is to help operators answer:

- Which recurrence families keep appearing?
- Are recurrence family counts increasing, decreasing, stable, new, or resolved?
- Is category severity moving across informational, watch, actionable, or blocking?
- Are recovered, unrecovered, skipped, or unknown outcomes changing over time?
- Did Phase 6 and Qdrant health remain stable across durable reports?
- What recommendation status and inspection hints were produced previously?

This is observer-only operator memory. It provides trend visibility, not
orders, remediation, execution, or automatic repair.

## Inputs

Allowed inputs:

- `reports/control_recurrence/index.json`
- durable JSON recurrence artifacts referenced by that index

Not allowed inputs:

- raw run roots
- `step_runs.jsonl`
- `scene_manifest.json`
- `temporal_index.json`
- generated markdown-only reconstruction
- fresh recurrence report generation

Markdown-only index entries may appear in a trend timeline as metadata-only
entries. They must not be reconstructed into fake recurrence trend data.

## Output Shape

The derived trend output uses stable top-level keys:

| Field | Purpose |
| --- | --- |
| `trend_report` | Metadata for the trend output: name, generated time, mode, source index, and read-only boundary. |
| `report_window` | Ordered report ids included in the trend window, plus counts for JSON-backed, markdown-only, malformed, skipped, and warning entries. |
| `report_timeline` | Timeline of report entries with report id, type, timestamp, artifact status, recommendation status, highest category, total signals, and health summaries. |
| `family_trends` | Derived trend rows per recurrence family. |
| `category_trends` | Derived movement for informational, watch, actionable, and blocking counts. |
| `recovery_trends` | Derived movement for recovered, unrecovered, skipped, and unknown counts. |
| `health_trends` | Phase 6 and Qdrant health continuity across comparable reports. |
| `recommendation_history` | Recommendation status, reasons, and highest category by report. |
| `scope_warnings` | Warnings about incomparable scope, missing scope data, markdown-only entries, malformed artifacts, or thin sample size. |
| `safety_boundary` | Explicit no-mutation, no-healing, no-ingestion, no-report-generation, no-ControlAgent boundary. |

### `family_trends`

Each family trend row should be derived only from existing recurrence JSON
fields such as `top_repeated_failure_families`,
`recurrence_classification.families`, and comparison-report deltas.

Suggested fields:

- `error_family`
- `scope_signature`
- `trend_status`
- `first_seen_report_id`
- `latest_seen_report_id`
- `report_count`
- `counts_by_report`
- `latest_count`
- `previous_count`
- `delta`
- `category`
- `recovery_outcomes`
- `inspection_targets`

Allowed `trend_status` values:

- `increased`
- `decreased`
- `stable`
- `new`
- `resolved`
- `insufficient_comparable_data`
- `timeline_only`

## Comparability Model

Trend claims require a conservative derived `scope_signature`. The signature
may be derived from existing report/index fields where available:

- `report_type`
- run roots from report scope
- `run_id`
- `baseline_run_id`
- `candidate_run_id`
- video identifiers
- episode identifiers
- report schema or policy version when present
- recurrence report kind: `single_run` or `comparison`
- artifact backing: JSON-backed or markdown-only

### Scope Rules

- Matching or similar `scope_signature` values are trendable.
- Different `scope_signature` values are timeline-only and must not be used for
  improvement or regression claims.
- Missing scope data produces a `limited_trendability` warning.
- Markdown-only entries are metadata-only timeline entries.
- Comparison reports may trend comparison deltas, but they should not be mixed
  directly with single-run report family counts unless the scope signature
  explicitly supports that view.

The `scope_signature` is derived. It is not a new canonical artifact field and
must be labeled as derived in any future output.

## Safety Boundary

The future trend layer must not:

- regenerate recurrence reports
- scan arbitrary run roots
- compare raw step logs
- read `step_runs.jsonl` directly
- trigger recommendation generation except deterministic in-memory summary from existing JSON
- mutate configs
- trigger ingestion
- activate or import `ControlAgent`
- enable healing
- write back to report artifacts
- write back to `reports/control_recurrence/index.json`

It may read the existing index and JSON artifacts referenced by that index. Any
written trend artifact, if added later, must be explicit operator output and
must not alter source recurrence artifacts.

## Operator Language Rules

The layer may say:

- `increased`
- `decreased`
- `stable`
- `new`
- `resolved`
- `insufficient comparable data`
- `timeline only`

The layer must not say:

- `improved`
- `regressed`
- `fixed`
- `healed`
- `safer`

Those stronger claims are allowed only when compared reports share a comparable
derived `scope_signature` and the specific claim is supported by existing JSON
fields. Even then, prefer the more precise trend language above.

## Implementation Shape

The active implementation follows this shape:

1. Load `reports/control_recurrence/index.json`.
2. Filter JSON-backed entries.
3. Preserve markdown-only entries as metadata-only timeline rows with warnings.
4. Load referenced JSON reports through narrow path-safe index resolution.
5. Derive `scope_signature` from existing report/index fields.
6. Group reports into comparable windows.
7. Compute trends only from existing JSON fields.
8. Emit a derived trend summary with `scope_warnings` and `safety_boundary`.
9. Never mutate source artifacts.

## Validation Expectations For Future Implementation

The implementation is expected to keep:

- unit tests with temp index and temp JSON fixtures
- markdown-only entry warning test
- incomparable scope warning test
- missing scope data warning test
- malformed JSON artifact warning test
- no raw run-root access test
- no direct `step_runs.jsonl` access test
- no report generation test
- no ControlAgent import test
- no mutation of index or source report artifacts test
- stable JSON shape test for the proposed output keys

## Design Summary

`control_recurrence_trend` should be the read-only memory layer over the
read-only recurrence layer. It may remember and compare what recurrence reports
already said. It must not rediscover, regenerate, repair, or act.
