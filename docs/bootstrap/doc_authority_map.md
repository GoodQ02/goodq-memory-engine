<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Documentation Authority Map

Generated: 2026-02-11T22:50:35

This file is a generated inventory snapshot for documentation triage.
It does not supersede the canonical reading order in `AGENTS.md`, the
authority docs listed below, or direct file-level audits when entries drift.

## Scope

- Recursive scan: `docs/` plus root markdown/text docs.
- Total documents audited: **544**.

## Documentation Governance

- `docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md`
- `docs/technical/LEGACY_PATHS_DEPRECATED.md`
- `docs/bootstrap/doc_governance_summary.md`
- `scripts/docs/doc_drift_lint.py`

## Category Definitions

- **A) Canonical**: must be preserved and actively maintained as source-of-truth.
- **B) Operational**: setup/runbook/usage guides for operators and maintainers.
- **C) Historical**: release snapshots, status reports, milestone artifacts.
- **D) Experimental**: design notes, trial logs, working-session docs.
- **E) Redundant/Obsolete**: duplicate/backup/stale docs safe to retire.

## Entropy Summary

- **Doc entropy level:** **HIGH**
- Canonical (A): **20**
- Operational (B): **123**
- Historical (C): **248**
- Experimental (D): **152**
- Redundant/Obsolete (E): **1**

### Recommended Actions (count)

- ARCHIVE: **286**
- DELETE (safe): **1**
- KEEP: **112**
- MERGE: **102**
- REFRACTOR: **43**

## Phase A Drift Findings

- Docs contradicting Phase A profile semantics: **12**
- Docs with hardcoded `<drive>:/` or `<drive>:\` paths: **373**
- Docs implying CUDA/NVIDIA mandatory: **8**
- Duplicate install/start guides detected: **12**

### Contradictions (sample)

- `docs/reference/DEPENDENCIES.md`
- `docs/agent-comms/PHASED_SEGMENTATION_ENGINE_ANALYSIS_2025-12-04.md`
- `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- `docs/archive/README.md.backup_20251204`
- `docs/audits/ADVANCED_TACTICS_ANALYSIS.md`
- `docs/guides/CONSOLIDATION_EXPLAINED.md`
- `docs/guides/llm/WSL2_AUDIO_SETUP.md`
- `docs/releases/GPU_AND_PROCESS_CONTROL_SUMMARY.md`
- `docs/releases/SESSION_SUMMARY.md`
- `docs/reports/session_summaries/PR_SUMMARY.md`
- `docs/status-reports/ENVIRONMENT_CONSOLIDATION_COMPLETE.md`
- `docs/status-reports/GPU_STATUS_REPORT.md`

### Hardcoded L: paths (sample)

- `README.md`
- `docs/reference/DEPENDENCIES.md`
- `docs/CHEAT_SHEET.md`
- `docs/CLI-REFERENCE.md`
- `docs/CONTROL_AGENT.md`
- `docs/DOCUMENTATION_AUDIT_DEC15_2025.md`
- `docs/GITHUB_RELEASE_CHECKLIST.md`
- `docs/GITHUB_RELEASE_READY.md`
- `docs/OPERATIONAL_STATE_CHECKLIST.md`
- `docs/PHASE6B_COMPONENT_STATUS.md`
- `docs/PHASE6_MULTIMODAL_FUSION.md`
- `docs/QDRANT_QUICKREF.md`
- `docs/QUICK_START.md`
- `docs/RUNTIME_AUTHORITY_MEMO.md`
- `docs/SCENE_MANIFEST_SPECIFICATION.md`
- `docs/START_HERE.md`
- `docs/TESTING_GUIDE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/WSL2_COMPLETE_AUDIT_DEC15.md`
- `docs/WSL2_SCRIPTS_ADDED.md`
- `docs/agent-comms/ALL_ISSUES_RESOLVED.md`
- `docs/agent-comms/CLEANUP_SUMMARY.md`
- `docs/agent-comms/CLEANUP_VISUAL_GUIDE.txt`
- `docs/agent-comms/COMMIT_MESSAGE.md`
- `docs/agent-comms/COMMIT_MESSAGE_CORE_FIXES.md`
- `docs/agent-comms/COMMIT_SUCCESS.md`
- `docs/agent-comms/COMPREHENSIVE_AUDIT_COMPLETE.md`
- `docs/agent-comms/CONSOLIDATION_PLAN_ANALYSIS_2025-12-03.md`
- `docs/agent-comms/COPILOT_PROMPT_FOR_CMD.txt`
- `docs/agent-comms/CORE_FIXES_COMPLETE.md`
- `docs/agent-comms/DEDUPLICATION_COMPLETE.md`
- `docs/agent-comms/DIAGNOSIS_SUMMARY.md`
- `docs/agent-comms/FIXES_APPLIED.md`
- `docs/agent-comms/IMPLEMENTATION_COMPLETE.md`
- `docs/agent-comms/LAPTOP_ACTION_PLAN.md`
- `docs/agent-comms/MODEL_LOADING_FIXES.md`
- `docs/agent-comms/MORNING_CHECKLIST.md`
- `docs/agent-comms/NEXT_PHASE_WIRING_PLAN.md`
- `docs/agent-comms/NEXT_STEPS.md`
- `docs/agent-comms/OVERNIGHT_AUDIT_FINDINGS.md`
- `docs/agent-comms/OVERNIGHT_MONITOR.md`
- `docs/agent-comms/PHASE1_SEGMENTATION_COMPLETE_2025-12-04.md`
- `docs/agent-comms/PHASE4_COMPLETE_SUMMARY.md`
- `docs/agent-comms/PHASE5_IMPLEMENTATION_COMPLETE.md`
- `docs/agent-comms/PHASED_SEGMENTATION_ENGINE_ANALYSIS_2025-12-04.md`
- `docs/agent-comms/RECENT_FIXES.md`
- `docs/agent-comms/SCENE_DETECTION_BUG_FIXED.md`
- `docs/agent-comms/SESSION_COMPLETE_20251015.md`
- `docs/agent-comms/SESSION_SUMMARY.md`
- `docs/agent-comms/SESSION_SUMMARY_2025-10-18.md`
- `docs/agent-comms/TRANSCRIPTION_FIX_APPLIED.md`
- `docs/agent-comms/VALIDATION_AND_NEXT_STEPS.md`
- `docs/agent-comms/WATCHDOG_CLEANUP.md`
- `docs/architecture/AGENT_SYSTEM.md`
- `docs/architecture/ARCHITECTURE_REFERENCE.md`
- `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- `docs/architecture/DATA_STRUCTURE.md`
- `docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md`
- `docs/architecture/LEGACY_WORKFLOWS.md`
- `docs/architecture/MEMORY_STORAGE.md`
- `docs/architecture/ORGANIZATION_COMPLETE_2025-11-15.md`
- `docs/architecture/PORT_ARCHITECTURE_ASSESSMENT.md`
- `docs/architecture/PROJECT_ORGANIZATION_2025-11-19.md`
- `docs/architecture/PROJECT_ORGANIZATION_PHASE3_DATABASE_CONSOLIDATION.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/diagrams/PIPELINE_FLOW.md`
- `docs/archive/DEEP_PROJECT_EXPLORATION_2025-12-03.md`
- `docs/archive/EXPLORATION_SESSION_2025-12-03.md`
- `docs/archive/LOG_ANALYSIS_2025-12-03.md`
- `docs/archive/PROJECT_HISTORY.md`
- `docs/archive/QUICK_REFERENCE.txt`
- `docs/archive/README.md.backup_20251204`
- `docs/archive/_SESSION_FILES_CREATED.txt`
- `docs/archive/archived_docs/BUGFIX_HEREDOC.md`
- `docs/archive/archived_docs/COMPLETION_SUMMARY.md`
- `docs/archive/archived_docs/DOCUMENTATION_COMPLETE_2025-10-08.md`
- `docs/archive/archived_docs/DOCUMENTATION_ORGANIZATION.md`
- `docs/archive/archived_docs/ORGANIZATION_COMPLETE_SUMMARY.md`
- `docs/archive/archived_docs/ORGANIZATION_REPORT_20251010_225307.md`
- `docs/archive/archived_docs/POLISH_SUMMARY.md`
- ... and 293 more

### CUDA mandatory implications (sample)

- `docs/reference/DEPENDENCIES.md`
- `docs/agent-comms/PHASED_SEGMENTATION_ENGINE_ANALYSIS_2025-12-04.md`
- `docs/archive/README.md.backup_20251204`
- `docs/audits/ADVANCED_TACTICS_ANALYSIS.md`
- `docs/releases/GPU_AND_PROCESS_CONTROL_SUMMARY.md`
- `docs/releases/SESSION_SUMMARY.md`
- `docs/reports/session_summaries/PR_SUMMARY.md`
- `docs/status-reports/GPU_STATUS_REPORT.md`

### Duplicate install/start guides

- `docs/QUICK_START.md`
- `docs/START_HERE.md`
- `docs/agent-comms/START_HERE_AFTER_WORK.md`
- `docs/guides/general/INSTALL.md`
- `docs/guides/general/LAPTOP_INSTALL_GUIDE.md`
- `docs/guides/general/QUICK_START_CLEAN.md`
- `docs/guides/general/QUICK_START_GUIDE.md`
- `docs/guides/general/WATCHDOG_QUICKSTART.txt`
- `docs/guides/gpu/GPU_QUICK_START.md`
- `docs/guides/wsl2/START_HERE_WSL2.md`
- `docs/session-reports/PRIORITY_2_START_HERE_UPDATE_COMPLETE.md`
- `docs/technical/AUDIO_GPU_QUICK_START.md`

## Top 10 Highest-Risk Docs For Drift

| File | Risk Score | Why High Risk | Recommended Action |
| --- | --- | --- | --- |
| `docs/reference/DEPENDENCIES.md` | 11 | High-authority dependency contract surface; must stay aligned with portability and profile semantics. | KEEP |
| `docs/architecture/CONFIG_LOADING_CONTRACT.md` | 12 | Phase A semantic contradiction; hardcoded L: paths; high-authority surface | REFRACTOR |
| `docs/guides/CONSOLIDATION_EXPLAINED.md` | 12 | Phase A semantic contradiction; hardcoded L: paths; high-authority surface | REFRACTOR |
| `docs/guides/llm/WSL2_AUDIO_SETUP.md` | 12 | Phase A semantic contradiction; hardcoded L: paths; high-authority surface | REFRACTOR |
| `docs/archive/README.md.backup_20251204` | 10 | Phase A semantic contradiction; hardcoded L: paths | DELETE (safe) |
| `docs/agent-comms/PHASED_SEGMENTATION_ENGINE_ANALYSIS_2025-12-04.md` | 9 | Phase A semantic contradiction; hardcoded L: paths | ARCHIVE |
| `docs/audits/ADVANCED_TACTICS_ANALYSIS.md` | 9 | Phase A semantic contradiction | ARCHIVE |
| `docs/releases/GPU_AND_PROCESS_CONTROL_SUMMARY.md` | 9 | Phase A semantic contradiction; hardcoded L: paths | ARCHIVE |
| `docs/releases/SESSION_SUMMARY.md` | 9 | Phase A semantic contradiction; hardcoded L: paths | ARCHIVE |
| `docs/reports/session_summaries/PR_SUMMARY.md` | 9 | Phase A semantic contradiction | ARCHIVE |

## Proposed Archive Structure

```text
docs/archive/
  releases/                 # release snapshots, ship notes, deployment reports
  status-reports/           # dated status and system state snapshots
  session-reports/          # operator/agent session logs and handoff notes
  audits/                   # forensic audits and one-time diagnostics
  implementation-reports/   # phase implementation completion reports
  fix-reports/              # one-off fix verification documents
  agent-comms/              # conversational planning and interim execution notes
  project-history/          # historical migration/rename/change timeline
  backups/                  # *.md.backup* and derivative document copies
```

## Recommended Cleanup Plan

1. **Authority lock**: keep Canonical (A) in place; add explicit 'canonical' header badges to each A doc.
2. **Operational normalization**: refactor B docs that conflict with Phase A (profile semantics, paths, CUDA optionality).
3. **Install guide consolidation**: merge duplicate install/quickstart/start_here docs into one canonical install + one quickstart.
4. **Historical relocation**: move C docs into `docs/archive/` structure without rewriting content.
5. **Experimental triage**: merge useful D docs into canonical/operational targets; archive the rest.
6. **Obsolete pruning**: remove E backup/duplicate files after one verification pass and git history confirmation.
7. **Drift gate**: add CI lint to flag new docs with hardcoded `<drive>:/` paths or mandatory CUDA wording outside GPU-specific guides.

## Authority Map

| File Path | Category | Rationale | Action Recommendation |
| --- | --- | --- | --- |
| `AGENTS.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `CODE_OF_CONDUCT.md` | B) Operational | Repository governance/operational contribution policy. | KEEP |
| `CONTRIBUTING.md` | B) Operational | Repository governance/operational contribution policy. | KEEP |
| `README.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/reference/DEPENDENCIES.md` | A) Canonical | Declared runtime/contract authority document moved under the reference surface. | KEEP |
| `docs/AGENT_CAPABILITIES.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/AUDIT_SUMMARY_QUICK.txt` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/CHEAT_SHEET.md` | B) Operational | Current command-first cheat sheet for the supported runtime surface. | KEEP |
| `docs/CLI-REFERENCE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/CONTROL_AGENT.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/DEPLOYMENT_SUCCESS_v2.0.0.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/DOCUMENTATION_AUDIT_DEC15_2025.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/GITHUB_RELEASE_CHECKLIST.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/GITHUB_RELEASE_READY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/HANDOFF_BASEMENT_PHASE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/README.md` | B) Operational | Current documentation landing page for active surfaces and archive boundaries. | KEEP |
| `docs/OPERATIONAL_STATE_CHECKLIST.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/PHASE6B_COMPONENT_STATUS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/PHASE6_MULTIMODAL_FUSION.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/QDRANT_QUICKREF.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/QUICK_START.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/ROADMAP.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/RUNTIME_AUTHORITY_MEMO.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/SCENE_MANIFEST_SPECIFICATION.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/SESSION_COMPLETE_WSL2_AUDIT.txt` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/START_HERE.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/SYSTEM_SNAPSHOT.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/TESTING_GUIDE.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/TROUBLESHOOTING.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/WSL2_COMPLETE_AUDIT_DEC15.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/WSL2_CONSISTENCY_AUDIT_DEC15.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/WSL2_SCRIPTS_ADDED.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/agent-comms/ALL_ISSUES_RESOLVED.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/AUDIT_CHECKLIST.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/AUDIT_INDEX.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/CLEANUP_SUMMARY.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/CLEANUP_VISUAL_GUIDE.txt` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMMIT_MESSAGE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMMIT_MESSAGE_CORE_FIXES.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMMIT_MESSAGE_v1.3.0.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMMIT_SUCCESS.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMMIT_SUCCESS_v1.3.0.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMPREHENSIVE_AUDIT_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COMPREHENSIVE_ENHANCEMENT_PLAN.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/CONSOLIDATION_PLAN_ANALYSIS_2025-12-03.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/COPILOT_PROMPT_FOR_CMD.txt` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/CORE_FIXES_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/Context Engineering - Short-Term Memory Management with Sessions from OpenAI Agents SDK.txt` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/DEDUPLICATION_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/DIAGNOSIS_SUMMARY.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/FIXES_APPLIED.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/IMPLEMENTATION_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/LAPTOP_ACTION_PLAN.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/LINT_CLEAN_SESSION.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/MODEL_LOADING_FIXES.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/MORNING_BRIEFING.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/MORNING_CHECKLIST.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/NEXT_PHASE_WIRING_PLAN.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/NEXT_STEPS.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OPTION_C_IMPLEMENTATION_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_AUDIT_FINDINGS.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_AUDIT_SUMMARY.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_DELIVERABLES_README.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_INDEX.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_MONITOR.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_MONITORING_REPORT.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/OVERNIGHT_WORK_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/PHASE1_SEGMENTATION_COMPLETE_2025-12-04.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/PHASE4_COMPLETE_SUMMARY.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/PHASE5_IMPLEMENTATION_COMPLETE.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/PHASED_SEGMENTATION_ENGINE_ANALYSIS_2025-12-04.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/README.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/RECENT_FIXES.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/SCENE_DETECTION_BUG_FIXED.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/SESSION_COMPLETE.txt` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/SESSION_COMPLETE_20251015.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/SESSION_SUMMARY.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/SESSION_SUMMARY_2025-10-18.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/START_HERE_AFTER_WORK.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/TRANSCRIPTION_FIX_APPLIED.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/VALIDATION_AND_NEXT_STEPS.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/WATCHDOG_CLEANUP.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/agent-comms/WELCOME_BACK.md` | D) Experimental | Agent session notes and transient planning artifacts. | ARCHIVE |
| `docs/architecture/AGENT_SYSTEM.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/ARCHITECTURE_REFERENCE.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/CONFIG_LOADING_CONTRACT.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/DATA_STRUCTURE.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/architecture/DOCUMENTATION_REORGANIZATION_REPORT.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/architecture/EPISTEMIC_READ_MODEL.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/LEGACY_WORKFLOWS.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/LLM_CLIENT_INJECTION_CONTRACT.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/MEMORY_STORAGE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/architecture/NON_ACTION_CONTRACT.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/ORGANIZATION_COMPLETE_2025-11-15.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/architecture/PIPELINES.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/PORT_ARCHITECTURE_ASSESSMENT.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/PROJECT_ORGANIZATION_2025-11-19.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/PROJECT_ORGANIZATION_PHASE3_DATABASE_CONSOLIDATION.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/PROJECT_STRUCTURE.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/architecture/SYSTEM_MAP_v1.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/diagrams/PIPELINE_FLOW.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/architecture/diagrams/knowledge_graph_architecture.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/diagrams/watchdog_flow.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/architecture/narrative_layer.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/archive/DEEP_PROJECT_EXPLORATION_2025-12-03.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/EXPLORATION_SESSION_2025-12-03.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/FIXES_QUICK_REFERENCE.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/LOG_ANALYSIS_2025-12-03.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/PROJECT_HISTORY.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/QUICK_REFERENCE.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/README.md.backup_20251204` | E) Redundant/Obsolete | Backup/derivative copy not suitable as live authority. | DELETE (safe) |
| `docs/archive/_SESSION_FILES_CREATED.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/BUGFIX_HEREDOC.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/COMMAND_CENTER_SUCCESS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/COMPLETION_SUMMARY.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/DOCUMENTATION_COMPLETE_2025-10-08.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/DOCUMENTATION_ORGANIZATION.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/ORGANIZATION_COMPLETE_SUMMARY.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/ORGANIZATION_REPORT_20251010_225307.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/POLISH_SUMMARY.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/PROJECT_ORGANIZATION_COMPLETE.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/REORGANIZATION_COMPLETE.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/REORGANIZATION_SUMMARY.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/archived_docs/WHERE CODEX LEFT OFF.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/server_info.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/GPU_OPTIMIZATION_SESSION_REPORT.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/INDEX.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/SESSION_REPORT_Nov8_2025.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/SESSION_SUMMARY_2025-10-17.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/SESSION_SUMMARY_2025-11-12.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/SESSION_SUMMARY_2025-11-13_GPU_SCENE_DETECTION.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/session_summaries_archive/SESSION_SUMMARY_20251010.txt` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/COMPLETION_STATUS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/CURRENT_SYSTEM_STATUS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/FINAL_SYSTEM_STATUS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/INDEX.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/PRODUCTION_STATUS_2025-11-09.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/PRODUCTION_SYSTEM_STATUS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/PRODUCTION_TEST_FINDINGS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/PRODUCTION_TEST_REPORT.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/STATUS.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/SYSTEM_LIVE_REPORT.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/SYSTEM_OPERATIONAL_REPORT.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/archive/status_reports_archive/SYSTEM_STATUS_REPORT.md` | C) Historical | Already archival/historical material. | ARCHIVE |
| `docs/audits/ADVANCED_TACTICS_ANALYSIS.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/AUDIO_PIPELINE_ANALYSIS.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/AUDIT_COMPLETE.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/AUDIT_INDEX.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/AUDIT_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/AUDIT_RESOLUTION_2025-12-16.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/CLEAN_RUN_TEST_REPORT_2025-11-07.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPLETE_AUDIT_SUMMARY.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPREHENSIVE_ARCHITECTURE_RESEARCH_2025-11-15.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPREHENSIVE_AUDIT_SUCCESS_REPORT_2025-11-09.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPREHENSIVE_DIAGNOSTIC_2025-10-17.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPREHENSIVE_DIAGNOSTIC_REPORT_2025-11-07.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/COMPREHENSIVE_PROJECT_ANALYSIS_2025-11-07.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/CONTEXT_CHECKPOINT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/FINAL_RETEST_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/FULL_RETEST_DIAGNOSTIC_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/HEALTH_CHECK_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/INTERFACE_READY_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/LAPTOP_TEST_CHECKLIST.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/LAUNCHER_AUDIT_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/LAUNCH_AUDIT_COMPLETE.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/LAUNCH_SCRIPTS_AUDIT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/L_DRIVE_ARCHITECTURE_AUDIT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/PRE_EMBEDDING_STRATEGY_ANALYSIS.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/RELEASE_CHECKLIST.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SAMPLE_MP4_ANALYSIS_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SANITY_CHECK_STRUCTURE.txt` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SCENE_ANALYSIS_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SCRIPT_AUDIT_REPORT_2025-11-07.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SYSTEM_AUDIT_REPORT.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/SYSTEM_DIAGNOSTIC_REPORT.txt` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/TECHNICAL_FINDINGS.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/TEST_REPORT_PHASE_1-6.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/TROUBLESHOOTING_EMPTY_ANALYSIS.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/UI_AUDIT_REPORT_2025-11-15.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/audits/VISION_TESTING_CHECKLIST.md` | C) Historical | Audit snapshot; preserve as evidence, not live authority. | ARCHIVE |
| `docs/bootstrap/bootstrap_manifest.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/bootstrap/doc_authority_map.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/bootstrap/smoke_matrix_phase_a.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/components/VISION_PIPELINE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/data_epochs.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/diagnostics/TEST_RESULTS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/diagnostics/VLLM_AND_INGESTION_STATUS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/fix-reports/AUDIO_DIARIZATION_COMPLETE_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/AUDIO_DIARIZATION_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/CRITICAL_FIXES_APPLIED.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/CRITICAL_FIX_APPLIED.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/ENTITY_EXTRACTION_FIX_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/FIXES_APPLIED_2025-10-17.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/HUGGINGFACE_COMPLETE_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/IMMEDIATE_FIXES.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/MISSING_DEPS_QUICK_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/OOM_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/OPENCV_MISSING_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/PERFORMANCE_FIXES.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/PHASE4_EMOTION_DETECTION_FIXES.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/PHASE5_CRITICAL_FINDINGS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/PHASE_ABC_SURGICAL_FIX_2025-12-13.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/PYTHON_PATH_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_CONFIG_FIX_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_DETECTION_FIX_2025-10-13.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_DETECTION_FIX_APPLIED.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_DETECTION_FIX_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_DETECTION_FIX_COMPLETE_2025-11-09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_DETECTION_FIX_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SCENE_SUMMARIZATION_FIX_PLAN.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SENTIMENT_TIMEOUT_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SILENT_FAILURE_FIX_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/SURGICAL_FIX_COMPLETE_2025-12-13.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/WEB_INTERFACE_FIX_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/fix-reports/WSL2_AUDIO_FIX_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/goodq4all_agent_status.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/guides/CONSOLIDATION_EXPLAINED.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/QDRANT_SETUP.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/SCENE_OPTIMIZATION_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/API_DEBUG_INSTRUCTIONS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/COMMAND_CENTER_LIVE.md` | C) Historical | Historical implementation note for a still-supported feature whose backend details moved into the canonical API surface. | KEEP |
| `docs/guides/general/CONTROL_AGENT_PHASE1.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/CONTROL_AGENT_PHASE3.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/GITHUB_SETUP_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/INSTALL.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/general/LAPTOP_INSTALL_GUIDE.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/general/LAUNCH_INSTRUCTIONS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/PROCESS_MANAGEMENT_GUIDE.md` | C) Historical | Historical retirement marker for the removed process-manager surface. | KEEP |
| `docs/guides/general/PROCESS_MANAGER_QUICK_REFERENCE.md` | C) Historical | Historical retirement marker for the removed process-manager surface. | KEEP |
| `docs/guides/general/PYTHON_PATH_CONFIGURATION.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/QUICK_START_CLEAN.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/general/QUICK_START_GUIDE.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/general/REMAINING_STEPS_AND_RUNTIME_TESTING.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/RESTART_API_INSTRUCTIONS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/SCRIPTS_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/USER_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/general/WATCHDOG_QUICKSTART.txt` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/gpu/GPU_CONFIGURATION_REPORT.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_DIAGNOSTIC_REPORT.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_FIX_SUMMARY.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_ISOLATION_STRATEGY.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_LLM_WSL_INDEX.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_MONITORING_COMPLETE.md` | C) Historical | Historical implementation report for the retired process-manager/API-monolith stack. | KEEP |
| `docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_PHASE_1_COMPLETE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_PHASE_1_TEST_RESULTS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_QUICK_START.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/gpu/GPU_REFACTOR_PROGRESS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_SCENE_DETECTION_IMPLEMENTATION.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/gpu/GPU_SETUP.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/LLM_CLIENT_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/LLM_INFRASTRUCTURE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/LLM_INTEGRATION_ANALYSIS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/LLM_INTEGRATION_COMPLETE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/PHASE2_WSL2_COMPLETE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/PHASE3_LLM_INTEGRATION_COMPLETE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/VLLM_INTEGRATION_PLAN.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/WSL2_AUDIO_MIGRATION_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/llm/WSL2_AUDIO_SETUP.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/archive/proof_of_concept/ui/UI_ALIGNMENT_AUDIT.md` | C) Historical | Archived UI audit artifact from the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_AUDIT_COMPLETE.md` | C) Historical | Archived UI audit artifact from the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_AUDIT_REPORT.md` | C) Historical | Archived UI audit artifact from the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_AUDIT_SUMMARY.md` | C) Historical | Archived UI audit artifact from the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_CONNECTION_GUIDE.md` | C) Historical | Archived UI rollout note for the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_FIXES_COMPLETED.txt` | C) Historical | Archived UI rollout note for the retired scaffolded interface. | KEEP |
| `docs/archive/proof_of_concept/ui/UI_PHASE2_FIXES.md` | C) Historical | Archived UI rollout note for the retired scaffolded interface. | KEEP |
| `docs/guides/ui/JUSTIFICATION_UI.md` | B) Operational | Current note describing the dormant UI scaffold and the supported API-only runtime surface. | KEEP |
| `docs/guides/watchdog/WATCHDOG_CHANGELOG.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/watchdog/WATCHDOG_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/watchdog/WATCHDOG_INDEX.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/watchdog/WATCHDOG_QUICKREF.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/watchdog/WATCHDOG_SUMMARY.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/PIPELINE_UPGRADE.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/QUICK_REFERENCE_WSL2.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/START_HERE_WSL2.md` | B) Operational | Operational guide with overlap/drift risk; keep but normalize. | REFRACTOR |
| `docs/guides/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/WSL2_AUDIO_SUMMARY.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/guides/wsl2/WSL2_BENCHMARKS.md` | B) Operational | Operator setup/usage guide. | KEEP |
| `docs/implementation-reports/PHASE_9.7_COMPLETE_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/implementation-reports/PHASE_9.8_FINAL_ACTIVATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/implementation/ENTITY_EXTRACTION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE1_SCENE_EXPLORER_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE2_COMPLETE_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE2_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE3_SELF_HEALING.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE4_AGENT_ORCHESTRATION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE4_AUDIO_PROCESSING_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE5_FINAL_SUCCESS_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE5_VALIDATION_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE6_KG_INTEGRATION_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE7_ANALYTICS_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE8_EXECUTIVE_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE8_FINAL_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE8_UNIFIED_KG_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_10_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_11_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_12_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_AUDIO_DIARIZATION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_GPU_FINAL_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_OSD_INTEGRATION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_PROGRESS_TRACKING_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_1_READY_FOR_PHASE_2.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_1_AUDIO_OPTIMIZATION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_2_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_3_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_3_FINAL_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_AUDIO_OPTIMIZATION_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_COMPLETE_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_TEST_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_2_VALIDATION_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_FINAL_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_FINAL_TEST_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_GPU_ISOLATION_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_GPU_ISOLATION_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_3_TESTING_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_7_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_8_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_9_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_B_COMPLETE_REAL_DATA.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/PHASE_INDEX.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/phases/UI_POLISH_BATTLE_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-history/CHANGELOG.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/DOCUMENTATION_UPDATE_2025-10-08.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/DOCUMENTATION_UPDATE_2025-10-09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/FINAL_RENAME_REPORT.txt` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/PROJECT_RENAME_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/RENAME_MIGRATION_LOG.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/RENAME_SUCCESS_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-history/REORGANIZATION_SUMMARY.txt` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/project-mgmt/AUDIT_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/BREAKTHROUGH_FINDINGS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/CRITICAL_FIX_REQUIRED.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/DIAGNOSIS_AND_REPAIR_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/DOCUMENTATION_CLEANUP_PLAN.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/DOCUMENTATION_CLEANUP_SUMMARY_2025-11-07.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/EXECUTIVE_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/ISSUE_PATTERNS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/MISSION_STATUS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PERFORMANCE_SUMMARY.txt` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROGRESS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROGRESS_TRACKING_IMPLEMENTATION.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROJECT_CLEANUP_SUMMARY.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROJECT_DEEP_ANALYSIS_2025-12-02.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROJECT_STATUS.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/PROJECT_STATUS_2025-10-08.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/READY_FOR_PRODUCTION_TEST.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/SETTINGS_AUDIT_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/SETTINGS_FIX_COMPLETE.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/SETTINGS_OPTIMIZED.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/STATUS_REPORT.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/project-mgmt/TODAYS_BREAKTHROUGH.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/proof_of_concept/WITNESS_RUN_001.md` | D) Experimental | Unclassified supporting document; merge/archive after review. | MERGE |
| `docs/reference/indexes/AGENT_COMMS_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/indexes/ANALYTICS_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/indexes/CODE_CLEANUP_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/indexes/DOCUMENTATION_INDEX.md` | B) Operational | Current pointer preserving incoming links to the docs landing and quick-reference surfaces. | KEEP |
| `docs/reference/indexes/ENVIRONMENT_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/indexes/QUICK_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/indexes/TROUBLESHOOTING_INDEX.md` | B) Operational | Reference/operator quick-access documentation. | KEEP |
| `docs/reference/quick-refs/CLI_COMMANDS_REFERENCE.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/reference/quick-refs/QUICK_REFERENCE.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/reference/quick-refs/QUICK_REFERENCE_CARD.md` | B) Operational | Compact operational quick reference for the supported runtime surface. | KEEP |
| `docs/reference/quick-refs/QUICK_REFERENCE_SETTINGS.md` | B) Operational | Reference guide with path/profile drift; normalize to canonical contract. | REFRACTOR |
| `docs/releases/AUDIO_DIARIZATION_STATUS.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/DEPLOYMENT_SUMMARY.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/GPU_AND_PROCESS_CONTROL_SUMMARY.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/GPU_QUICK_REF.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/READY_FOR_LAPTOP.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/RELEASE_CHECKPOINT_2026-02-10.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/RELEASE_NOTES_v1.4.0.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/SESSION_SUMMARY.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/releases/SHIP_PROFILE.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/releases/VISION_GPU_COMPLETE.md` | C) Historical | Release artifact or shipping snapshot (except canonical ship profile). | ARCHIVE |
| `docs/reports/CLEAN_SLATE_2025_12_09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/CRITICAL_BUG_FIX_Infinite_Hang_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/CRITICAL_FIX_INFINITE_LOOP_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/CRITICAL_SYSTEM_AUDIT_2025-12-10.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/DEPLOYMENT_STATUS_2025-12-09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/ENV_CONSOLIDATION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FILE_ORGANIZATION_LAUNCHER_20251211.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FINAL_CLEANUP_MIGRATION_COMPLETE_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FINAL_PRODUCTION_VALIDATION_2025-12-10.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FINAL_PRODUCTION_VALIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FINAL_STATUS_2025-12-10.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/FINAL_VALIDATION_STATUS_2025-12-10.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/LAUNCHER_TEST_RESULTS_20251211.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/MEMORY_ARCHITECTURE_AUDIT_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/NESTED_DIRECTORY_REMOVAL_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/OLLAMA_PORT_CORRECTION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE5_QUICK_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE5_SCENE_DETECTION_INTEGRATION_ANALYSIS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE6B_DIAGNOSTIC_REPORT_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE6B_PATCH_APPLIED_20251211.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE6_IMPLEMENTATION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE6_MULTIMODAL_EMBEDDINGS_ANALYSIS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE7_API_UI_ARCHITECTURE_ANALYSIS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE7_IMPLEMENTATION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE8_CLEANUP_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE8_FILESYSTEM_AUDIT_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE9.1_CRITICAL_CORRECTIONS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE9_2_FINAL_CLEANUP_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE9_FULL_SYSTEM_VALIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASED_SEGMENTATION_ENGINE_IMPLEMENTATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_10.4_VALIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_10_3_CONFIG_CONSOLIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_10_5_DIAGNOSTIC_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_10_COMPLETE_SYSTEM_READY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_10_LAUNCH_SYSTEM_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_11_COMPLETION_STATUS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_11_FINAL_VALIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_5_ACTIVATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_6_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_9.6_FIX_APPLIED.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_9.6_STATUS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PHASE_9_6_BREAKTHROUGH_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/PRODUCTION_VALIDATION_REPORT_2025-12-10.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/Phase_9.3_Live_Validation_Report.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/Phase_9.4_Legacy_Orchestration_Removal_Complete.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/Phase_9.7_Debug_Report.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/QDRANT_INTEGRATION_COMPLETE_20251211.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/README.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/SESSION_2025-12-09_GLOBAL_PATH_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/SESSION_SUMMARY_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/STAGE1_MEMORY_CLEANUP_RECON_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/STAGE2_CONFIG_CODE_CROSSCHECK_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/STAGE3_DATA_MIGRATION_COMPLETE_20251210.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/SYSTEM_READY_FOR_PRODUCTION.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/Session_Report_2025-12-07_to_2025-12-09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/Session_Summary_December_6_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/VIDEO_ID_PROPAGATION_FIX.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase10_3_config_consolidation_analysis.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase10_5_live_ingestion_status.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase6_integration_deep_diagnostic.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase7_api_test_report.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase96_SUCCESS_ingestion_running.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase96_ingestion_status_report.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/CONTROL_AGENT_PHASE2_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE7_ANALYSIS_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE9.5_LIVE_VALIDATION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE_10_1_DECLUTTER_ANALYSIS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE_10_2A_CLEANUP_PLAN.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE_9.9_FIRST_MEMORY_RUN_SUCCESS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE_9_7_STATUS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/PHASE_9_FINAL_STATUS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/cleanup_vendor_specs_analysis.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/phase_reports/pipeline_diagnosis_20251115_191741.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/scripts_cleanup_plan.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/reports/session_summaries/PR_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/ARTIFACT_LOCATION_AUDIT_DEC15_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/DOCUMENTATION_AUDIT_DEC15_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/DOCUMENTATION_AUDIT_DEC_15_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/DOCUMENTATION_COMPLETE_DEC_15_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/DOCUMENTATION_UPDATE_DEC_14_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/MEMORY_STORAGE_DOCUMENTATION_DEC15_2025.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/PRIORITY_1_DOCS_UPDATE_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/PRIORITY_2_COMPLETE_FINAL.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/PRIORITY_2_START_HERE_UPDATE_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/session-reports/PRIORITY_3_COMPLETE_GITHUB_READY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/CURRENT_STATUS.txt` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/CURRENT_SYSTEM_STATUS_2025-12-02.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/DECEMBER_2025_MAJOR_UPDATES.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/DOCUMENTATION_UPDATE_COMPLETE_2025-12-04.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/ENVIRONMENT_CONSOLIDATION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/GPU_STATUS_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/LAUNCH_SYSTEM_GUIDE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/LLM_PHASE1_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/LLM_STATUS.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/MASTER_DOCUMENTATION_TIMELINE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/MORNING_BRIEFING_2025-12-02.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/OVERNIGHT_SESSION_HANDOFF.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE1_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE2_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE3_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE3_COMPLETION_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE5_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE5_KG_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE6_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE7_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PHASE8_COMPLETION_REPORT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PRODUCTION_READY_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/PRODUCTION_VALIDATION_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/SYSTEM_AUDIT_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/SYSTEM_AUDIT_COMPLETE_2025-11-09.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/SYSTEM_CONFIG_AUDIT.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/SYSTEM_FIX_SUMMARY.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/status-reports/SYSTEM_REFACTOR_COMPLETE.md` | C) Historical | Time-bound report/release snapshot content. | ARCHIVE |
| `docs/systems/ERROR_HANDLING_RECOVERY.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/systems/WATCHDOG_SYSTEM.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/technical/ANALYTICS_PAGES_COMPLETE.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/ANALYTICS_QUICK_REFERENCE.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/API_CONSOLIDATION_COMPLETE.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/ARTIFACT_LOCATION_CONTRACT.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/AUDIO_GPU_IMPLEMENTATION_SUMMARY.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/AUDIO_GPU_OPTIMIZATION.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/AUDIO_GPU_QUICK_START.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/AUDIO_VAD_OPTIMIZATION.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/DATA_FLOW_DIAGRAM.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/ISSUE_RESOLUTION_20251012.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/KNOWLEDGE_GRAPH_IMPLEMENTATION.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/LIB_COMPONENTS.md` | A) Canonical | Declared runtime/contract authority document. | KEEP |
| `docs/technical/LOCKDOWN_STATUS.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/LOGGING_AND_RESILIENCE.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/MILESTONE_KNOWLEDGE_GRAPH_INTEGRATION.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/MODEL_HEALTH_DASHBOARD.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/MODEL_LOCKDOWN.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/MODEL_LOCKDOWN_IMPLEMENTATION.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/MODEL_LOCKDOWN_QUICK_REF.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/PHASE5_ACTIVATION_REPORT.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/PIPELINE_DEEP_DIVE_REPORT.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/PIPELINE_DIAGNOSIS_2025-11-11.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/PIPELINE_ENGINES_COMPLETE.md` | C) Historical | Historical implementation note for the pipeline-engines UI rollout; retain only as context. | KEEP |
| `docs/technical/PIPELINE_ENGINES_UI_UPDATE.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/SCENE_EXPLORER_DEPLOYMENT_GUIDE.md` | C) Historical | Historical deployment note for the Scene Explorer rollout; retain only as context. | KEEP |
| `docs/technical/SECRETS_ENV_MIGRATION.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/technical/SESSION_SUMMARY_2025-12-05.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/VAD_IMPLEMENTATION_SUMMARY.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/VISION_GPU_OPTIMIZATION.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/VISION_GPU_OPTIMIZATION_REPORT.md` | D) Experimental | Design or implementation note; useful but not primary authority. | MERGE |
| `docs/technical/WORKFLOW_VISUAL_GUIDE.md` | B) Operational | Architecture/technical reference; align to canonical runtime contracts. | REFRACTOR |
| `docs/technical/knowledge_graph.md` | B) Operational | Architecture/technical reference document. | KEEP |
| `docs/testing/TEST_RESULTS.md` | B) Operational | Testing and validation runbook. | KEEP |
| `docs/validation/run_narrative_validation.md` | B) Operational | Testing and validation runbook. | KEEP |
| `docs/reference/GPU_CAPABILITY_MATRIX.md` | A) Canonical | Declared runtime/contract authority document moved under the reference surface. | KEEP |
| `docs/reference/PLATFORM_SUPPORT.md` | A) Canonical | Declared runtime/contract authority document moved under the reference surface. | KEEP |
