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

Public release artifacts document methodology and aggregate metrics only.
Copyrighted third-party reference anchors are not shipped in the public release.

See [`reports/reference_anchors/README.md`](reference_anchors/README.md) for the
public anchor boundary. Runtime scene truth is generated locally from
user-provided media, and public examples must use fictional, owned, synthetic,
or permissively licensed fixtures.

### Released Witness Evidence

The released, front-door proof surfaces are:

- [`docs/releases/RELEASE_0.1.1.md`](../docs/releases/RELEASE_0.1.1.md)
- [`docs/releases/SHIP_PROFILE.md`](../docs/releases/SHIP_PROFILE.md)
- [`docs/goodq4all_agent_status.md`](../docs/goodq4all_agent_status.md)
- [`docs/SYSTEM_SNAPSHOT.md`](../docs/SYSTEM_SNAPSHOT.md)

Those documents summarize the proving witness, current checkpoint, and what the
project is willing to claim publicly.

Public-safe reference-anchor policy lives here:

- [`reports/reference_anchors/README.md`](reference_anchors/README.md)

### Local Proving Runs

Local proving witnesses for active repair loops live under
`reports/fresh_ingest_runs/`.

Important:

- this path is intentionally treated as local operational history
- it may contain successful and failed witnesses from in-progress work
- the authoritative released outcome is always summarized back into the release
  and snapshot docs above

### Control Recurrence Outputs

Read-only control recurrence reports can be written under
`reports/control_recurrence/` for local operator inspection.

Important:

- generated recurrence markdown, JSON reports, and `index.json` are local
  workspace artifacts by default
- promote only deliberately selected, sanitized audit packs
- current source status belongs in
  [`docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md`](../docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md)
- public proof should use released summaries and public-safe methodology, not
  local generated recurrence artifacts by default

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
3. released methodology, aggregate metrics, and public-safe anchor policy
4. local witness history and older diagnostic families

That order keeps the repo outcome-forward while preserving the full evidence
trail behind it.
