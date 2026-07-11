<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: ../../releases/ROADMAP.md -->
<!-- DOC_ARCHIVED_ON: 2026-07-10 -->

# Documentation Audit & Reorganization Report

> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS

This report presents the complete inventory, deduping matrix, and path/link alignment details resulting from the documentation audit of v2.5.8-rc5.

## 1. Executive Summary

A comprehensive audit was performed across all documentation files inside the `docs/` tree. Literal Windows drive letter leaks were replaced with environment-relative path abstractions, broken relative links were repaired, redundant files were deleted, and historical legacy documentation was quarantined to `docs/archive/` using the automated script `scripts/reorganize_docs.ps1`.

- **Total Audited Files**: 258
- **Active / Canonical Files**: 165
- **Needs Update Files**: 25 (all drive paths abstracted and 66 relative links repaired)
- **Legacy / Historical Files**: 80 (moved to `docs/archive/` preserving folder structures)
- **Redundant / Obsolete Files**: 2 (deleted)

---

## 2. Deduping & Redundancy Matrix

The following table summarizes overlapping, duplicate, or conflicting instructions identified and resolved during the audit:

| Overlapping Filename / Topic | Overlapping Paths | Resolution & v2.5.8-rc5 Alignment |
| :--- | :--- | :--- |
| `clean_memory_start.md` | `docs/agent/workflows/CLEAN_MEMORY_START.md` <br> `docs/guides/CLEAN_MEMORY_START.md` | Keep `docs/agent/workflows/CLEAN_MEMORY_START.md` as the authoritative runbook. Cleaned up folder-up offset error in `docs/guides/CLEAN_MEMORY_START.md` to point properly to the runbook. |
| `install.md` | `docs/guides/general/INSTALL.md` <br> `docs/guides/install/INSTALL.md` | Deleted both variants as they are redundant. Manual Conda installation details are obsolete and fully superseded by `docs/bootstrap/INSTALL_BOOTSTRAP.md` (which covers the zero-dependency sandbox installer `GoodQ4All_Setup_2.5.8-rc5.exe`). |
| Installation Guides | `docs/guides/general/LAPTOP_INSTALL_GUIDE.md` <br> `docs/guides/install/LAPTOP.md` <br> `docs/guides/install/setup-windows.md` | Moved all to `docs/archive/` as they contain obsolete manual installation instructions. |
| WSL2 Audio Setup | `docs/guides/wsl2/START_HERE_WSL2.md` <br> `docs/guides/wsl2/test_pipeline.md` | Moved to `docs/archive/` as the canonical WSL2 audio runtime contract is now defined under `docs/reference/WSL_AUDIO_RUNTIME.md`. |
| GPU Setup | `docs/guides/gpu/GPU_SETUP.md` <br> `docs/guides/gpu/GPU_QUICK_START.md` | Archived redundant files. The authoritative source for GPU/VRAM isolation strategy and VRAM budgeting is `configs/models_config.yaml` and `docs/agent/CURRENT_STATE.md`. |
| Watchdog Guides | `docs/guides/watchdog/WATCHDOG_INDEX.md` <br> `docs/guides/watchdog/WATCHDOG_QUICKREF.md` | Archived redundant indices/quickrefs. `docs/systems/WATCHDOG_SYSTEM.md` remains the active system contract. |

---

## 3. Specific Content & Link Updates Performed

The following changes were applied to active / Needs Update files:

1. **Drive Path Abstractions**:
   - `docs/agent/CLEAN_FIRST_GO_INGESTION_MONITORING_REPORT.md` (Line 23): Replaced `L-drive:\_DATA\GoodQ_Data` with `<GOODQ_DATA_ROOT>\GoodQ_Data`.
   - `docs/agent/FORENSIC_THREE_SCENE_TRACE_AUDIT_76dedbe1b16c.md`: Replaced all absolute local paths (`L-drive:\_DATA\GoodQ_Data`, `L-drive:/_DATA/GoodQ_Data`, `C-drive:\Users\jdben\AppData\Local\Temp`, and `L-drive:\GOOD_CUBE\projects\goodq4all`) with appropriate `<GOODQ_DATA_ROOT>\GoodQ_Data`, `<temp_dir>`, and `<project_root>` abstractions.
   - `docs/codebase_index/README.md`: Replaced 1,100+ occurrences of absolute `file-protocol://L-drive/GOOD_CUBE/projects/goodq4all/` URLs with relative paths (`../../`).

2. **Relative Link Repairs**:
   - `docs/guides/CLEAN_MEMORY_START.md`: Repaired folder-up offset path `../../agent/workflows/CLEAN_MEMORY_START.md` to `../agent/workflows/CLEAN_MEMORY_START.md`.
   - `docs/architecture/PHASE6_MULTIMODAL_FUSION.md`: Standardized sibling links `architecture/SYSTEM_ARCHITECTURE.md`, `architecture/ARCHITECTURE_REFERENCE.md`, `architecture/IDENTITY_STITCHING_CONTRACT.md` to sibling files (`SYSTEM_ARCHITECTURE.md`, `ARCHITECTURE_REFERENCE.md`, `IDENTITY_STITCHING_CONTRACT.md`) and corrected references to the WSL audio contract as `../reference/WSL_AUDIO_RUNTIME.md`.
   - `docs/architecture/SCENE_MANIFEST_SPECIFICATION.md`: Corrected links to sibling files (`INGEST_ORCHESTRATION_CONTRACT.md`, `IDENTITY_STITCHING_CONTRACT.md`, `SYSTEM_ARCHITECTURE.md`) and sibling folder reference for `../reference/WSL_AUDIO_RUNTIME.md`.
   - `docs/reference/CLI-REFERENCE.md`: Corrected parent folder references (`../architecture/SYSTEM_ARCHITECTURE.md`, `../architecture/INGEST_ORCHESTRATION_CONTRACT.md`, `../architecture/SCENE_MANIFEST_SPECIFICATION.md`) and sibling `WSL_AUDIO_RUNTIME.md` link.
   - `docs/reference/indexes/GLOSSARY.md`: Normalized relative offsets to point to double folder-up paths (`../../systems/WATCHDOG_SYSTEM.md`, `../../guides/FIRST_RUN.md`, `../../guides/QDRANT_SETUP.md`).
   - `docs/reference/indexes/SUBSYSTEMS_INDEX.md`: Replaced dead diarization link with `[process_audio.py](../../wsl2_audio/process_audio.py)`.
   - `docs/reference/quick-refs/CHEAT_SHEET.md`: Corrected relative references to `../API.md`, `../indexes/QUICK_INDEX.md`, and updated LAUNCH_INSTRUCTIONS link to the archived path.
   - `docs/technical/MODEL_LOCKDOWN_QUICK_REF.md`: Updated `LOCKDOWN_STATUS.md` reference to the archived location `../../archive/docs/status-reports/LOCKDOWN_STATUS.md`.

3. **Victory Audit Link Alignment (2026-07-06)**:
   - A total of 66 broken relative links identified by the Victory Auditor's log were programmatically repaired across 25 active documentation and index files.
   - Relocated Targets: Links pointing to archived files (e.g., historical release notes, obsolete diagnostics, and deprecated guides) were updated relative to the source files to point to their new location inside `docs/archive/`.
   - Deleted Targets: Links pointing to deleted redundant files (e.g., manual installation guides) were redirected to the zero-dependency sandbox installer guide `docs/bootstrap/INSTALL_BOOTSTRAP.md` relative to the source files.
   - Active Replacements: Links with relative path offset errors pointing to active files (like `wsl2_audio/process_audio.py` or diarization/transcribe steps) were correctly aligned.

---

## 4. Reorganization Script & Verification

The reorganization was automated using `scripts/reorganize_docs.ps1`.
Verification was successfully performed using the documentation drift linter:
```powershell
conda run -n goodq_core python scripts/docs/doc_drift_lint.py
```
Output:
- Active drive path violations: **0**
- Active L-path violations: **0**
- Active ghost path violations: **0**
- Linter status: **PASS**

### Victory Audit Link Verification (2026-07-06)
Following the programmatic repair of the 66 broken relative links, the codebase was verified clean.
1. The Victory Auditor link status has been fully resolved (0 broken links).
2. The documentation drift linter was run:
```powershell
conda run -n goodq_core python scripts/docs/doc_drift_lint.py
```
Output:
- Active drive path violations: **0**
- Active L-path violations: **0**
- Active ghost path violations: **0**
- Linter status: **PASS** with zero violations.

---

## 5. Complete Audited Files Inventory

The table below lists all 258 audited documentation files, their metadata badges, mapped actions, and rationale:

| File Path | Status | Badge | Action Category | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `docs/AGENT_CAPABILITIES.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/GOODQ_RAG_CONTEXT_PACK.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/HANDOFF_BASEMENT_PHASE.md` | `SEALED_BASEMENT_RECORD` | `HISTORICAL` | **Legacy / Historical** | Listed in Historical Trap Docs in doc_authority_map.md |
| `docs/README.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/SYSTEM_SNAPSHOT.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/agent/CLEAN_FIRST_GO_INGESTION_MONITORING_REPORT.md` | `None` | `None` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/agent/CONTROL_AGENT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/agent/CURRENT_STATE.md` | `ACTIVE_AGENT_STATE` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/agent/FORENSIC_THREE_SCENE_TRACE_AUDIT_76dedbe1b16c.md` | `None` | `None` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/agent/GPU_ACCELERATED_INGESTION_WITNESS_REPORT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/GPU_WSL_INGESTION_MONITORING_REPORT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/README.md` | `ACTIVE_AGENT_OFFICE_INDEX` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/agent/RESILIENCE_AND_DEAD_CODE_RECONNECTION_REPORT.md` | `None` | `None` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT_BASELINE.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/agent/UCF_COVERAGE_GAP_REPORT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md` | `RESOLVED` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/UCF_REMAINING_WORK.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/UCF_SEARCH_LOOP_PLAN.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/skills/documentation-and-adrs/SKILL.md` | `None` | `None` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/agent/skills/fable-prompt-cache/SKILL.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/skills/goodq4all-audit/SKILL.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/skills/goodq4all-operator/SKILL.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/skills/using-agent-skills/SKILL.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/workflows/CLEAN_MEMORY_START.md` | `ACTIVE_RUNBOOK` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` | `ACTIVE_AGENT_WORKFLOW` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/agent/workflows/LAPTOP_TEST_AND_REPORT_PROTOCOL.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/agent/workflows/PIPELINE_TROUBLESHOOTING_FLOW.md` | `ACTIVE_AGENT_WORKFLOW` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/AGENT_DECISION_PROTOCOL.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/AGENT_SYSTEM.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/ARCHITECTURE_REFERENCE.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/CONFIG_LOADING_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/DATA_STRUCTURE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/DOCUMENTATION_REORGANIZATION_REPORT.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/EPISTEMIC_READ_MODEL.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/GOODQ_EXECPLAN_PROTOCOL.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/HITL_STITCHING_CONTRACT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/architecture/IDENTITY_STITCHING_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/INGESTION_PERFORMANCE_TIMINGS.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/LEGACY_WORKFLOWS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/LLM_CLIENT_INJECTION_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/MEMORY_STORAGE.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/NON_ACTION_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/OFFLINE_DEPENDENCIES.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/architecture/ORGANIZATION_COMPLETE_2025-11-15.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/OUTPUT_SCHEMA_INVENTORY.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/PHASE6_MULTIMODAL_FUSION.md` | `AUTHORITATIVE` | `CANONICAL` | **Needs Update** | Listed in Canonical Authority Set but contains drive letters or dead links |
| `docs/architecture/PIPELINES.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Legacy / Historical** | Listed in Historical Trap Docs in doc_authority_map.md |
| `docs/architecture/PORT_ARCHITECTURE_ASSESSMENT.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/architecture/PROJECT_STRUCTURE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/README.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/RUNTIME_AUTHORITY_MEMO.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/SCENE_MANIFEST_SPECIFICATION.md` | `AUTHORITATIVE` | `CANONICAL` | **Needs Update** | Listed in Canonical Authority Set but contains drive letters or dead links |
| `docs/architecture/SUMMARY_CONSOLE_CONTRACT.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/SYSTEM_MAP_v1.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/TURBOQUANT_HYBRID_CACHING.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/components/README.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/components/VISION_PIPELINE.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/architecture/data_epochs.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/diagrams/PIPELINE_FLOW.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/diagrams/README.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/diagrams/knowledge_graph_architecture.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/diagrams/watchdog_flow.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/architecture/narrative_layer.md` | `REFERENCE_ONLY` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md` | `INVENTORY` | `ACTIVE_LEDGER` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/bootstrap/CORPUS_PACK_MANIFEST.md` | `ACTIVE_MANIFEST` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/bootstrap/INSTALL_BOOTSTRAP.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md` | `ACTIVE_CONTRACT` | `OPERATIONAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md` | `ACTIVE_EXECPLAN` | `OPERATIONAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md` | `ACTIVE_CONTRACT` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md` | `DRAFT_REVIEW` | `REVIEW_MATRIX` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md` | `DRAFT_SELECTION` | `PROPOSAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md` | `SUPPORTING_EVIDENCE` | `EVIDENCE_APPENDIX` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/REPO_GROUNDED_CLEANUP_CHECKLIST.md` | `VERIFIED_CHECKLIST` | `OPERATIONAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/bootstrap/bootstrap_manifest.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/doc_archive_plan.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/bootstrap/doc_authority_map.md` | `CURATED_AUTHORITY_INDEX` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/doc_authority_policy.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/bootstrap/doc_governance_summary.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/bootstrap/doc_lint_ci_snippet.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/bootstrap/smoke_matrix_phase_a.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/codebase_index/README.md` | `None` | `None` | **Needs Update** | Codebase guide containing absolute file:// links with drive roots |
| `docs/codebase_index/codebase_health_audit.md` | `None` | `None` | **Active / Canonical** | Codebase index guide |
| `docs/diagnostics/ENV_DISCOVERY_REPORT.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/ENV_RECONCILIATION_REPORT.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/HOME_MEMORY_WITNESS_RUN_2026-05-22.md` | `WITNESS_RUN_SUMMARY` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/HOST_COMPAT_PATCH_NOTES.md` | `OPERATOR_NOTE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/LAUNCHER_PORTABILITY_DISCOVERY.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/LAUNCHER_PORTABILITY_PATCH_NOTES.md` | `OPERATOR_NOTE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/MEMORY_CLEAN_START_AUDIT_2026-05-20.md` | `CLEAN_START_AUDIT_SUMMARY` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/PERCEPTION_SURFACE_AUDIT_2026-04-09.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/POWER_LOSS_INGESTION_AUDIT_2026-05-20.md` | `ACTIVE_INCIDENT_AUDIT` | `DIAGNOSTIC` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/README.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x03_2026-04-11.md` | `OPERATOR_NOTE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md` | `OPERATOR_NOTE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/SCENE_SUMMARIZER_AUDIT_2026-04-09.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/WSL2_CONSISTENCY_AUDIT_DEC15.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/diagnostics/WSL2_SCRIPTS_ADDED.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Diagnostic run log / report |
| `docs/goodq4all_agent_status.md` | `GENERATED_SNAPSHOT` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/guides/CLEAN_MEMORY_START.md` | `ACTIVE` | `OPERATIONAL` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/guides/CONSOLIDATION_EXPLAINED.md` | `HISTORICAL_NOTE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/DEMO.md` | `GUIDE` | `None` | **Active / Canonical** | Default active doc |
| `docs/guides/FIRST_RUN.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/QDRANT_SETUP.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/SCENE_OPTIMIZATION_GUIDE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/general/API_DEBUG_INSTRUCTIONS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/GITHUB_SETUP_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/INSTALL.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Redundant / Obsolete** | Superseded by standalone setup installer bootstrap instructions |
| `docs/guides/general/LAPTOP_INSTALL_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/LAUNCH_INSTRUCTIONS.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/PRIVACY.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/PROCESS_MANAGEMENT_GUIDE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/PROCESS_MANAGER_QUICK_REFERENCE.md` | `HISTORICAL_POINTER` | `HISTORICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/PYTHON_PATH_CONFIGURATION.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/QUICK_START_CLEAN.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/QUICK_START_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/REMAINING_STEPS_AND_RUNTIME_TESTING.md` | `HISTORICAL_PLANNING_DRAFT` | `HISTORICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/SCRIPTS_GUIDE.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/TROUBLESHOOTING.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/general/USER_GUIDE.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/gpu/GPU_FIX_SUMMARY.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_ISOLATION_STRATEGY.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_LLM_WSL_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_MONITORING_COMPLETE.md` | `HISTORICAL_REFERENCE` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_PHASE_1_COMPLETE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_PHASE_1_TEST_RESULTS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_QUICK_START.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_REFACTOR_PROGRESS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_SCENE_DETECTION_IMPLEMENTATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/gpu/GPU_SETUP.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/install/INSTALL.md` | `AUTHORITATIVE` | `CANONICAL` | **Redundant / Obsolete** | Superseded by standalone setup installer bootstrap instructions |
| `docs/guides/install/LAPTOP.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/install/QUICKSTART.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/install/UNINSTALL.md` | `None` | `None` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/install/setup-linux.md` | `None` | `None` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/install/setup-macos.md` | `None` | `None` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/install/setup-windows.md` | `None` | `None` | **Legacy / Historical** | Superseded by zero-dependency standalone setup installer workflow |
| `docs/guides/llm/LLM_CLIENT_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/LLM_INFRASTRUCTURE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/LLM_INTEGRATION_ANALYSIS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/LLM_INTEGRATION_COMPLETE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/VLLM_WSL_INSTALL_VERIFY_2026-04-10.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/llm/WSL2_AUDIO_SETUP.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/ui/JUSTIFICATION_UI.md` | `ACTIVE_NOTE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/ui/USER_INTERFACE_WALKTHROUGH.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/guides/watchdog/WATCHDOG_CHANGELOG.md` | `REFERENCE_ONLY` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/watchdog/WATCHDOG_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/watchdog/WATCHDOG_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/watchdog/WATCHDOG_QUICKREF.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/PIPELINE_UPGRADE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/QUICK_REFERENCE_WSL2.md` | `HISTORICAL_POINTER` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/START_HERE_WSL2.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/WSL2_BENCHMARKS.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/guides/wsl2/test_pipeline.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/operator/OLLAMA_PORT_BOUNDARIES.md` | `None` | `None` | **Active / Canonical** | Default active doc |
| `docs/reference/API.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/CLI-REFERENCE.md` | `AUTHORITATIVE` | `CANONICAL` | **Needs Update** | Listed in Canonical Authority Set but contains drive letters or dead links |
| `docs/reference/DEPENDENCIES.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/reference/GPU_CAPABILITY_MATRIX.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/reference/PLATFORM_SUPPORT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/reference/WSL_AUDIO_RUNTIME.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/reference/indexes/AGENT_COMMS_INDEX.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/reference/indexes/AGENT_FILE_INDEX.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/reference/indexes/ANALYTICS_INDEX.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/indexes/CODE_CLEANUP_INDEX.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/reference/indexes/DOCS_FORENSICS_INDEX.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/reference/indexes/DOCUMENTATION_INDEX.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/indexes/ENVIRONMENT_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/indexes/GLOSSARY.md` | `ACTIVE` | `OPERATIONAL` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/reference/indexes/MASTER_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/indexes/QUICK_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Listed in Operational Index Surfaces |
| `docs/reference/indexes/SUBSYSTEMS_INDEX.md` | `AUTHORITATIVE` | `OPERATIONAL` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/reference/indexes/TROUBLESHOOTING_INDEX.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/quick-refs/CHEAT_SHEET.md` | `ACTIVE` | `OPERATIONAL` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/reference/quick-refs/CLI_COMMANDS_REFERENCE.md` | `ACTIVE_POINTER` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/quick-refs/QDRANT_QUICKREF.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/quick-refs/QUICK_REFERENCE.md` | `HISTORICAL_POINTER` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/reference/quick-refs/QUICK_REFERENCE_CARD.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/reference/quick-refs/QUICK_REFERENCE_SETTINGS.md` | `HISTORICAL_POINTER` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/releases/CONTROL_RECURRENCE_SHARED_RUNTIME_SCOPING_2026-05-03.md` | `OPERATOR_NOTE` | `RELEASE` | **Legacy / Historical** | Historical release notes |
| `docs/releases/CONTROL_RECURRENCE_TREND_DESIGN.md` | `IMPLEMENTED_CONTRACT` | `DESIGN` | **Legacy / Historical** | Historical release notes |
| `docs/releases/CONTROL_RECURRENCE_v0.4.0.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Historical release notes |
| `docs/releases/CONTROL_RECURRENCE_v0.4.1.md` | `OPERATOR_NOTE` | `RELEASE` | **Legacy / Historical** | Historical release notes |
| `docs/releases/CONTROL_RECURRENCE_v0.4.2.md` | `OPERATOR_NOTE` | `RELEASE` | **Legacy / Historical** | Historical release notes |
| `docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md` | `OPERATOR_NOTE` | `RELEASE` | **Active / Canonical** | Active release roadmap / status doc |
| `docs/releases/RELEASE_0.1.0.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical release notes |
| `docs/releases/RELEASE_0.1.1.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical release notes |
| `docs/releases/ROADMAP.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Active release roadmap / status doc |
| `docs/releases/SHIP_PROFILE.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical release notes |
| `docs/releases/VENDOR_PAYLOAD_EXIT_PLAN.md` | `ACTIVE_PLAN` | `OPERATIONAL` | **Legacy / Historical** | Historical release notes |
| `docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Historical implementation plan |
| `docs/superpowers/plans/2026-05-07-docs-root-forensics.md` | `REFERENCE_ONLY` | `OPERATIONAL` | **Legacy / Historical** | Historical implementation plan |
| `docs/superpowers/plans/2026-05-08-wsl-wav2vec-transformers-lane.md` | `QUALIFIED_PROOF_TRAIL` | `HISTORICAL` | **Legacy / Historical** | Historical implementation plan |
| `docs/superpowers/plans/2026-05-17-first-run-truth-closure.md` | `COMPLETE_EXECPLAN` | `OPERATIONAL` | **Legacy / Historical** | Historical implementation plan |
| `docs/superpowers/plans/2026-05-19-pipeline-surface-audit.md` | `None` | `None` | **Legacy / Historical** | Historical implementation plan |
| `docs/superpowers/plans/2026-05-20-agent-state-and-memory-clean-start.md` | `None` | `None` | **Legacy / Historical** | Historical implementation plan |
| `docs/systems/ERROR_HANDLING_RECOVERY.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/systems/WATCHDOG_SYSTEM.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/technical/ANALYTICS_PAGES_COMPLETE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/ANALYTICS_QUICK_REFERENCE.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/ARTIFACT_LOCATION_CONTRACT.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Listed in Historical Trap Docs in doc_authority_map.md |
| `docs/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/AUDIO_GPU_IMPLEMENTATION_SUMMARY.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/AUDIO_GPU_OPTIMIZATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/AUDIO_GPU_QUICK_START.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/AUDIO_VAD_OPTIMIZATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/DATA_FLOW_DIAGRAM.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/DEPENDENCY_ARCHITECTURE.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/FASTAPI_COMPATIBILITY_WALL.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/KNOWLEDGE_GRAPH_IMPLEMENTATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/LEGACY_PATHS_DEPRECATED.md` | `ACTIVE` | `OPERATIONAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/technical/LIB_COMPONENTS.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Listed in Canonical Authority Set |
| `docs/technical/LOGGING_AND_RESILIENCE.md` | `REFERENCE_ONLY` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/MODEL_LOCKDOWN.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/MODEL_LOCKDOWN_IMPLEMENTATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/MODEL_LOCKDOWN_QUICK_REF.md` | `ACTIVE_GUIDE` | `OPERATIONAL` | **Needs Update** | Active doc containing drive paths or dead links |
| `docs/technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md` | `IMPLEMENTATION_NOTE` | `HISTORICAL` | **Legacy / Historical** | Listed in Historical Trap Docs in doc_authority_map.md |
| `docs/technical/PIPELINE_DEEP_DIVE_REPORT.md` | `HISTORICAL_REFERENCE` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/PIPELINE_DIAGNOSIS_2025-11-11.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/PIPELINE_ENGINES_COMPLETE.md` | `HISTORICAL_REFERENCE` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/PIPELINE_ENGINES_UI_UPDATE.md` | `HISTORICAL_REFERENCE` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/PIPELINE_RESTORATION_BACKLOG.md` | `BACKLOG_REFERENCE` | `HISTORICAL` | **Legacy / Historical** | Listed in Historical Trap Docs in doc_authority_map.md |
| `docs/technical/SCENE_EXPLORER_DEPLOYMENT_GUIDE.md` | `HISTORICAL_REFERENCE` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/SECRETS_ENV_MIGRATION.md` | `REFERENCE_ONLY` | `OPERATIONAL` | **Active / Canonical** | Default active doc |
| `docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md` | `AUTHORITATIVE` | `CANONICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/SESSION_SUMMARY_2025-12-05.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Contains obsolescence keywords |
| `docs/technical/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/VAD_IMPLEMENTATION_SUMMARY.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/VISION_GPU_OPTIMIZATION.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/technical/knowledge_graph.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Active / Canonical** | Default active doc |
| `docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON1_MAIN_BENCHMARK_MEMO_2026-04-08.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON1_SEASON2_FORENSIC_COMPARISON_MEMO_2026-04-25.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON3_FIVE_EPISODE_RUNBOOK_2026-04-11.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/SEASON3_TREATMENT_LADDER_MEMO_2026-04-11.md` | `AUTHORITATIVE` | `CANONICAL` | **Legacy / Historical** | Historical test campaign / memo |
| `docs/testing/TESTING_GUIDE.md` | `ACTIVE` | `OPERATIONAL` | **Active / Canonical** | Active Testing Guide |
| `docs/testing/validation/run_narrative_validation.md` | `REFERENCE_ONLY` | `HISTORICAL` | **Legacy / Historical** | Historical test campaign / memo |
