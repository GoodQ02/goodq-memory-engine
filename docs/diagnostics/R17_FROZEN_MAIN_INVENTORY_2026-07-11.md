<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-17 Frozen Mixed-Main Inventory

## Scope

This is the entry-by-entry ownership map for the frozen main checkout on
`feature/semantic-identity-layer`. The ordinary status view contains 85
collapsed entries; `git status --short -uall` expands them to 96 files. The
checkout was read only during classification.

Authority for already repaired content is the latest isolated checkpoint
lineage ending at `eb4b5e28`, not the older mixed-tree copy.

## Summary

| Owner or disposition | Files |
|---|---:|
| Generated residue | 9 |
| No-repeat / evidence | 1 |
| No-repeat / orientation | 7 |
| No-repeat / R-02 | 12 |
| No-repeat / R-03 | 2 |
| No-repeat / R-04 | 7 |
| No-repeat / R-06 | 4 |
| No-repeat / register | 1 |
| R-05 | 5 |
| R-08 | 13 |
| R-08 evidence | 3 |
| R-09 | 2 |
| R-11 | 1 |
| R-13 | 10 |
| R-13 archive | 16 |
| R-18 validator | 2 |
| R-19 discard | 1 |

Unknown entries: **0**.

## Entry Register

| Status | Path | Owner | Required disposition |
|---|---|---|---|
| `M` | `.agents/skills/goodq4all-operator/SKILL.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `AGENTS.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `PROJECT.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `agents/mini_agent_client.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `agents/stack/contracts/goodq-o2-local.contract.json` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `api/main.py` | R-05 | Preserve artifact intent; checkpoint only with R-05/R-08/R-11 authority. |
| `M` | `api/routes/identity.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `M` | `cli/run_ingestion.py` | No-repeat / R-06 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `configs/config.local.example.yaml` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `configs/config.yaml` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `configs/identity/family_roster.template.yaml` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `configs/identity/family_terms.template.yaml` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `configs/python_paths.py` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `docs/README.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/agent/CURRENT_STATE.md` | R-09 | Rebuild from one fresh evidence source; do not transplant. |
| `D` | `docs/agent/DOCS_AUDIT_AND_REORGANIZATION_REPORT.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `D` | `docs/agent/POST_PROMOTION_GRAPH_SIGNAL_NOISE_AUDIT.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `M` | `docs/agent/README.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT_BASELINE.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `D` | `docs/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `D` | `docs/agent/UCF_REMAINING_WORK.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `D` | `docs/agent/UCF_SEARCH_LOOP_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `M` | `docs/agent/current_state.json` | R-09 | Rebuild from one fresh evidence source; do not transplant. |
| `M` | `docs/agent/skills/goodq4all-operator/SKILL.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `docs/architecture/CONFIG_LOADING_CONTRACT.md` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md` | No-repeat / R-06 | Do not extract; the latest isolated checkpoint is authoritative. |
| `D` | `docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `M` | `docs/architecture/README.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/bootstrap/doc_authority_map.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/goodq4all_agent_status.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `D` | `docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `M` | `docs/reference/CLI-REFERENCE.md` | No-repeat / R-06 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `docs/reference/indexes/AGENT_FILE_INDEX.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/reference/indexes/DOCS_FORENSICS_INDEX.md` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `docs/releases/ROADMAP.md` | No-repeat / register | Do not transplant; the checkpoint lineage contains the authoritative register. |
| `D` | `docs/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `M` | `gemini.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `lib/identity_resolver.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `D` | `scripts/build_handoff.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `scripts/docs/doc_drift_lint.py` | R-13 | Reconcile in the R-13 authority/index seam; do not transplant piecemeal. |
| `M` | `scripts/identity/build_speaker_clusters.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `M` | `scripts/qdrant/prepare_clean_slate.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `D` | `scripts/run_lifecycle.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `D` | `scripts/ucf/promote_pilot.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `scripts/ucf/ucf_ledger.py` | No-repeat / R-03 | Do not extract; the latest isolated checkpoint is authoritative. |
| `D` | `scripts/ucf/validate_and_promote_epoch.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `scripts/ucf/validate_ucf_epoch.py` | R-18 validator | Next extraction pair; isolate and reverify before broader R-18 work. |
| `M` | `tests/agents/test_mini_agent_client.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `tests/integration/test_governance_validators.py` | R-11 | Reassess with the MiniAgent confirmation-bypass repair. |
| `M` | `tests/integration/test_ucf_retrieval_bridge.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `tests/integration/test_ucf_retrieval_bridge_stress.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `tests/integration/test_ucf_validator.py` | R-18 validator | Next extraction pair; isolate and reverify before broader R-18 work. |
| `M` | `tests/unit/test_config_values.py` | No-repeat / R-04 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `tests/unit/test_progressive_ingestion.py` | No-repeat / R-06 | Do not extract; the latest isolated checkpoint is authoritative. |
| `M` | `ui/identity_workbench/index.html` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `M` | `ui/identity_workbench/static/css/identity.css` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `M` | `ui/identity_workbench/static/js/identity.js` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `M` | `ui/retro_console_v1/index.html` | R-05 | Preserve artifact intent; checkpoint only with R-05/R-08/R-11 authority. |
| `??` | `.pytest_temp_clean/test_audio_media_route_invertecurrent` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_family_roster_crud_and_va0/GoodQ_Data/identity/face_clusters.json` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_family_roster_crud_and_va0/GoodQ_Data/identity/family_roster.json` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_family_roster_crud_and_va0/GoodQ_Data/identity/family_roster.yaml` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_family_roster_crud_and_va0/GoodQ_Data/identity/speaker_clusters.json` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_family_roster_crud_and_vacurrent` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_out_of_range_boundscurrent` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `.pytest_temp_clean/test_range_header_streamingcurrent` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `cli/ucf_promotion.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `??` | `docs/agent/IDENTITY_WORKBENCH_EVIDENCE_WIRING_REPORT.md` | R-08 evidence | Regenerate after the repaired live API/browser witness; do not preserve stale counts. |
| `??` | `docs/agent/PROJECT_ORIENTATION.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `??` | `docs/agent/screenshots/identity_workbench_evidence.png` | R-08 evidence | Regenerate after the repaired live API/browser witness; do not preserve stale counts. |
| `??` | `docs/agent/screenshots/identity_workbench_failure.png` | Generated residue | Discard only during separately approved frozen-tree retirement. |
| `??` | `docs/agent/screenshots/identity_workbench_polished.png` | R-08 evidence | Regenerate after the repaired live API/browser witness; do not preserve stale counts. |
| `??` | `docs/archive/agent/UCF_QDRANT_STATUS_BACKFILL_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/agent/UCF_REMAINING_WORK.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/agent/UCF_SEARCH_LOOP_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/reports/DOCS_AUDIT_AND_REORGANIZATION_REPORT.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/reports/POST_PROMOTION_GRAPH_SIGNAL_NOISE_AUDIT.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/archive/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` | R-13 archive | Move source and destination together under R-13, then regenerate indexes and links. |
| `??` | `docs/diagnostics/R02_CHECKPOINT_HANDOFF_2026-07-10.md` | No-repeat / evidence | Do not extract; newer R-02 checkpoint evidence is authoritative. |
| `??` | `docs/superpowers/plans/2026-07-11-project-orientation-instruction-alignment.md` | No-repeat / orientation | Do not extract; the latest isolated checkpoint is authoritative. |
| `??` | `lib/identity_evidence_resolver.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `scripts/identity/run_phases_job.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `scripts/start_api_server.ps1` | R-19 discard | Do not extract; rebuild the supervisor from the R-19 contract. |
| `??` | `tests/identity/test_challenger_streaming_roster.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `tests/identity/test_evidence_wiring.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `tests/identity/test_identity_api_stress.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `tests/integration/test_ucf_transition_atomicity.py` | No-repeat / R-03 | Do not extract; the latest isolated checkpoint is authoritative. |
| `??` | `tests/ui/test_identity_workbench_polished.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `tests/unit/test_identity_phases_api.py` | R-08 | Reconstruct and harden in R-08; do not copy wholesale. |
| `??` | `tests/unit/test_ucf_promotion_cli.py` | No-repeat / R-02 | Do not extract; the latest isolated checkpoint is authoritative. |
| `??` | `ui/command_center/index.html` | R-05 | Preserve artifact intent; checkpoint only with R-05/R-08/R-11 authority. |
| `??` | `ui/command_center/static/css/command.css` | R-05 | Preserve artifact intent; checkpoint only with R-05/R-08/R-11 authority. |
| `??` | `ui/command_center/static/js/command.js` | R-05 | Preserve artifact intent; checkpoint only with R-05/R-08/R-11 authority. |

## Family Decisions

- R-02, R-03, R-04, R-06, the master register, and the foundational orientation
  are no-repeat families. Exact matches and older variants remain frozen only
  until the final uniqueness comparison.
- The next extractable pair is R-18 validator truth:
  `scripts/ucf/validate_ucf_epoch.py` plus
  `tests/integration/test_ucf_validator.py`.
- Current-state files are rebuilt under R-09; documentation/archive/index work
  stays together under R-13.
- Identity and Command Center prototypes have explicit R-08/R-05/R-11 owners.
  Their intent is preserved, but their current unsafe authority, live-store
  tests, path disclosure, and job-lifecycle behavior are not checkpoint-ready.
- The API startup prototype is discarded in favor of an R-19 supervisor rebuild.
- Generated pytest links/files and the failed screenshot are deletion candidates
  only at a separately approved frozen-tree retirement.

## Retirement Gate

Do not reset, restore, clean, or retire the mixed checkout from this inventory
alone. Retirement requires:

1. the R-18 validator pair checkpoint,
2. every later-owned family either reconstructed or explicitly deferred,
3. a fresh content comparison against the checkpoint lineage,
4. a separate destructive approval.
