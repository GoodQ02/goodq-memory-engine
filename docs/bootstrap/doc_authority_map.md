<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CURATED_AUTHORITY_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->

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

These documents define intended runtime behavior, architecture, identity, and
operator contracts. They do not certify current runtime health.

### Root Canonical

- [AGENTS.md](../../AGENTS.md)
- [README.md](../../README.md)

### Runtime And Architecture Contracts

- [REPOSITORY_MAP.md](../architecture/REPOSITORY_MAP.md) - canonical source-navigation map; detailed behavior remains owned by the subsystem contracts below.
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
  topology, evidence boundaries and task-scoped resume guidance.
- [Agent office index](../agent/README.md) - agent entrypoint and reading order.
- [PROJECT.md](../../PROJECT.md) - current bounded checkpoint, evidence limits,
  and exact resume seam.
- [Ingestion failure modes](../reference/INGESTION_FAILURE_MODES.md) - distilled
  advisory lessons; not a list of confirmed current defects or an execution plan.
- [Captured agent state](../agent/CURRENT_STATE.md) - generated dated evidence
  or an explicitly unconfigured public template; pre-reset corpus captures are
  retired from current ingestion planning and are not startup reading.
- [Captured agent state JSON](../agent/current_state.json) - machine-readable
  projection of the same evidence or template. Verify time-sensitive claims
  against live evidence.
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

The October 13 reset retired pre-reset corpus reports across `reports/`,
`docs/diagnostics/`, archived diagnostics and the marked local run directories.
The subsequent approved archive pass moved 95 diagnostic Markdown reports,
14 tracked report documents and four completed/superseded plans under
`docs/archive/`, and extracted 619 lines of old run narratives from the roadmap.
Archive badges and repaired links preserve code-history access. Generated
snapshot inputs remain at the paths required by their existing consumers.
The generated [RAG context capture](../GOODQ_RAG_CONTEXT_PACK.md), agent state
projections and system snapshot retain historical evidence dates; their corpus
claims are retired regardless of an older authority badge inside the capture.
Their indexes and `RETIRED.md` markers define the boundary. The roadmap's retired
narratives and prior handoffs are code history, not current work orders. Source
contracts and regression tests retain their authority; report retirement does
not retire product requirements.

- `SCRIPT_REGISTRY.md` (omitted from public source)
- `HANDOFF_BASEMENT_PHASE.md` (omitted from public source)
- `ARTIFACT_LOCATION_CONTRACT.md` (omitted from public source)
- `PIPELINE_RESTORATION_BACKLOG.md` (omitted from public source)
- `PHASE5_FINAL_ACTIVATION_SUMMARY.md` (omitted from public source)
- `PIPELINES.md` (omitted from public source)
- `UCF_REMAINING_WORK.md` (omitted from public source)
- `UCF_SEARCH_LOOP_PLAN.md` (omitted from public source)
- `UCF_QDRANT_STATUS_BACKFILL_PLAN.md` (omitted from public source)
- `NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` (omitted from public source)
- `LLM_IMPLEMENTATION_PLAN_PHASE1.md` (omitted from public source)
- `AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` (omitted from public source)
- `DOCS_AUDIT_AND_REORGANIZATION_REPORT.md` (omitted from public source)
- `POST_PROMOTION_GRAPH_SIGNAL_NOISE_AUDIT.md` (omitted from public source)
- `UCF_CLEAN_REINGEST_VERIFICATION_REPORT_BASELINE.md` (omitted from public source)

## Delete-Safe Registry

Only items listed here are approved for direct deletion without additional archive work.

Approved instruction-only removals, 2026-11-06 (user-authorized instruction cleanup):
- `docs/agent/skills/using-agent-skills/SKILL.md`: obsolete generic skill chain;
  repository `AGENTS.md` owns proportional task selection.
- `docs/agent/skills/goodq4all-operator/SKILL.md`: duplicate skill-name stub;
  canonical discovery is `.agents/skills/goodq4all-operator/SKILL.md`.
- `docs/agent/skills/fable-prompt-cache/SKILL.md`: unreferenced session recipe
  whose scratch script is absent. No runtime implementation is removed.

These exact paths are retired, recoverable from Git history; this grants no
authority to remove adjacent data, source or historical evidence.

If a future cleanup approves deletion, record the file here before removal.

## Related Audit Tools

These tools support documentation verification, but they do not define authority by themselves.

- [doc_drift_lint.py](../../scripts/docs/doc_drift_lint.py)
- [doc_authority_lint.py](../../scripts/docs/doc_authority_lint.py)
- [runtime_path_authority_audit.py](../../scripts/docs/runtime_path_authority_audit.py)

## Non-Action Rules

Public releases may carry an explicit `unconfigured_template` evidence kind.
Its projections say that no runtime or corpus was observed; zero values are
placeholders. The generator rejects observed counts, healthy services, model
routes and historical receipts in this mode. Real runtime captures retain the
reachable loopback Qdrant requirement. A public template is never live authority.

- Do not expand this file into another full inventory snapshot.
- Do not use this file to classify every archive or session note.
- Do not cite this file to contradict a canonical contract.
- Do not add generated counts, entropy scores, or stale whole-repo metrics here.
