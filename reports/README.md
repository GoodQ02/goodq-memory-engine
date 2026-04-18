<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-17 -->

# Reports and Evidence Map

This directory holds the evidence trail behind GoodQ4All release claims,
audits, and experiment history.

## Start Here

If you want the current supported outcome first, read these in order:

1. [`docs/releases/RELEASE_0.1.1.md`](../docs/releases/RELEASE_0.1.1.md)
2. [`docs/releases/SHIP_PROFILE.md`](../docs/releases/SHIP_PROFILE.md)
3. [`docs/goodq4all_agent_status.md`](../docs/goodq4all_agent_status.md)
4. [`docs/SYSTEM_SNAPSHOT.md`](../docs/SYSTEM_SNAPSHOT.md)

Use this `reports/` surface after the release/checkpoint docs above when you
need the underlying evidence path.

## Current Evidence Path

### Curated Reference Anchors

These are the release-tracked episode anchors used for offline evaluation:

- [`reports/reference_anchors/seinfeld/episodes/03x10_the_stranded.reference.json`](reference_anchors/seinfeld/episodes/03x10_the_stranded.reference.json)
- [`reports/reference_anchors/seinfeld/episodes/03x11_the_alternate_side.reference.json`](reference_anchors/seinfeld/episodes/03x11_the_alternate_side.reference.json)

They support the local episode-reference eval lane used for witness scoring and
audit. They are anchors, not runtime truth overrides.

### Released Witness Evidence

The repo-tracked witness bundle today is the Season 1 witness release:

- [`reports/seinfeld_experiment/README.md`](seinfeld_experiment/README.md)
- [`reports/seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md`](seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md)
- [`reports/seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md`](seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md)
- [`reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/README.md`](seinfeld_experiment/releases/season1_witness_run_2026-03-09/README.md)

These are the long-lived, repo-visible proof artifacts.

### Local Proving Runs

Local proving witnesses for active repair loops live under
`reports/fresh_ingest_runs/`.

Important:

- this path is intentionally treated as local operational history
- it may contain successful and failed witnesses from in-progress work
- the authoritative released outcome is always summarized back into the release
  and snapshot docs above

## Historical and Exploratory Families

These report families are useful for forensic work and backtracking, but they
are not the first thing to read for current truth:

- `reports/dino_*` - targeted repro investigations
- `reports/identity_control/` - identity-specific audit/control work
- `reports/seg_p5_*` and `reports/segmentation_shadow_*` - segmentation
  campaign and comparison history

Treat them as supporting historical evidence, not the current front door.

## Reading Rule

When deciding what is true **now**, prefer:

1. release and ship-profile docs
2. current agent status and system snapshot
3. tracked anchors and released witness artifacts
4. local witness history and older diagnostic families

That order keeps the repo outcome-forward while preserving the full evidence
trail behind it.
