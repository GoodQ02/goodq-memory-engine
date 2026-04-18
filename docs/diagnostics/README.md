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

## High-Value Diagnostics

### Scene Context and Arbitration

- [`SCENE_CONTEXT_LLM_AUDIT_03x03_2026-04-11.md`](SCENE_CONTEXT_LLM_AUDIT_03x03_2026-04-11.md)
- [`SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md`](SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md)
- [`SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md`](SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md)
- [`SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md`](SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md)
- [`PERCEPTION_SURFACE_AUDIT_2026-04-09.md`](PERCEPTION_SURFACE_AUDIT_2026-04-09.md)
- [`SCENE_SUMMARIZER_AUDIT_2026-04-09.md`](SCENE_SUMMARIZER_AUDIT_2026-04-09.md)

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
