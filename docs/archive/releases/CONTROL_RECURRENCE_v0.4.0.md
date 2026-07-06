<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# Control Recurrence v0.4.0 Release Note

Tag: `control-recurrence-v0.4.0`

## Scope

Control Recurrence v0.4.0 adds deterministic recommendation drafts over
existing durable recurrence reports.

This is an operator inspection surface, not a healer, planner, or execution
engine.

## What Shipped

- `lib/control_recurrence_recommendations.py`
- CLI option: `--recommendations-for <report_id>`
- API endpoint: `GET /api/control-recurrence/reports/{report_id}/recommendations`
- Unit coverage for informational, watch, actionable, and blocking reports
- Path-traversal rejection coverage for report-id based recommendation fetches
- Status and operator docs updated with exact CLI/API examples

## Operator Output

Recommendation drafts include:

- `report_id`
- `recommendation_status`
- `highest_category`
- `blocking_summary`
- `top_operator_priorities`
- `inspection_plan`
- `defer_mutation_reason`
- `safety_boundary`

## Boundary

This release does not:

- activate or import `ControlAgent`
- enable healing
- mutate configs
- execute commands
- use LLMs
- generate reports from the API
- trigger ingestion
- touch `cli/run_ingestion.py`

Recommendations are deterministic read-only inspection steps derived from
already-written recurrence JSON artifacts under `reports/control_recurrence/`.

## Validation

- Focused recurrence/API/disable-invariant tests: `30 passed`
- Full unit suite on `main`: `410 passed`
- Real smoke against existing Season 1/Season 2 witness artifacts wrote a
  temporary single-run report, comparison report, JSON artifacts, markdown
  artifacts, and index, then generated CLI/API recommendation drafts.
- OpenAPI check confirmed all five `/api/control-recurrence` endpoints.
- Public branch focused recurrence/API/disable-invariant tests: `30 passed`

## Operator Examples

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness
```

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness --json
```

```powershell
curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/recommendations
```
