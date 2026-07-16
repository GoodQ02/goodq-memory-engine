<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CURATED_AUTHORITY_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

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

- [INGEST_ORCHESTRATION_CONTRACT.md](../architecture/INGEST_ORCHESTRATION_CONTRACT.md)
- [IDENTITY_STITCHING_CONTRACT.md](../architecture/IDENTITY_STITCHING_CONTRACT.md)
- [HITL_STITCHING_CONTRACT.md](../architecture/HITL_STITCHING_CONTRACT.md)
- [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)
- [ARCHITECTURE_REFERENCE.md](../architecture/ARCHITECTURE_REFERENCE.md)
- [MEMORY_STORAGE.md](../architecture/MEMORY_STORAGE.md)
- [PHASE6_MULTIMODAL_FUSION.md](../architecture/PHASE6_MULTIMODAL_FUSION.md)
- [SCENE_MANIFEST_SPECIFICATION.md](../architecture/SCENE_MANIFEST_SPECIFICATION.md)
- [VISION_PIPELINE.md](../architecture/components/VISION_PIPELINE.md)
- [LIB_COMPONENTS.md](../technical/LIB_COMPONENTS.md)
- [CONFIG_LOADING_CONTRACT.md](../architecture/CONFIG_LOADING_CONTRACT.md)
- [SUMMARY_CONSOLE_CONTRACT.md](../architecture/SUMMARY_CONSOLE_CONTRACT.md)
- [TURBOQUANT_HYBRID_CACHING.md](../architecture/TURBOQUANT_HYBRID_CACHING.md)

### Read Model, Restraint, And Sensitive Source Contracts

- [EPISTEMIC_READ_MODEL.md](../architecture/EPISTEMIC_READ_MODEL.md)
- [NON_ACTION_CONTRACT.md](../architecture/NON_ACTION_CONTRACT.md)
- [VISUAL_PROJECTION_CONTRACT_v1.md](../architecture/VISUAL_PROJECTION_CONTRACT_v1.md)
- [CANONICAL_SENSITIVE_EVENTS.md](../architecture/CANONICAL_SENSITIVE_EVENTS.md)
- [VAULT_TOKEN_RESOLVER_CONTRACT.md](../architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md)
- [LLM_CLIENT_INJECTION_CONTRACT.md](../architecture/LLM_CLIENT_INJECTION_CONTRACT.md)

### Runtime And Operator Contracts

- [WSL_AUDIO_RUNTIME.md](../reference/WSL_AUDIO_RUNTIME.md)
- [WATCHDOG_SYSTEM.md](../systems/WATCHDOG_SYSTEM.md)
- [CONTROL_AGENT.md](../agent/CONTROL_AGENT.md)
- [CLI-REFERENCE.md](../reference/CLI-REFERENCE.md)

### Documentation Governance Authority

- [CORPUS_PACK_MANIFEST.md](./CORPUS_PACK_MANIFEST.md)
- [INSTALL_BOOTSTRAP.md](./INSTALL_BOOTSTRAP.md)
- [doc_authority_policy.md](./doc_authority_policy.md)
- [doc_archive_plan.md](./doc_archive_plan.md)
- [doc_governance_summary.md](./doc_governance_summary.md)

## Operational Index Surfaces

These docs are safe discovery/index surfaces for humans and agents, but they do not override canonical contracts.

- [PROJECT_ORIENTATION.md](../agent/PROJECT_ORIENTATION.md) - timeless project
  topology, evidence hierarchy, component boundaries, and no-repeat preflight.
- [Agent office index](../agent/README.md)
- [Agent current state](../agent/CURRENT_STATE.md) - transient restart snapshot;
  verify time-sensitive claims against live evidence.
- [Agent current state JSON](../agent/current_state.json) - machine-readable
  transient state mirror.
- [Clean memory start workflow](../agent/workflows/CLEAN_MEMORY_START.md)
- [goodq4all_agent_status.md](../goodq4all_agent_status.md) - compatibility
  redirect; it carries no independent status claims.
- [SYSTEM_SNAPSHOT.md](../SYSTEM_SNAPSHOT.md) - generated system snapshot, not
  timeless authority.
- [ROADMAP.md](../releases/ROADMAP.md)
- [USER_INTERFACE_WALKTHROUGH.md](../guides/ui/USER_INTERFACE_WALKTHROUGH.md)
- [AGENT_FILE_INDEX.md](../reference/indexes/AGENT_FILE_INDEX.md)
- [Codebase Python-module index](../codebase_index/README.md)
- [CORPUS_PACK_INVENTORY_LEDGER.md](./CORPUS_PACK_INVENTORY_LEDGER.md)
- [REFERENCE_PACK_V0_SELECTION_PROPOSAL.md](./REFERENCE_PACK_V0_SELECTION_PROPOSAL.md)
- [REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md](./REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md)
- [QUICK_INDEX.md](../reference/indexes/QUICK_INDEX.md)
- [DOCS_FORENSICS_INDEX.md](../reference/indexes/DOCS_FORENSICS_INDEX.md)
- [AGENT_COMMS_INDEX.md](../reference/indexes/AGENT_COMMS_INDEX.md)
- [REPO_GROUNDED_CLEANUP_CHECKLIST.md](./REPO_GROUNDED_CLEANUP_CHECKLIST.md)

## Historical Trap Docs

These docs remain in the repo because they are useful historical records, but they must never be treated as current operator or runtime authority.

- [SCRIPT_REGISTRY.md](../../archive/docs/bootstrap/SCRIPT_REGISTRY.md)
- [HANDOFF_BASEMENT_PHASE.md](../archive/HANDOFF_BASEMENT_PHASE.md)
- [ARTIFACT_LOCATION_CONTRACT.md](../archive/technical/ARTIFACT_LOCATION_CONTRACT.md)
- [PIPELINE_RESTORATION_BACKLOG.md](../archive/technical/PIPELINE_RESTORATION_BACKLOG.md)
- [PHASE5_FINAL_ACTIVATION_SUMMARY.md](../archive/technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md)
- [PIPELINES.md](../archive/architecture/PIPELINES.md)
- [UCF_REMAINING_WORK.md](../archive/agent/UCF_REMAINING_WORK.md)
- [UCF_SEARCH_LOOP_PLAN.md](../archive/agent/UCF_SEARCH_LOOP_PLAN.md)
- [UCF_QDRANT_STATUS_BACKFILL_PLAN.md](../archive/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md)
- [NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md](../archive/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md)
- [LLM_IMPLEMENTATION_PLAN_PHASE1.md](../archive/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md)
- [AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md](../archive/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md)
- [DOCS_AUDIT_AND_REORGANIZATION_REPORT.md](../archive/reports/DOCS_AUDIT_AND_REORGANIZATION_REPORT.md)
- [POST_PROMOTION_GRAPH_SIGNAL_NOISE_AUDIT.md](../archive/reports/POST_PROMOTION_GRAPH_SIGNAL_NOISE_AUDIT.md)
- [UCF_CLEAN_REINGEST_VERIFICATION_REPORT_BASELINE.md](../archive/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT_BASELINE.md)

## Delete-Safe Registry

Only items listed here are approved for direct deletion without additional archive work.

Current approved delete-safe items:
- none

If a future cleanup approves deletion, record the file here before removal.

## Related Audit Tools

These tools support documentation verification, but they do not define authority by themselves.

- [doc_drift_lint.py](../../scripts/docs/doc_drift_lint.py)
- [doc_authority_lint.py](../../scripts/docs/doc_authority_lint.py)
- [runtime_path_authority_audit.py](../../scripts/docs/runtime_path_authority_audit.py)

## Non-Action Rules

- Do not expand this file into another full inventory snapshot.
- Do not use this file to classify every archive or session note.
- Do not cite this file to contradict a canonical contract.
- Do not add generated counts, entropy scores, or stale whole-repo metrics here.
