<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-17 -->

# Diagnostics Index

This folder preserves targeted audits, forensic reads, and environment
investigations.

## How To Use This Folder

Read diagnostics only after you have the current supported context from:

1. [`docs/releases/RELEASE_0.1.1.md`](../releases/RELEASE_0.1.1.md)
2. [`docs/goodq4all_agent_status.md`](../goodq4all_agent_status.md)
3. [`docs/SYSTEM_SNAPSHOT.md`](../SYSTEM_SNAPSHOT.md)

Diagnostics explain *why* a fix was made or *how* a seam was discovered. They
do not override the release checkpoint.

## Diagnostic Families

### Scene Context, Arbitration, and Eval

Current scene-context findings are summarized back into the current release and
runtime checkpoint documents:

- [`docs/releases/RELEASE_0.1.1.md`](../releases/RELEASE_0.1.1.md)
- [`docs/goodq4all_agent_status.md`](../goodq4all_agent_status.md)
- [`docs/SYSTEM_SNAPSHOT.md`](../SYSTEM_SNAPSHOT.md)
- [`reports/README.md`](../../reports/README.md)

Detailed forensic reads may exist in local operational history during active
repair loops, but the release surfaces above are the public summary of what is
currently proven.

### Environment and Portability

- [`ENV_DISCOVERY_REPORT.md`](ENV_DISCOVERY_REPORT.md)
- [`ENV_RECONCILIATION_REPORT.md`](ENV_RECONCILIATION_REPORT.md)
- [`HOST_COMPAT_DISCOVERY_REPORT.md`](HOST_COMPAT_DISCOVERY_REPORT.md)
- [`HOST_COMPAT_PATCH_NOTES.md`](HOST_COMPAT_PATCH_NOTES.md)
- [`LAUNCHER_PORTABILITY_DISCOVERY.md`](LAUNCHER_PORTABILITY_DISCOVERY.md)
- [`LAUNCHER_PORTABILITY_PATCH_NOTES.md`](LAUNCHER_PORTABILITY_PATCH_NOTES.md)

## Interpretation Rule

If a diagnostic appears to disagree with the current release surface, treat it
as historical context unless the agent status or system snapshot points back to
it explicitly.
