<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CURATED_AUTHORITY_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-04-02 -->

# Documentation Authority Map

This file is a curated authority index for active documentation governance.
It is intentionally small and manually maintained.

It is not:
- a generated whole-repo snapshot
- an exhaustive list of every markdown file
- a substitute for file-level audits

Use this map to answer only these questions:
- Which docs are canonical authority right now?
- Which operational/index docs are safe to send operators to?
- Which historical docs still look active and must stay clearly quarantined?
- Which deletions have been explicitly approved as safe?

## Maintenance Rules

Update this file only when one of the following happens:
- a new canonical doc is introduced
- an active operator/index doc becomes authoritative enough to track here
- a formerly active doc is rebadged historical
- a deletion is explicitly approved as safe

Do not regenerate this file from a bulk scan.
Do not add archive/session/history material just for completeness.

## Canonical Authority Set

These documents define current runtime, architecture, identity, and operator truth.

### Root Canonical

- [AGENTS.md](../../AGENTS.md)
- [README.md](../../README.md)

### Runtime And Architecture Contracts

- [HANDOFF_BASEMENT_PHASE.md](../HANDOFF_BASEMENT_PHASE.md)
- [INGEST_ORCHESTRATION_CONTRACT.md](../architecture/INGEST_ORCHESTRATION_CONTRACT.md)
- [IDENTITY_STITCHING_CONTRACT.md](../architecture/IDENTITY_STITCHING_CONTRACT.md)
- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](../architecture/ARCHITECTURE_REFERENCE.md)
- [MEMORY_STORAGE.md](../architecture/MEMORY_STORAGE.md)
- [PHASE6_MULTIMODAL_FUSION.md](../PHASE6_MULTIMODAL_FUSION.md)
- [SCENE_MANIFEST_SPECIFICATION.md](../SCENE_MANIFEST_SPECIFICATION.md)
- [VISION_PIPELINE.md](../architecture/components/VISION_PIPELINE.md)
- [LIB_COMPONENTS.md](../technical/LIB_COMPONENTS.md)

### Runtime Operator Authority

- [WSL_AUDIO_RUNTIME.md](../reference/WSL_AUDIO_RUNTIME.md)
- [WATCHDOG_SYSTEM.md](../systems/WATCHDOG_SYSTEM.md)
- [CONTROL_AGENT.md](../CONTROL_AGENT.md)
- [CLI-REFERENCE.md](../CLI-REFERENCE.md)
- [goodq4all_agent_status.md](../goodq4all_agent_status.md)
- [SYSTEM_SNAPSHOT.md](../SYSTEM_SNAPSHOT.md)

### Documentation Governance Authority

- [doc_authority_policy.md](./doc_authority_policy.md)
- [doc_archive_plan.md](./doc_archive_plan.md)
- [doc_governance_summary.md](./doc_governance_summary.md)

## Operational Index Surfaces

These docs are safe discovery/index surfaces for humans and agents, but they do not override canonical contracts.

- [SCRIPT_REGISTRY.md](./SCRIPT_REGISTRY.md)
- [QUICK_INDEX.md](../reference/indexes/QUICK_INDEX.md)
- [AGENT_COMMS_INDEX.md](../reference/indexes/AGENT_COMMS_INDEX.md)
- [REPO_GROUNDED_CLEANUP_CHECKLIST.md](./REPO_GROUNDED_CLEANUP_CHECKLIST.md)

## Historical Trap Docs

These docs remain in the repo because they are useful historical records, but they must never be treated as current operator or runtime authority.

- [ARTIFACT_LOCATION_CONTRACT.md](../technical/ARTIFACT_LOCATION_CONTRACT.md)
- [PIPELINE_RESTORATION_BACKLOG.md](../technical/PIPELINE_RESTORATION_BACKLOG.md)
- [PHASE5_FINAL_ACTIVATION_SUMMARY.md](../technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md)
- [PIPELINES.md](../architecture/PIPELINES.md)

## Delete-Safe Registry

Only items listed here are approved for direct deletion without additional archive work.

Current approved delete-safe items:
- none

If a future cleanup approves deletion, record the file here before removal.

## Related Audit Tools

These tools support documentation verification, but they do not define authority by themselves.

- [doc_drift_lint.py](../../scripts/docs/doc_drift_lint.py)
- [runtime_path_authority_audit.py](../../scripts/docs/runtime_path_authority_audit.py)

## Non-Action Rules

- Do not expand this file into another full inventory snapshot.
- Do not use this file to classify every archive or session note.
- Do not cite this file to contradict a canonical contract.
- Do not add generated counts, entropy scores, or stale whole-repo metrics here.
