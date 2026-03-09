# Season 1 Witness Release Bundle

Date: 2026-03-09

## Purpose

This directory is the curated, human-review-friendly release bundle for the formal Season 1 witness run.

It does **not** duplicate the full raw rerun workspace. Instead, it captures the high-signal snapshots needed to review the run without reopening the entire operational rerun directory.

Raw witness rerun source:

- `reports/seinfeld_experiment/reruns/20260308_season1_witness_run/`

## Included Snapshots

- `witness_metrics.json`
  - core run metrics, KG profile, Qdrant counts, optional failures, per-episode coverage
- `per_episode_coverage.csv`
  - compact episode-by-episode coverage table
- `optional_step_failures.json`
  - explicit non-`ok` optional failures from canonical `step_runs.jsonl`
- `retrieval_anchor_checks.json`
  - post-witness prompt spot checks against the live witness store
- `resolved_config_snapshot.json`
  - resolved runtime config copied from the witness rerun workspace
- `ingestion_stderr.log`
  - copied stderr stream from the witness rerun
- `artifact_manifest.json`
  - source-to-bundle mapping for this release snapshot

## Related Documents

- Witness record: `../../diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
- Post-witness comparison pack: `../../diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`
- Experiment rollup: `../../diagnostics/experiment_summary.md`

## Review Notes

- The witness baseline is a clean-state rebuild from empty authoritative stores.
- The release bundle preserves the high-signal evidence needed for audit and future comparison without tracking the full raw stdout or the complete rerun tree in Git.
- If deeper forensic review is needed later, start from `artifact_manifest.json` and the raw rerun source path above.
