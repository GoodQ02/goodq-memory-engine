# Season 1 Witness Release Bundle

Date: 2026-03-09

## Purpose

This directory is the curated, human-review-friendly release bundle for the formal Season 1 witness run.

It does **not** duplicate the full raw rerun workspace. Instead, it captures the high-signal snapshots needed to review the run without reopening the entire operational rerun directory.

Raw witness rerun source:

- `reports/seinfeld_experiment/reruns/20260308_season1_witness_run/`

Follow-up clean reliability validation source:

- `reports/seinfeld_experiment/reruns/20260309_235047_season1_reliability_rerun_v2/`

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

## 2026-03-10 Reliability Follow-Up

This bundle now also includes the clean full-season reliability rerun that verified the optional-step hardening pass:

- `reliability_validation_metrics_2026-03-10.json`
  - structural totals and optional-step status for the clean follow-up season run
- `reliability_validation_optional_status_2026-03-10.json`
  - the non-`ok` rows from the follow-up run, which are now only honest `sentiment` skips
- `reliability_validation_stderr_2026-03-10.log`
  - the tiny stderr record showing two recovered `conda run` retries for optional `sentiment`
- `resolved_config_snapshot_2026-03-10.json`
  - resolved runtime config copied from the clean reliability rerun
- `semantic_comparison_report_2026-03-10.md`
  - semantic readout covering recurring entities, scene clusters, cross-episode groups, and dialogue archetypes
- `semantic_comparison_metrics_2026-03-10.json`
  - structured metrics companion for the semantic report
- `scene_embedding_map_2d_2026-03-10.png` / `.svg`
  - fused 2-D embedding projection for all 185 scenes
- `scene_embedding_map_2d_labeled_2026-03-10.png` / `.svg`
  - labeled variant with anchor scenes and cross-episode group labels
- `scene_embedding_map_2d_2026-03-10.csv`
  - per-scene coordinates and lightweight metadata for downstream inspection
- `scene_embedding_map_2d_2026-03-10_metadata.json`
  - projection method, modality counts, and artifact paths

## Related Documents

- Witness record: `../../diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`
- Post-witness comparison pack: `../../diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`
- Experiment rollup: `../../diagnostics/experiment_summary.md`

## Review Notes

- The witness baseline is a clean-state rebuild from empty authoritative stores.
- The release bundle preserves the high-signal evidence needed for audit and future comparison without tracking the full raw stdout or the complete rerun tree in Git.
- The 2026-03-10 follow-up clean rerun confirmed `0` optional-step errors at season scale while preserving the same `185`-scene structural baseline.
- If deeper forensic review is needed later, start from `artifact_manifest.json` and the raw rerun source path above.
