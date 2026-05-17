<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_POINTER -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# Documentation Forensics Index

This index is an operator lookup surface for documentation cleanup and future
repo forensics. It is not runtime authority and it does not replace
`docs/bootstrap/doc_authority_map.md`.

Use this file to answer:

- which docs are current authority vs historical context
- where likely drift or hidden project intelligence may live
- which relics are preserved because they may still explain old behavior
- what to inspect before moving, deleting, or promoting a document

## Clearance Status

As of this pass:

- every active Markdown/text doc under `docs/` has an explicit authority/status
  marker
- active docs lint clean for drive-root path leaks, mandatory-CUDA wording, and
  generated-snapshot authority conflicts
- changed-doc links resolved during the cleanup pass
- `docs/archive/` remains historical evidence, not active runtime authority
- local recurrence artifacts under `reports/control_recurrence/` remain
  workspace artifacts and are not documentation sources unless intentionally
  promoted
- local generated branding exports under `branding/*.html` and scratch payloads
  under `scratch/` remain workspace artifacts unless a release/demo surface
  intentionally promotes them

## Authority Lookups

Start here for current truth:

- documentation authority map:
  [`docs/bootstrap/doc_authority_map.md`](../../bootstrap/doc_authority_map.md)
- documentation authority policy:
  [`docs/bootstrap/doc_authority_policy.md`](../../bootstrap/doc_authority_policy.md)
- corpus/reference pack manifest:
  [`docs/bootstrap/CORPUS_PACK_MANIFEST.md`](../../bootstrap/CORPUS_PACK_MANIFEST.md)
- docs landing page:
  [`docs/README.md`](../../README.md)
- quick reference index:
  [`docs/reference/indexes/QUICK_INDEX.md`](QUICK_INDEX.md)

Do not use this file to override a canonical contract.

## High-Value Intel Buckets

### Current Runtime Contracts

These are current doctrine surfaces. Update them only when the runtime contract
changes:

- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/reference/WSL_AUDIO_RUNTIME.md`
- `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
- `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- `docs/architecture/components/VISION_PIPELINE.md`

### Offline Bundle And Corpus Routing

Use these before packaging, copying, deleting, or promoting offline assets:

- `docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md`
- `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- `docs/bootstrap/CORPUS_PACK_MANIFEST.md`
- `docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md`
- `docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md`
- `docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md`
- `docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md`

These docs classify runtime assets, optional dataset corpora, optional
reference-bank material, synthetic debug fixtures, generated witnesses, and
memory snapshots. Do not use local sample media or scaffold artifacts as product
memory or installer content unless a selected manifest explicitly allows it.

### Operator Status And Handoff

These are restart/operator surfaces. They may need refresh after validated
witnesses or bootstrap changes:

- `docs/HANDOFF_BASEMENT_PHASE.md`
- `docs/SYSTEM_SNAPSHOT.md`
- `docs/goodq4all_agent_status.md`
- `CHANGELOG.md`

### Preserved Relics With Possible Diagnostic Value

These are not current truth, but may reveal capability history or regression
expectations:

- `docs/archive/diagnostics/wsl2_audio_emotion_sample_output.json`
  - old WSL audio sample output with emotion scores, features, and embeddings
  - useful when comparing whether current WSL audio output is richer, poorer,
    or merely differently shaped
- `docs/technical/AUDIO_GPU_OPTIMIZATION.md`
- `docs/technical/AUDIO_GPU_QUICK_START.md`
- `docs/technical/VAD_IMPLEMENTATION_SUMMARY.md`
- `docs/technical/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md`
- `docs/guides/wsl2/PIPELINE_UPGRADE.md`
- `docs/guides/wsl2/WSL2_BENCHMARKS.md`

### Generated Snapshots

These can guide audits, but must not be treated as live authority without
rerunning or verifying the underlying surface:

- `docs/bootstrap/SCRIPT_REGISTRY.md`
- `docs/diagnostics/ENV_DISCOVERY_REPORT.md`
- `docs/diagnostics/ENV_RECONCILIATION_REPORT.md`
- `docs/diagnostics/LAUNCHER_PORTABILITY_DISCOVERY.md`
- `docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md`
- `docs/AGENT_CAPABILITIES.md`

### Historical Trap Docs

These names sound important, but they are historical/reference-only unless a
current canonical doc restates the claim:

- `docs/RUNTIME_AUTHORITY_MEMO.md`
- `docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md`
- `docs/architecture/AGENT_SYSTEM.md`
- `docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md`
- `docs/guides/llm/LLM_INTEGRATION_COMPLETE.md`
- `docs/technical/SESSION_SUMMARY_2025-12-05.md`
- `docs/WSL2_SCRIPTS_ADDED.md`
- `docs/WSL2_CONSISTENCY_AUDIT_DEC15.md`

## Cleanup Rules

When cleaning docs:

1. update or consult canonical contracts first
2. preserve historical evidence unless deletion is explicitly approved
3. prefer rebadging before moving
4. move only when the file is clearly historical and inbound links are repaired
5. never treat archive contents as current runtime truth
6. never add local machine paths or drive roots to active docs
7. do not create new task-completion docs for ordinary fixes

## Remaining Project-Root Watch Items

These are outside the docs-folder clearance and should be handled in separate
repo-root audits:

- tracked backup files beside active step modules
  - 2026-05-07 audit found and removed `17` tracked
    `steps/*/step.py.backup_*` siblings from the active tree after reference
    checks found no active runtime/test consumers
- root scene-detection config relic
  - 2026-05-07 audit found and removed the retired root `config.json`
    override plus obsolete fixer/monitor helper scripts after reference checks
    showed canonical runtime config is `configs/config.yaml`
- scratch/temp directories at repo root
  - 2026-05-07 audit found local scratch/workspace directories and added
    root-specific ignore rules; keep these as local artifacts unless a file is
    explicitly promoted
- legacy test and archive folders outside `docs/archive/`
- script registry entries classified as unclear/obsolete
  - 2026-05-07 audit found `docs/bootstrap/SCRIPT_REGISTRY.md` stale as a
    generated snapshot; use it as an audit aid, not execution authority
- source files with broad `except:` or placeholder `TODO` comments
  - next source seam is silent observability/provenance loss in observer,
    memory commit, retrieval event, provenance, API status, and audio helper
    paths
