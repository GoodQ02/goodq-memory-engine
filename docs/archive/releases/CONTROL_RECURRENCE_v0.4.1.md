<!-- DOC_BADGE: RELEASE -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-04-28 -->

# Control Recurrence v0.4.1

## Summary

`control-recurrence-v0.4.1` closes the direct-run map gap found during the
one-episode forensic sanity run after v0.4.0.

The recurrence reporter now understands two read-only run shapes:

- wrapper witness roots with root/per-episode `experiment_log.json`
- direct canonical `cli.run_ingestion` run roots with existing
  `output/scene_ingest_results.json`, `workspace/_resolved_config.json`,
  `operator_run_metadata.json`, canonical `step_runs.jsonl`, and captured
  ingestion stdout events

This is still observability only. It does not activate `ControlAgent`, enable
healing, mutate configs, execute commands, trigger ingestion, use LLMs, or
create a second orchestration path.

## What Changed

- Direct run roots without wrapper `experiment_log.json` are no longer reported
  as empty when their persisted output/workspace artifacts are present.
- Recovered native retry events captured in ingestion stdout can be surfaced as
  deterministic recurrence signals such as `native_crash_retry:0xC0000409`.
- Report path output is sanitized so durable artifacts do not expose local
  drive-root paths.
- Phase 6 harmonization now keeps `scene_manifest.json`, `temporal_index.json`,
  and final run output aligned on `phase5_complete`, scene counts, and
  `content_summary`.

## Commands

Wrapper witness run:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness
```

Direct canonical run root:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root>
```

Durable direct-run artifact:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root> --write-md --write-json-file
```

Recommendation draft after artifact indexing:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for <report_id>
```

## Validation

- `tests/unit/test_control_recurrence_report.py`
- `tests/unit/test_control_agent_disable_invariant.py`
- targeted Phase 6 content-summary/manifest alignment test
- `tests/unit/test_run_ingestion_content_state.py`
- real direct-run smoke against the v0.4.0 one-episode forensic run

## Boundary

This release completes the map; it does not give the map power. The canonical
ingestion owner remains `cli/run_ingestion.py`, and control recurrence remains a
read-only operator instrument.
