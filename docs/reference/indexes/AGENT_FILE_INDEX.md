<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_INDEX -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->
<!-- DOC_GENERATOR: scripts/docs/doc_authority_lint.py render-index -->

# Active Repository File Index

This operational index is generated from `git ls-files`. It is a discovery
surface, not runtime or architecture authority. The explicit active scope
excludes `archive/`, `docs/archive/`, and `vendor/`.

Regenerate with:

```powershell
conda run --no-capture-output -n goodq_core python scripts/docs/doc_authority_lint.py render-index
```

Indexed active tracked paths: **1325**

| File Path | Component | Purpose |
|---|---|---|
| `/.agents/DEFERRED_FINDINGS.md` | Repository root | Root-level project or runtime surface. |
| `/.agents/index/corrections.json` | Repository root | Root-level project or runtime surface. |
| `/.agents/skills/goodq4all-operator/SKILL.md` | Repository root | Root-level project or runtime surface. |
| `/.env.local.template` | Repository root | Root-level project or runtime surface. |
| `/.env.model_cache` | Repository root | Root-level project or runtime surface. |
| `/.env.template` | Repository root | Root-level project or runtime surface. |
| `/.gitattributes` | Repository root | Root-level project or runtime surface. |
| `/.github/CODEOWNERS` | Repository automation | Workflow or repository automation asset. |
| `/.github/ISSUE_TEMPLATE/bug_report.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/ISSUE_TEMPLATE/config.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/ISSUE_TEMPLATE/feature_request.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/ISSUE_TEMPLATE/first_run_problem.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/PULL_REQUEST_TEMPLATE.md` | Repository automation | Workflow or repository automation asset. |
| `/.github/dependabot.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/workflows/ci.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/workflows/codeql.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/workflows/dependency-review.yml` | Repository automation | Workflow or repository automation asset. |
| `/.github/workflows/doc-drift-lint.yml` | Repository automation | Workflow or repository automation asset. |
| `/.gitignore` | Repository root | Root-level project or runtime surface. |
| `/.ignore` | Repository root | Root-level project or runtime surface. |
| `/AGENTS.md` | Repository root | Root-level project or runtime surface. |
| `/CHANGELOG.md` | Repository root | Root-level project or runtime surface. |
| `/CODE_OF_CONDUCT.md` | Repository root | Root-level project or runtime surface. |
| `/CONTRIBUTING.md` | Repository root | Root-level project or runtime surface. |
| `/LAUNCH_GOODQ.bat` | Repository root | Root-level project or runtime surface. |
| `/LAUNCH_GOODQ.ps1` | Repository root | Root-level project or runtime surface. |
| `/LICENSE` | Repository root | Root-level project or runtime surface. |
| `/PLAN.md` | Repository root | Root-level project or runtime surface. |
| `/PROJECT.md` | Repository root | Root-level project or runtime surface. |
| `/README.md` | Repository root | Root-level project or runtime surface. |
| `/SECURITY.md` | Repository root | Root-level project or runtime surface. |
| `/SUPPORT.md` | Repository root | Root-level project or runtime surface. |
| `/TEST_INFRA.md` | Repository root | Root-level project or runtime surface. |
| `/TEST_READY.md` | Repository root | Root-level project or runtime surface. |
| `/THIRD_PARTY_NOTICES.md` | Repository root | Root-level project or runtime surface. |
| `/__init__.py` | Repository root | Root-level project or runtime surface. |
| `/agents/README.md` | Agent control | Agent control or contract implementation. |
| `/agents/__init__.py` | Agent control | Agent control or contract implementation. |
| `/agents/analysis/__init__.py` | Agent control | Agent control or contract implementation. |
| `/agents/base_agent.py` | Agent control | Agent control or contract implementation. |
| `/agents/config_healer.py` | Agent control | Agent control or contract implementation. |
| `/agents/control_agent.py` | Agent control | Agent control or contract implementation. |
| `/agents/ingestion/__init__.py` | Agent control | Agent control or contract implementation. |
| `/agents/knowledge/__init__.py` | Agent control | Agent control or contract implementation. |
| `/agents/llm_agent.py` | Agent control | Agent control or contract implementation. |
| `/agents/mini_agent_client.py` | Agent control | Agent control or contract implementation. |
| `/agents/recovery_db.py` | Agent control | Agent control or contract implementation. |
| `/agents/recovery_strategies.py` | Agent control | Agent control or contract implementation. |
| `/agents/self_healing_monitor.py` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-delegation-worker-map.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-output-adapters.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-persona-pack.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-preferences.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-service-policies.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/configs/goodq-v2-modules.config.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/contracts/goodq-coding-agent.contract.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/contracts/goodq-o2-local.contract.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/delegation/goodq-delegation-protocol.offline.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/delegation/goodq-delegation-protocol.safe.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/delegation/goodq-delegation-protocol.unrestricted.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/policies/goodq-runtime-policy.offline.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/policies/goodq-runtime-policy.safe.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/policies/goodq-runtime-policy.unrestricted.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/schema/delegation-protocol-v1.schema.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/schema/goodq-tool-contract-v1.schema.json` | Agent control | Agent control or contract implementation. |
| `/agents/stack/schema/runtime-policy-v1.schema.json` | Agent control | Agent control or contract implementation. |
| `/api/API_DOCUMENTATION.md` | API | API or local control-plane implementation. |
| `/api/main.py` | API | API or local control-plane implementation. |
| `/api/requirements.txt` | API | API or local control-plane implementation. |
| `/api/route_effects.py` | API | API or local control-plane implementation. |
| `/api/routes/__init__.py` | API | API or local control-plane implementation. |
| `/api/routes/control_recurrence.py` | API | API or local control-plane implementation. |
| `/api/routes/identity.py` | API | API or local control-plane implementation. |
| `/api/routes/ingest.py` | API | API or local control-plane implementation. |
| `/api/routes/media.py` | API | API or local control-plane implementation. |
| `/api/routes/meta.py` | API | API or local control-plane implementation. |
| `/api/routes/run_index.py` | API | API or local control-plane implementation. |
| `/api/routes/run_summary.py` | API | API or local control-plane implementation. |
| `/api/routes/runtime.py` | API | API or local control-plane implementation. |
| `/api/routes/scenes.py` | API | API or local control-plane implementation. |
| `/api/routes/search.py` | API | API or local control-plane implementation. |
| `/api/routes/summary.py` | API | API or local control-plane implementation. |
| `/api/routes/system.py` | API | API or local control-plane implementation. |
| `/api/routes/timeline.py` | API | API or local control-plane implementation. |
| `/api/server.py` | API | API or local control-plane implementation. |
| `/api/utils/__init__.py` | API | API or local control-plane implementation. |
| `/api/utils/action_jobs.py` | API | API or local control-plane implementation. |
| `/api/utils/identity_read_projection.py` | API | API or local control-plane implementation. |
| `/api/utils/ingest_requests.py` | API | API or local control-plane implementation. |
| `/api/utils/loaders.py` | API | API or local control-plane implementation. |
| `/api/utils/media_projection.py` | API | API or local control-plane implementation. |
| `/api/utils/response_models.py` | API | API or local control-plane implementation. |
| `/api/utils/temporal_summary_results.py` | API | API or local control-plane implementation. |
| `/branding/README.md` | Repository root | Root-level project or runtime surface. |
| `/branding/favicon.ico` | Repository root | Root-level project or runtime surface. |
| `/branding/goodbrand.svg` | Repository root | Root-level project or runtime surface. |
| `/branding/site.webmanifest` | Repository root | Root-level project or runtime surface. |
| `/branding/xfiles_title_card.png` | Repository root | Root-level project or runtime surface. |
| `/cli/__init__.py` | CLI | Command-line operator surface. |
| `/cli/auth_models.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_external_pin.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_filesystem.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_protected_boundary.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_protected_manifest.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_protected_membership.py` | CLI | Command-line operator surface. |
| `/cli/clean_memory_qdrant.py` | CLI | Command-line operator surface. |
| `/cli/conduits_build.py` | CLI | Command-line operator surface. |
| `/cli/conduits_kg.py` | CLI | Command-line operator surface. |
| `/cli/conduits_memory.py` | CLI | Command-line operator surface. |
| `/cli/conduits_processing.py` | CLI | Command-line operator surface. |
| `/cli/conduits_sensitive_sources.py` | CLI | Command-line operator surface. |
| `/cli/conduits_store_stats.py` | CLI | Command-line operator surface. |
| `/cli/control_recurrence_report.py` | CLI | Command-line operator surface. |
| `/cli/goodq_doctor.py` | CLI | Command-line operator surface. |
| `/cli/links.py` | CLI | Command-line operator surface. |
| `/cli/list_inbox.py` | CLI | Command-line operator surface. |
| `/cli/media_refs.py` | CLI | Command-line operator surface. |
| `/cli/memory.py` | CLI | Command-line operator surface. |
| `/cli/monitor_ingestion.py` | CLI | Command-line operator surface. |
| `/cli/monitor_live.bat` | CLI | Command-line operator surface. |
| `/cli/nl_query.py` | CLI | Command-line operator surface. |
| `/cli/observability_health.py` | CLI | Command-line operator surface. |
| `/cli/observability_rollup.py` | CLI | Command-line operator surface. |
| `/cli/persistent_store_alignment_audit.py` | CLI | Command-line operator surface. |
| `/cli/print_config.py` | CLI | Command-line operator surface. |
| `/cli/recovery_promotion.py` | CLI | Command-line operator surface. |
| `/cli/retrieve.py` | CLI | Command-line operator surface. |
| `/cli/run_ingestion.py` | CLI | Command-line operator surface. |
| `/cli/step_runner.py` | CLI | Command-line operator surface. |
| `/cli/system_status.py` | CLI | Command-line operator surface. |
| `/cli/test_ingestion.py` | CLI | Command-line operator surface. |
| `/cli/ucf_promotion.py` | CLI | Command-line operator surface. |
| `/cli/ui_conduits_rollup.py` | CLI | Command-line operator surface. |
| `/cli/watchdog.py` | CLI | Command-line operator surface. |
| `/common/gpu_manager.py` | Repository root | Root-level project or runtime surface. |
| `/common/gpu_monitor.py` | Repository root | Root-level project or runtime surface. |
| `/common/progress_tracker.py` | Repository root | Root-level project or runtime surface. |
| `/common/vram_allocator.py` | Repository root | Root-level project or runtime surface. |
| `/configs/__init__.py` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/build_toolchain_manifest.json` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/config.local.example.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/config.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/entities.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/identity/.gitignore` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/identity/family_roster.template.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/identity/family_terms.template.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/model_download_manifest.json` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/model_download_manifest.json.sig` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/model_registry.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/models_config.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/offline_dependencies_manifest.json` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/open_config.yaml` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/paths.py` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/python_paths.py` | Configuration | Configuration, schema, or runtime profile. |
| `/configs/quantization_codebooks.npz` | Configuration | Configuration, schema, or runtime profile. |
| `/context7.json` | Repository root | Root-level project or runtime surface. |
| `/dev_off.bat` | Repository root | Root-level project or runtime surface. |
| `/dev_off.sh` | Repository root | Root-level project or runtime surface. |
| `/dev_on.bat` | Repository root | Root-level project or runtime surface. |
| `/dev_on.sh` | Repository root | Root-level project or runtime surface. |
| `/docs/AGENT_CAPABILITIES.md` | Documentation | Active documentation or governance surface. |
| `/docs/GOODQ_RAG_CONTEXT_PACK.md` | Documentation | Active documentation or governance surface. |
| `/docs/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/SYSTEM_SNAPSHOT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/CLEAN_FIRST_GO_INGESTION_MONITORING_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/CONTROL_AGENT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/CURRENT_STATE.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/FORENSIC_THREE_SCENE_TRACE_AUDIT_76dedbe1b16c.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/GPU_ACCELERATED_INGESTION_WITNESS_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/GPU_WSL_INGESTION_MONITORING_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/PROJECT_ORIENTATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/UCF_COVERAGE_GAP_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/birth_certificate.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/current_state.json` | Documentation | Active documentation or governance surface. |
| `/docs/agent/skills/fable-prompt-cache/SKILL.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/skills/goodq4all-audit/SKILL.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/skills/goodq4all-operator/SKILL.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/skills/using-agent-skills/SKILL.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/training_dataset_generator_specification.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/workflows/CLEAN_MEMORY_START.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/workflows/LAPTOP_TEST_AND_REPORT_PROTOCOL.md` | Documentation | Active documentation or governance surface. |
| `/docs/agent/workflows/PIPELINE_TROUBLESHOOTING_FLOW.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/AGENT_DECISION_PROTOCOL.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/AGENT_SYSTEM.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/ARCHITECTURE_REFERENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/CANONICAL_SENSITIVE_EVENTS.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/CONFIG_LOADING_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/EPISTEMIC_READ_MODEL.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/HITL_STITCHING_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/IDENTITY_STITCHING_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/INGESTION_PERFORMANCE_TIMINGS.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/LEGACY_WORKFLOWS.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/LLM_CLIENT_INJECTION_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/MEMORY_STORAGE.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/NON_ACTION_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/OFFLINE_DEPENDENCIES.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/ORGANIZATION_COMPLETE_2025-11-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/PHASE6_MULTIMODAL_FUSION.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/PROJECT_STRUCTURE.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/RUNTIME_AUTHORITY_MEMO.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/SCENE_MANIFEST_SPECIFICATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/SUMMARY_CONSOLE_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/SYSTEM_ARCHITECTURE.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/SYSTEM_MAP_v1.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/TURBOQUANT_HYBRID_CACHING.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/components/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/components/VISION_PIPELINE.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/data_epochs.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/diagrams/PIPELINE_FLOW.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/diagrams/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/diagrams/knowledge_graph_architecture.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/diagrams/watchdog_flow.md` | Documentation | Active documentation or governance surface. |
| `/docs/architecture/narrative_layer.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/CORPUS_PACK_MANIFEST.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/INSTALL_BOOTSTRAP.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/REPO_GROUNDED_CLEANUP_CHECKLIST.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/bootstrap_manifest.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/doc_archive_plan.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/doc_authority_map.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/doc_authority_policy.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/doc_governance_summary.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/doc_lint_ci_snippet.md` | Documentation | Active documentation or governance surface. |
| `/docs/bootstrap/smoke_matrix_phase_a.md` | Documentation | Active documentation or governance surface. |
| `/docs/codebase_index/README.md` | Documentation | Active documentation or governance surface. |
| `/docs/codebase_index/codebase_health_audit.md` | Documentation | Active documentation or governance surface. |
| `/docs/codebase_index/codebase_index.json` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/AUDIT_SUMMARY_QUICK.txt` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/FOUNDATIONAL_ORIENTATION_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R02_PORTABLE_PROMOTION_CHECKPOINT_2026-07-10.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R03_LIFECYCLE_TRANSITION_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R04_CONFIG_PORTABILITY_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_API_AUTHORITY_AUDIT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_HIDDEN_READ_MUTATION_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_INGEST_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_MODEL_CACHE_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_MODEL_CACHE_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_QDRANT_QUERY_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_REMAINING_CANDIDATE_RECONCILIATION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_REMAINING_HIDDEN_READ_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_CONTEXT_AUTHORITY_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_FAISS_STORE_REF_PRIVACY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_FAISS_STORE_REF_PRIVACY_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_QUERY_LOG_PRIVACY_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_SQLITE_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_RETRIEVAL_TELEMETRY_PERSISTENCE_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_SUMMARY_SQLITE_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_F1_SUMMARY_STATUS_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_GATE_REPAIR_CHECKPOINT_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_INGEST_STAGING_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_MUTATION_EXECUTION_AUTHORITY_AUDIT_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_PRIVATE_BACKUP_CHECKPOINT_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_AUDIT_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_ROUTE_EFFECT_BOUNDARY_CHECKPOINT_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_SUMMARY_COLLECTION_AUTHORITY_SELECTION_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_TEMPORAL_SUMMARY_AUTHORITY_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R05_VIDEO_SUMMARY_AUTHORITY_CHECKPOINT_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R06_PROGRESSIVE_CHECKPOINT_EVIDENCE_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_CHECKPOINT_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_RECHECK_DECISION_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_CLEAN_MEMORY_REPLACEMENT_SELECTION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_FILESYSTEM_OBSERVER_BOUNDARY_AUDIT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PASSIVE_PLAN_ORCHESTRATION_AUDIT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_BOUNDARY_AUTHORITY_AUDIT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CHECKPOINT_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_BOUNDARY_OBSERVER_CONTRACT_DECISION_2026-07-15.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CAPABILITY_GAP_AUDIT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CONTRACT_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MANIFEST_VALIDATOR_EXTRACTION_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_QDRANT_OBSERVATION_BOUNDARY_AUDIT_2026-07-16.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_QDRANT_OBSERVER_CHECKPOINT_2026-07-16.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CAPACITY_EXTENSION_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_BOUNDED_READ_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_IMPLEMENTATION_DECISION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_LABEL_SECURITY_TRANSPORT_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_PROGRAM_DATA_LOCATOR_RECHECK_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_READER_CAPABILITY_GAP_AUDIT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_READER_IDENTITY_POLICY_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_SECURITY_CAPABILITY_DECISION_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_SECURITY_DESCRIPTOR_CHECKPOINT_2026-07-13.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_CHECKPOINT_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R07_WINDOWS_SECURITY_MECHANICS_EXTRACTION_DECISION_2026-07-14.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R08_IDENTITY_GET_NONCREATING_CHECKPOINT_2026-07-16.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R08_PIPELINE_RECOVERY_AND_WITNESS_CLOSEOUT_2026-07-28.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R08_WSL_AUDIO_OFFLINE_WITNESS_2026-07-28.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R09_CURRENT_STATE_TRUTH_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R10_ARCHITECTURE_CONTRACT_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R11_CONTROL_AUTHORITY_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R11_F1_HANDLER_OUTCOME_TRUTH_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R13_DOCUMENTATION_AUTHORITY_CHECKPOINT_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R17_FROZEN_MAIN_INVENTORY_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R18_F1_API_TEST_HARNESS_CHECKPOINT_2026-07-12.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/R18_VALIDATOR_EVIDENCE_ISOLATION_2026-07-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/SESSION_COMPLETE_WSL2_AUDIT.txt` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/evidence/CURRENT_STATE_EVIDENCE_2026-07-11.json` | Documentation | Active documentation or governance surface. |
| `/docs/diagnostics/evidence/CURRENT_STATE_EVIDENCE_2026-07-28.json` | Documentation | Active documentation or governance surface. |
| `/docs/goodq4all_agent_status.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/CLEAN_MEMORY_START.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/CONSOLIDATION_EXPLAINED.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/DEMO.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/FIRST_RUN.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/QDRANT_SETUP.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/SCENE_OPTIMIZATION_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/general/WATCHDOG_QUICKSTART.txt` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_FIX_SUMMARY.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_ISOLATION_STRATEGY.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_LLM_WSL_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_MONITORING_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_PHASE_1_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_PHASE_1_TEST_RESULTS.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_QUICK_START.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_REFACTOR_PROGRESS.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_SCENE_DETECTION_IMPLEMENTATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/gpu/GPU_SETUP.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/LLM_CLIENT_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/LLM_INFRASTRUCTURE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/LLM_INTEGRATION_ANALYSIS.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/LLM_INTEGRATION_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/VLLM_SYSTEMD_SETUP.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/VLLM_WSL_INSTALL_VERIFY_2026-04-10.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/llm/WSL2_AUDIO_SETUP.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/ui/JUSTIFICATION_UI.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/ui/USER_INTERFACE_WALKTHROUGH.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/watchdog/WATCHDOG_CHANGELOG.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/watchdog/WATCHDOG_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/watchdog/WATCHDOG_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/watchdog/WATCHDOG_QUICKREF.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/PIPELINE_UPGRADE.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/QUICK_REFERENCE_WSL2.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/START_HERE_WSL2.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/WSL2_BENCHMARKS.md` | Documentation | Active documentation or governance surface. |
| `/docs/guides/wsl2/test_pipeline.md` | Documentation | Active documentation or governance surface. |
| `/docs/operator/OLLAMA_PORT_BOUNDARIES.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/API.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/CLI-REFERENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/DEPENDENCIES.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/GPU_CAPABILITY_MATRIX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/PLATFORM_SUPPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/WSL_AUDIO_RUNTIME.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/AGENT_COMMS_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/AGENT_FILE_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/ANALYTICS_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/DOCS_FORENSICS_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/DOCUMENTATION_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/ENVIRONMENT_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/GLOSSARY.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/MASTER_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/QUICK_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/SUBSYSTEMS_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/indexes/TROUBLESHOOTING_INDEX.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/CHEAT_SHEET.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/CLI_COMMANDS_REFERENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/QDRANT_QUICKREF.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/QUICK_REFERENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/QUICK_REFERENCE_CARD.md` | Documentation | Active documentation or governance surface. |
| `/docs/reference/quick-refs/QUICK_REFERENCE_SETTINGS.md` | Documentation | Active documentation or governance surface. |
| `/docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md` | Documentation | Active documentation or governance surface. |
| `/docs/releases/ROADMAP.md` | Documentation | Active documentation or governance surface. |
| `/docs/superpowers/plans/2026-07-10-qori-archive-lynx-pet.md` | Documentation | Active documentation or governance surface. |
| `/docs/superpowers/specs/2026-07-10-qori-archive-lynx-pet-design.md` | Documentation | Active documentation or governance surface. |
| `/docs/systems/ERROR_HANDLING_RECOVERY.md` | Documentation | Active documentation or governance surface. |
| `/docs/systems/WATCHDOG_SYSTEM.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/ANALYTICS_PAGES_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/ANALYTICS_QUICK_REFERENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/AUDIO_GPU_IMPLEMENTATION_SUMMARY.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/AUDIO_GPU_OPTIMIZATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/AUDIO_GPU_QUICK_START.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/AUDIO_VAD_OPTIMIZATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/DATA_FLOW_DIAGRAM.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/DEPENDENCY_ARCHITECTURE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/FASTAPI_COMPATIBILITY_WALL.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/KNOWLEDGE_GRAPH_IMPLEMENTATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/LIB_COMPONENTS.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/LOGGING_AND_RESILIENCE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/MODEL_LOCKDOWN.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/MODEL_LOCKDOWN_IMPLEMENTATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/MODEL_LOCKDOWN_QUICK_REF.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/PIPELINE_DEEP_DIVE_REPORT.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/PIPELINE_DIAGNOSIS_2025-11-11.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/PIPELINE_ENGINES_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/PIPELINE_ENGINES_UI_UPDATE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/SCENE_EXPLORER_DEPLOYMENT_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/SECRETS_ENV_MIGRATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/VAD_IMPLEMENTATION_SUMMARY.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/VISION_GPU_OPTIMIZATION.md` | Documentation | Active documentation or governance surface. |
| `/docs/technical/knowledge_graph.md` | Documentation | Active documentation or governance surface. |
| `/docs/testing/TESTING_GUIDE.md` | Documentation | Active documentation or governance surface. |
| `/environment-baseline-lock.yml` | Repository root | Root-level project or runtime surface. |
| `/environment.gpu.yml` | Repository root | Root-level project or runtime surface. |
| `/environment.yml` | Repository root | Root-level project or runtime surface. |
| `/envs/audio_diarize/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/audio_embed/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/audio_emotion/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/audio_metadata/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/audio_transcribe/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/emotion_classify/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/face_embed/KNOWN_ISSUES.md` | Repository root | Root-level project or runtime surface. |
| `/envs/face_embed/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/home_assistant_status/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/image_caption/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/llm_chat/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/README.md` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/audio_diarize.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/audio_embed.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/audio_emotion.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/audio_metadata.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/audio_transcribe.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/emotion_classify.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/face_embed.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/home_assistant_status.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/image_caption.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/llm_chat.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/object_detect.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/object_track_yolo.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/ocr.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/pdf_text.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/sentiment.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/system_metrics.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/tagger.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/text_embed.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/tts.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/locks/video_scene_detect.lock.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/object_detect/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/object_track_yolo/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/ocr/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/pdf_text/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/sentiment/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/system_metrics/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/tagger/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/text_embed/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/tts/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/envs/video_scene_detect/requirements.txt` | Repository root | Root-level project or runtime surface. |
| `/gemini.md` | Repository root | Root-level project or runtime surface. |
| `/goodq_version.py` | Repository root | Root-level project or runtime surface. |
| `/lib/control_recurrence_hygiene.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/control_recurrence_index.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/control_recurrence_recommendations.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/control_recurrence_report.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/control_recurrence_trend.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/goodq_logger.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/identity_ledger.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/identity_resolver.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/kg_realtime_integration.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/knowledge_graph.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/llm_client.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/mission_components.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/model_lifecycle.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/observability/__init__.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/observability/event_types.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/observability/observer.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/persistent_store_alignment.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/run_index.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/run_narrative.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/run_summary.py` | Core library | Core memory, control, or persistence implementation. |
| `/lib/summary_aggregator.py` | Core library | Core memory, control, or persistence implementation. |
| `/pipelines/__init__.py` | Repository root | Root-level project or runtime surface. |
| `/pipelines/direct_ingestion.py` | Repository root | Root-level project or runtime surface. |
| `/processing_onboarding/_resolved_config.json` | Repository root | Root-level project or runtime surface. |
| `/pytest.ini` | Repository root | Root-level project or runtime surface. |
| `/reports/README.md` | Repository root | Root-level project or runtime surface. |
| `/reports/control_recurrence/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness.md` | Repository root | Root-level project or runtime surface. |
| `/reports/control_recurrence/20260424_182406_season2_fresh_witness.md` | Repository root | Root-level project or runtime surface. |
| `/reports/llm_audit_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/reference_anchors/seinfeld/episodes/03x10_the_stranded.reference.json` | Repository root | Root-level project or runtime surface. |
| `/reports/reference_anchors/seinfeld/episodes/03x11_the_alternate_side.reference.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/README.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/embedding_health_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/entity_analysis_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/experiment_summary.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/kg_structure_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/post_witness_analytics_metrics_2026-03-09.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/scene_segmentation_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/diagnostics/semantic_pattern_report.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/README.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/artifact_manifest.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/ingestion_stderr.log` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/optional_step_failures.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/per_episode_coverage.csv` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_metrics_2026-03-10.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_optional_status_2026-03-10.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_stderr_2026-03-10.log` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/resolved_config_snapshot.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/resolved_config_snapshot_2026-03-10.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/retrieval_anchor_checks.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10.csv` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10.png` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10.svg` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10_metadata.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_labeled_2026-03-10.png` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_labeled_2026-03-10.svg` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/semantic_comparison_metrics_2026-03-10.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/semantic_comparison_report_2026-03-10.md` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/witness_metrics.json` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/umap/generate_umap_clip_text.py` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/umap/scene_umap_clip_text.png` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/umap/scene_umap_clip_text_coords.csv` | Repository root | Root-level project or runtime surface. |
| `/reports/seinfeld_experiment/umap/scene_umap_clip_text_meta.json` | Repository root | Root-level project or runtime surface. |
| `/reports/ui_audit/RELEASE_ADDENDUM.md` | Repository root | Root-level project or runtime surface. |
| `/reports/ui_surface_audits/2026-05-19-pipeline-surface-audit.md` | Repository root | Root-level project or runtime surface. |
| `/requirements-baseline-lock.txt` | Repository root | Root-level project or runtime surface. |
| `/retrieval/__init__.py` | Repository root | Root-level project or runtime surface. |
| `/retrieval/multimodal_search.py` | Repository root | Root-level project or runtime surface. |
| `/retrieval/narrative_summarizer.py` | Repository root | Root-level project or runtime surface. |
| `/retrieval/temporal_reasoning.py` | Repository root | Root-level project or runtime surface. |
| `/samples/README.md` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S02_opening_presenter_alpha.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S02_opening_presenter_audio_matched.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S05_preflight_presenter_alpha.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S05_preflight_presenter_audio_matched.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S14_final_landing_presenter_alpha.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/avatar/S14_final_landing_presenter_audio_matched.webm` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/01-clone-official-source.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/02-enter-project-cabin.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/03-bootstrap-installer.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/04-env-local-root.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/05-bootstrap-validator.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/06-launch-goodq.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/07-watchdog-observes.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/demo-steps/08-proof-recorded.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/goodq4all-demo-endcard.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/goodq4all-demo-poster.jpg` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/install_walkthrough.gif` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/install_walkthrough.mp4` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/manifest.json` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/nasa_descent.gif` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/nasa_launch.gif` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/one_click_installer_mockup.png` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/q-git-square.png` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/q-multicolor-square.png` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/q-white-square.png` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/retro_console_preview.png` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/ui_onboarding_walkthrough.gif` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/ui_onboarding_walkthrough.mp4` | Repository root | Root-level project or runtime surface. |
| `/samples/assets/ui_onboarding_walkthrough_raw.mp4` | Repository root | Root-level project or runtime surface. |
| `/samples/ingestion/anger_elimination.pdf` | Repository root | Root-level project or runtime surface. |
| `/samples/onboarding_fixture.mp4` | Repository root | Root-level project or runtime surface. |
| `/scripts/INSTALL_AUDIO_DIARIZE_ENV.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/INSTALL_WSL2_AUDIO.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/PIN_MODEL_VERSIONS.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/README.md` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/RUN_GPU_OPTIMIZATION.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/SETUP_WEB_DEPENDENCIES.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/TEST_GPU_PIPELINE.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/VERIFY_MODEL_LOCKDOWN.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/_lib/interpreter_bindings.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/_lib/interpreter_bindings.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analytics_cli.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analytics_dashboard.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analytics_engine.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analytics_query.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analyze_database.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analyze_kg_gaps.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analyze_sample_output.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/analyze_unified_kg.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/apply_performance_fixes.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/apply_scene_summaries.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audio_gpu_monitor.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audio_gpu_report.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audit_all_exceptions.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audit_codebase.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audit_llm.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audit_vision_gpu.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/audit_vision_pipeline.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/benchmark_vllm_quantization.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_install.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_install_unix.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_models.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_onboarding.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_validate.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/bootstrap_verify.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/build_identity_ledger.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/build_kg_standalone.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/build_knowledge_graph_from_db.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/build_unified_kg.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/cache_readiness_check.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/check_qdrant.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/clean_old_processing.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/comprehensive_gpu_setup.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/config_schema.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/dataset_specs.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/debug_kg_input.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/debug_kg_structure.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/deep_scene_analysis.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/dev/run_pytest.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/dev/run_r18_validator_suite.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/dev/run_runtime_evidence.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnose_gpu_issue.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnose_gpu_pipeline.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnose_transcription.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/FULL_SYSTEM_AUDIT.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/FULL_SYSTEM_TEST.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/RUN_FULL_DIAGNOSTIC.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/RUN_HEALTH_CHECK.lnk` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/audit_gpu_steps.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/check_atomic_writes.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/check_dbs.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/check_drive_roots.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/check_latest_results.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/check_silent_suppression.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/episode_reference_eval.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/monitor_progress.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/native_model_stability_smoke.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/pipeline_witness_sheet.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/quick_laptop_test.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/diagnostics/scene_context_debug.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/banned_token_lint.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/build_current_state.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/dependency_drift_lint.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/doc_authority_lint.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/doc_drift_lint.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/docs/runtime_path_authority_audit.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/download_datasets.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/extract_test_frame.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/extract_test_frame.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/final_validation_report.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/find_transcription_data.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/fix_imports.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/fix_pyannote_gpu.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/full_diagnostic_check.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/generate_goodq4all_agent_status.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/generate_post_manifest.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/generate_quantization_assets.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/generate_system_snapshot.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/get_processing_report.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/gpu_config.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/gpu_config_injector.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/gpu_config_tuner.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/gpu_pipeline_optimizer.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/gpu_setup_windows.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/health/pull_health_export.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/__init__.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/build_face_clusters.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/build_speaker_clusters.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/extract_name_mentions.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/promote_context_layer.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/promote_identity_layer.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/identity/validate_roster.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/implement_comprehensive_vad.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/init_qdrant_collections.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/inspect_db.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/LAUNCH_GOODQ.go` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/build_installer.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/generate_manifest.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/goodq4all_installer.nsi` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/launcher_unix.go` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/launcher_windows.go` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/preflight_check.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/sandbox_env_setup.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/sign_manifest.go` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/smoke_test_restore.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/stage_dependencies.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/sync_nsi_version.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/verify_offline_suite.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install/versioninfo.json` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_audio_deps_retry.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_gpu_support.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_pipeline_windows.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_pipeline_wsl.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_vad.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_vision_gpu.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/install_vision_gpu.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/internal/verify_entity_quality.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/login_hf.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitor_gpu_pipeline.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitor_ingestion.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitor_ingestion_progress.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitor_ingestion_realtime.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitor_processing.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitoring/monitor_ingestion.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/monitoring/monitor_live.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/optimize_config.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/optimize_vision_gpu.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_completion_report.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_embedding_analysis.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_fixes.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_llm_integration.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_progress_report.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase2_verify.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase3_diagnostic.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/phase5_full_validation.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/pin_model_versions.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/preflight_check.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/prepare_step_envs.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/promote_wsl_audio.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/CHECK_QDRANT.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/INIT_QDRANT.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/INSTALL_QDRANT_SERVICE.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/START_QDRANT.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/qdrant/prepare_clean_slate.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/query_db_simple.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/quick_analysis.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/quick_gpu_test.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/reorganize_docs.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/repair_temporal_projection_gaps.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/restart_llm_services.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/restart_llm_services.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/rotate_logs.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/run_audio_diarize_test.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/run_control_agent.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/run_gpu_optimization_tests.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/run_vision_audit.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/run_vision_optimization.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/scientific_benchmark.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/season3_feature_ladder.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/seg_p5_authoritative_compare.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/seg_p5_promotion_envelope.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/segmentation_shadow_campaign.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup-qdrant-net.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/INSTALL_WEB_DEPS.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/VALIDATE_PYTHON_PATHS.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/configure_envs_pythonpath.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/install_goodq.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/install_package_all_envs.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup/start_agents.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup_gpu_environments.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup_wsl2_audio.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup_wsl2_audio_fast.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/setup_wsl2_audio_userspace.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/show_intelligence_report.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/show_kg_insights.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/show_phase2_enhancement.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/smoke_phase_a.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/start_api.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/start_ollama_fallback.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/start_vllm_servers.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/status_vllm_servers.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/stop_vllm_servers.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/sync_env_local.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/sync_faiss_to_qdrant.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/system_readiness_check.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/system_status_check.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_all_endpoints.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_gpu_config.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_gpu_scene_detection.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_llm_client.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_preflight_concurrency.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_vad_gpu_usage.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_vision_gpu.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_vllm_from_windows.ps1` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_wsl2_bridge.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/test_wsl2_bridge_integrity.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/ucf/generate_birth_certificate.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/ucf/maintenance/heal_ucf_ledger.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/ucf/ucf_ledger.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/ucf/validate_ucf_epoch.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utilities/backup_gpu_steps.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utilities/gpu_config.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utilities/llm_client.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utils/banned_token_lint.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utils/check_watchdog_status.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utils/verify_command_center.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utils/verify_model_lockdown.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/utils/verify_phase1_fix.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/validate_gpu_setup.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/verify_audio_provisioning.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/verify_parity.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/vllm_control.bat` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/install_audio_service.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/install_vllm_service.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/monitor.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/qdrant_network_validator.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/smoke_wsl_memory.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl/update_vllm_service_port.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl2_audio_bridge.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl2_process_audio.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl2_quick_install.sh` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/scripts/wsl_audio_preflight.py` | Tooling | Operator, validation, bootstrap, or development utility. |
| `/setup.py` | Repository root | Root-level project or runtime surface. |
| `/start_goodq_dev.ps1` | Repository root | Root-level project or runtime surface. |
| `/steps/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/audio_wsl2_bridge.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/orchestrator.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase0_normalization.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase1_vad_segmentation.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase2_pyannote.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase3_chunk_builder.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase4_audio_processor.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase5_video_scene_integration.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio/segmentation/phase6_integration.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_diarize/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_diarize/step_wsl2.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_diarize/vad_preprocessor.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_embed_clap/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_ingest_unified/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_ingest_unified/step_wsl2.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_metadata/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_music_events/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_speaker_merge/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_time_hints/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_transcribe/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_transcribe/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/audio_transcribe/step_wsl2.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/atomic_io.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/audio_gpu_optimizer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/canonical_sensitive_events.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/clean_memory.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/clean_memory_protected_manifest.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/clean_memory_windows_program_data_locator.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/clean_memory_windows_reader_identity.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/conda_runner.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/config_loader.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/config_redaction.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/context_analyzer_llm.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/device_config.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/epistemic_diff.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/epistemic_formatter.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/faiss_utils.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/gpu_config.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/gpu_guard.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/lexicon.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/llm_model_factory.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_commit_events.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_context_writer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_manager.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_provenance.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_router.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_store.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_stores.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/memory_writer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/model_cache_inspector.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/model_provisioner.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/non_action_contract.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/platform_config.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/profile_config.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/progress_tracker.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/qdrant_client.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/quantization.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/retrieval_events.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/retry.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/safe_access.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/scene_summarizer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/sensitive_staging.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/sqlite_read_authority.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/step_logger.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/tag_utils.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/tool_paths.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/tool_resolver.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/vad_preprocessor.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/windows_held_handle.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/common/windows_security_mechanics.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/discover_sources/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/discover_sources/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/emotion_classify/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/emotion_classify/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/face_embed/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/face_embed/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/graph_builder/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/graph_builder/emotion_arc_analyzer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/graph_builder/graph_builder.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/graph_builder/llm_enrichment.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/health_auto_export/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/health_auto_export/adapter.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/health_auto_export/normalizer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/home_assistant_status/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/home_assistant_status/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_caption/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_caption/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_embed_clip/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_embed_dino/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_exif/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_ocr/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/image_ocr/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/llm_chat/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/llm_chat/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/object_detect/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/object_detect/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/object_track_yolo/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/overview/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/pdf_text/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/pdf_text/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/sentiment/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/sentiment/step_fixed.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/system_metrics/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/system_metrics/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/tagger/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/tagger/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/tagger/step_llm_enhanced.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/text_embed/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/text_embed/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/tts/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/tts/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/cross_modal_harmonizer.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/embedding_pooler.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/entity_extractor.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/scene_embedder.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/scene_frame_extractor.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video/scene_visual_embeddings.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video_ingest/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video_scene_detect/gpu_scene_detect.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video_scene_detect/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video_summarizer/__init__.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/steps/video_summarizer/step.py` | Pipeline | Pipeline processing step or shared step utility. |
| `/tests/README.md` | Verification | Test, fixture, or verification asset. |
| `/tests/__init__.py` | Verification | Test, fixture, or verification asset. |
| `/tests/agents/test_challenger_concurrency_database.py` | Verification | Test, fixture, or verification asset. |
| `/tests/agents/test_mini_agent_audit.py` | Verification | Test, fixture, or verification asset. |
| `/tests/agents/test_mini_agent_client.py` | Verification | Test, fixture, or verification asset. |
| `/tests/check_syntax.bat` | Verification | Test, fixture, or verification asset. |
| `/tests/conftest.py` | Verification | Test, fixture, or verification asset. |
| `/tests/e2e/test_agent_workspace.py` | Verification | Test, fixture, or verification asset. |
| `/tests/e2e/test_staged_ingestion_harness.py` | Verification | Test, fixture, or verification asset. |
| `/tests/identity/__init__.py` | Verification | Test, fixture, or verification asset. |
| `/tests/identity/test_retrieval_regression.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/__init__.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_governance_validators.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_qdrant_id_normalization.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_qdrant_lifecycle_coverage.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_runtime_profile_services.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_smoke_benchmark.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_audio_logging.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_ingestion.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_multi_source.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_qdrant_challenger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_regression.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_retrieval_bridge.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_retrieval_bridge_stress.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_stress.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_transition_atomicity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_validator.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_vector_integrity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_ucf_visual_logging.py` | Verification | Test, fixture, or verification asset. |
| `/tests/integration/test_watchdog.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/LAUNCH_WEB_INTERFACE.bat.old` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/LAUNCH_WEB_INTERFACE_FIXED.bat.old` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/README.md` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/integration_harnesses/test_ingestion_verbose.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/integration_harnesses/test_scene_comprehensive.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/integration_harnesses/verify_clip.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/run_test_ingestion.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_analytics_query.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_analytics_sample.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_audio_diarize_optimized.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_audio_pipeline_comprehensive.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_config_nesting.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_consolidation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_diarization_chunking.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_diarize_status.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_direct_run.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_entities.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_full_pipeline_llm.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_gpu_management.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_ingestion.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_ingestion_debug.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_ingestion_fix.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_ingestion_simple.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_kg_build.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_llm_client.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_llm_integration.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_module_import.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase2_verification.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase3_llm_integration.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase3_standalone.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase4_audio.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase6.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase6_harness.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase6_kg_integration.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_phase7_analytics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_pipeline_gpu.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_python_paths.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_sample.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_scene_detection_config.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_scene_structure.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_scene_summarizer.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_segment_text.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_vad_diarization.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_validation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/test_wsl_audio.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/root_harnesses/validate_analytics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_audio_diarize_cuda_path.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_audio_duration_wave_fallback.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_audio_transcribe_backend_unavailable.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_audio_transcribe_fw_contract.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_db_creation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_knowledge_graph.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/test_memory_context.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/__init__.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/quick_test_storage.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/test_clean_run.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/test_hf_auth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/test_mission_logger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/validate_all_steps.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/validate_ingestion_output.py` | Verification | Test, fixture, or verification asset. |
| `/tests/legacy/utilities/validate_results.py` | Verification | Test, fixture, or verification asset. |
| `/tests/runtime_evidence_manifest.json` | Verification | Test, fixture, or verification asset. |
| `/tests/runtime_profile.py` | Verification | Test, fixture, or verification asset. |
| `/tests/test_face_output.json` | Verification | Test, fixture, or verification asset. |
| `/tests/test_input.json` | Verification | Test, fixture, or verification asset. |
| `/tests/test_launcher.ps1` | Verification | Test, fixture, or verification asset. |
| `/tests/test_qdrant_payload_invariant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/test_runtime_wiring_fixes.py` | Verification | Test, fixture, or verification asset. |
| `/tests/test_sample_ingest.bat` | Verification | Test, fixture, or verification asset. |
| `/tests/test_scene_input.json` | Verification | Test, fixture, or verification asset. |
| `/tests/test_scene_output.json` | Verification | Test, fixture, or verification asset. |
| `/tests/test_system.bat` | Verification | Test, fixture, or verification asset. |
| `/tests/test_ucf_challenger_verification.py` | Verification | Test, fixture, or verification asset. |
| `/tests/ui/test_ui_audit.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/__init__.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/api_main_test_harness.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_action_jobs.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_api_health_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_api_main_legacy_prune_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_api_route_effect_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_api_surface_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_async_dag.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_atomic_json_write.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_audio_bridge_native.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_audio_segment_timeline_normalization.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_audio_speaker_merge_step.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_baseline_audio_profile_invariant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_hardening.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_install_console.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_install_qdrant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_install_wsl.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_models_resilience.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_bootstrap_verify_model_cache.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_build_face_clusters_start_gate.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_cache_readiness_check.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_challenger_stress.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_cli.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_external_pin.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_filesystem.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_protected_boundary.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_protected_manifest.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_protected_manifest_validator.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_protected_membership.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_qdrant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_windows_program_data_locator.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_clean_memory_windows_reader_identity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_config_redaction.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_config_values.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_context_analyzer_llm.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_agent_activation_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_agent_disable_invariant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_recurrence_api.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_recurrence_output_contract.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_recurrence_recommendations.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_recurrence_report.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_control_recurrence_trend.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_crash_family_env_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_current_state_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_dev_pytest_wrapper.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_device_config.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_doc_authority_lint.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_entity_extractor_logging.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_entity_extractor_semantic_quality.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_episode_reference_eval.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_epistemic_diff_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_epistemic_formatter_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_exception_guard.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_face_embed_fallback.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_faiss_id_mapping.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_faiss_lock.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_gpu_config_console.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_healer_retry_ceiling.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_health_intake_normalizer_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_hitl_stitching.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_hybrid_search_rrf.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_epoch_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_error_redaction.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_ledger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_mutation_confirmation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_process_confirmation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_process_recovery.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_resolver_evidence.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_roster_writes.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_routes.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_search_ranking.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_workbench_behavior.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_identity_workbench_static.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_image_embed_dino_diagnostics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_image_ocr_observability.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingest_request_ledger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingest_staging_convergence.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingest_status_route.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingest_submit_route.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingest_upload_hardening.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ingestion_isolation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_installer_paths.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_kg_realtime_relationship_enrichment.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_knowledge_graph_readonly.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_legacy_wsl_audio_bridge_compat.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_llm_client_activation_policy.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_media_containment_hardening.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_memory_embedding_keying.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_memory_ephemeral_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_migrated_loaders.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_model_lifecycle.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_model_provisioner.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_multimodal_search_audio.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_multimodal_search_similar_scene.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_narrative_summarization.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_native_model_stability_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_non_action_contract_smoke.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_offline_mode_challenger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_offline_mode_robustness_challenger.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_offline_mode_stress.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_offline_packaging.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_operator_console_static.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_optional_vision_observability.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_overview_semantic_quality.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_persistent_store_alignment.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_phase6_audio_artifact_path_unified.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_phase6_critical_integrity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_phase6_exception_persists_false.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_phase6_rerun_safety.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_phase6_truth_invariant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_platform_config.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_preflight_concurrency.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_print_config.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_profile_override_metadata.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_progressive_ingestion.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_promote_identity_layer.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_qdrant_loopback_transport.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_qdrant_query_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_recovery_promotion.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_context_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_faiss_store_ref_privacy_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_model_cache_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_query_log_privacy_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_sqlite_read_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retrieval_telemetry_persistence_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_retro_console_static.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_artifact_persisted_on_failure_exit.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_index.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_audio_backend_reducer.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_audio_entity_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_content_state.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_input_file.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_modality_status.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_progress_tracking.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_step_json_errors.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_ingestion_step_observer_metadata.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_run_summary.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_runtime_evidence_runner.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_runtime_run_preview.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_runtime_status.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_runtime_test_profile.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_bundle_transaction_atomicity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_embedder_clip_fallback.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_embedder_device_fallback.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_embedder_isolation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_frame_extractor_zero_duration.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_range_filtering.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_scene_summarizer_semantic_quality.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_search_route_audio.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_search_route_enrichment.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_search_route_sentiment.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_season3_feature_ladder.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_seg_p5_authoritative_compare.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_seg_p5_promotion_envelope.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_segmentation_shadow_campaign.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_segmentation_shadow_mode.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_self_healing_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_sidecar_migration.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_step_runner_openmp_guard.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_summary_console.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_summary_console_static.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_summary_routes.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_summary_sqlite_read_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_system_engine_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_system_route_policy.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_system_stitch_confirmation.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_tag_utils_taxonomy.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_tagger_llm_enhanced_semantic_quality.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_tagger_semantic_quality.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_temporal_projection_repair.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_temporal_reasoning.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_temporal_summary_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_temporal_summary_results.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_text_embedding_identity.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_time_hint_truth.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_tool_paths_piper.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_tool_resolver.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_turboquant.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ucf_canonical_loader.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ucf_promotion_cli.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_ui_conduits_audio_doctrine.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_vector_parity_artifact_persistence.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_verify_entity_quality_metrics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_video_ingest_semantic_summary.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_video_scene_detect_duration_fallback.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_video_scene_detect_entity_refine_retired.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_video_summarizer.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_vision_gpu_import_contract.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_vision_step_diagnostics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_vram_allocator.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_watchdog_processed_prefix_idempotent.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_watchdog_registry_deadlock.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_watchdog_safety.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_watchdog_stage_coverage.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_windows_held_handle.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_windows_security_mechanics.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl2_audio_bridge_cache_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl2_audio_bridge_preflight.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl2_audio_bridge_robustness.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl_audio_preflight.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl_audio_unified_bridge.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl_diarization_model_authority.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl_process_audio_diarization.py` | Verification | Test, fixture, or verification asset. |
| `/tests/unit/test_wsl_unified_clap_contract.py` | Verification | Test, fixture, or verification asset. |
| `/tests/verify_wsl_env.py` | Verification | Test, fixture, or verification asset. |
| `/ui/docs_offline/favicon.ico` | User interface | User-interface implementation or asset. |
| `/ui/docs_offline/redoc.standalone.js` | User interface | User-interface implementation or asset. |
| `/ui/docs_offline/swagger-ui-bundle.js` | User interface | User-interface implementation or asset. |
| `/ui/docs_offline/swagger-ui.css` | User interface | User-interface implementation or asset. |
| `/ui/identity_workbench/index.html` | User interface | User-interface implementation or asset. |
| `/ui/identity_workbench/static/css/identity.css` | User interface | User-interface implementation or asset. |
| `/ui/identity_workbench/static/js/identity.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/README.md` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/example_envelope.json` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/index.html` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/inspector/README.md` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/inspector/inspector.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/inspector/inspector_log.jsonl` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/css/app.css` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/js/app.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/js/integrity.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/js/test_render.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/js/types_epistemic.js` | User interface | User-interface implementation or asset. |
| `/ui/justification_v1/static/js/types_non_action.js` | User interface | User-interface implementation or asset. |
| `/ui/operator_console_v1/README.md` | User interface | User-interface implementation or asset. |
| `/ui/operator_console_v1/index.html` | User interface | User-interface implementation or asset. |
| `/ui/operator_console_v1/static/css/app.css` | User interface | User-interface implementation or asset. |
| `/ui/operator_console_v1/static/js/app.js` | User interface | User-interface implementation or asset. |
| `/ui/retro_console_v1/README.md` | User interface | User-interface implementation or asset. |
| `/ui/retro_console_v1/index.html` | User interface | User-interface implementation or asset. |
| `/ui/retro_console_v1/static/css/retro.css` | User interface | User-interface implementation or asset. |
| `/ui/retro_console_v1/static/js/retro.js` | User interface | User-interface implementation or asset. |
| `/ui/stitching_workbench/README.md` | User interface | User-interface implementation or asset. |
| `/ui/stitching_workbench/index.html` | User interface | User-interface implementation or asset. |
| `/ui/stitching_workbench/static/css/stitching.css` | User interface | User-interface implementation or asset. |
| `/ui/stitching_workbench/static/js/stitching.js` | User interface | User-interface implementation or asset. |
| `/ui/summary_console/README.md` | User interface | User-interface implementation or asset. |
| `/ui/summary_console/index.html` | User interface | User-interface implementation or asset. |
| `/ui/summary_console/static/css/summary.css` | User interface | User-interface implementation or asset. |
| `/ui/summary_console/static/js/summary.js` | User interface | User-interface implementation or asset. |
| `/vllm_wsl/INSTALLATION_REPORT.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/LLAMA_TEST_RESULTS.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/MODEL_DOWNLOAD_REPORT.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/MODEL_SCAN_REPORT.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/MODEL_SCAN_UPDATED.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/OLLAMA_INTEGRATION.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/README.md` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/activate.sh` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/configs/default.yaml` | Repository root | Root-level project or runtime surface. |
| `/vllm_wsl/configs/models.yaml` | Repository root | Root-level project or runtime surface. |
| `/wsl2_audio/CUDA_SETUP.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/HF_CLI_LOGIN_GUIDE.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/HF_QUICK_REF.txt` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/INSTALL_STATUS.txt` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/OOM_FIX.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/PIPELINE_UPGRADE.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/QUICKSTART.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/QUICK_REFERENCE.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/QUICK_START.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/README.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/TEST_RESULTS.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/WSL2_AUDIO_FIX_COMPLETE.md` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/audio_bridge.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/audio_service.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/bridge_config.json` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/check_cuda.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/config.json` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/config_wsl2_audio.json` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/fw_transcribe.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/model_cache.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/process.sh` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/process_audio.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/process_minimal.sh` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/requirements-bootstrap-constraints.txt` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/requirements-locked.txt` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/setup_cuda_env.sh` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/setup_windows.ps1` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/setup_wsl2_audio.sh` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/start_wsl2_service.bat` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/test_bridge.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/test_pipeline.py` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
| `/wsl2_audio/test_simple.sh` | WSL audio | WSL audio runtime, bootstrap, or verification asset. |
