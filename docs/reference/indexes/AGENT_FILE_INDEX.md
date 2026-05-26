<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-26 -->

# AGENT_FILE_INDEX

This is the canonical file registry for the GoodQ4All codebase. It indexes every active source file, configuration file, and document, detailing its role, architecture layer, and purpose.

## Directory Topology

- **api/**: FastAPI routes, request/response models, and server lifecycle.
- **cli/**: CLI entry points (watchdog, runner, doctor, health rollups).
- **lib/**: Core relational, vector, graph, and control logic.
- **steps/**: Isolated pipeline steps (perception, interpretation, common).
- **ui/**: Frontend consoles (Retro Memory Explorer, Stitching Workbench, Summary Console).
- **wsl2_audio/**: WSL-side compute and models for speech, VAD, and transcription.
- **configs/**: Global configuration schemas and model registries.
- **scripts/**: Developer utilities, installation bootstrap, and tests support.
- **tests/**: Unit and integration test suites.
- **docs/**: Architectural, user, and operator guides.

## Active File Registry

| File Path | Component / Layer | Purpose Summary |
|---|---|---|
| `/.agents/skills/goodq4all-operator/SKILL.md` | Generic | No description provided. |
| `/.env.agents` | Generic | No description provided. |
| `/.env.local.template` | Generic | No description provided. |
| `/.env.model_cache` | Generic | No description provided. |
| `/.env.template` | Generic | No description provided. |
| `/.gitattributes` | Generic | No description provided. |
| `/.gitignore` | Generic | No description provided. |
| `/.ignore` | Generic | No description provided. |
| `/AGENTS.md` | Generic | No description provided. |
| `/CHANGELOG.md` | Generic | No description provided. |
| `/CODE_OF_CONDUCT.md` | Generic | No description provided. |
| `/CONTRIBUTING.md` | Generic | No description provided. |
| `/LAUNCH_GOODQ.bat` | Script / CLI | GoodQ4All Master Launcher (Batch Wrapper) |
| `/LAUNCH_GOODQ.ps1` | Script / CLI | GoodQ4All Master Launcher |
| `/LICENSE` | Generic | No description provided. |
| `/README.md` | Generic | No description provided. |
| `/SECURITY.md` | Generic | No description provided. |
| `/SUPPORT.md` | Generic | No description provided. |
| `/THIRD_PARTY_NOTICES.md` | Generic | No description provided. |
| `/__init__.py` | Generic | No description provided. |
| `/agents/README.md` | Generic | No description provided. |
| `/agents/__init__.py` | Script / CLI | GoodQ Agent System |
| `/agents/analysis/__init__.py` | Script / CLI | GoodQ Agent System |
| `/agents/base_agent.py` | Script / CLI | Base agent class for GoodQ agents. |
| `/agents/config_healer.py` | Script / CLI | GoodQ4All Config Auto-Healer - Phase 2: Autonomous Recovery |
| `/agents/control_agent.py` | Script / CLI | GoodQ4All Pipeline Control Agent - Phase 2: Observer, Advisor & Healer |
| `/agents/ingestion/__init__.py` | Script / CLI | GoodQ Agent System |
| `/agents/ingestion/scene_detector.py` | Script / CLI | Scene Detector Agent - Detects scene boundaries in videos. |
| `/agents/knowledge/__init__.py` | Script / CLI | GoodQ Agent System |
| `/agents/llm_agent.py` | Script / CLI | LLM Agent - Provides LLM capabilities for analysis, summarization, and self-healing |
| `/agents/recovery_db.py` | Script / CLI | GoodQ4All Recovery Database - Phase 2 |
| `/agents/recovery_strategies.py` | Script / CLI | Recovery Strategies Database for Control Agent Self-Healing |
| `/agents/self_healing_monitor.py` | Script / CLI | Self-Healing Monitor |
| `/api/API_DOCUMENTATION.md` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/main.py` | FastAPI Server | API entry point and route setup; mounts static directories for UI consoles. |
| `/api/requirements.txt` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/routes/__init__.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/routes/control_recurrence.py` | FastAPI Server | Endpoints exposing recurrence reports, trends, and recommendations. |
| `/api/routes/ingest.py` | FastAPI Server | Endpoints exposing the ingestion pipeline status and cli progress. |
| `/api/routes/media.py` | FastAPI Server | Endpoints serving visual keyframe image files and audio clips. |
| `/api/routes/meta.py` | FastAPI Server | Endpoints exposing system metadata, build details, and environment configurations. |
| `/api/routes/run_index.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/routes/run_summary.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/routes/runtime.py` | FastAPI Server | Endpoints for live runtime checkups, GPU stats, WSL2 status, and inventory. |
| `/api/routes/scenes.py` | FastAPI Server | Endpoints serving detailed scene lists and single scene inspection records. |
| `/api/routes/search.py` | FastAPI Server | Endpoints supporting multimodal search queries fusing text, CLIP, DINO, and CLAP. |
| `/api/routes/summary.py` | FastAPI Server | Endpoints exposing aggregated stats, mood maps, and stitched people profiles. |
| `/api/routes/system.py` | FastAPI Server | Endpoints for triggering manual stitch mappings, revokes, and list unstitched voices. |
| `/api/routes/timeline.py` | FastAPI Server | Endpoints serving the full video temporal index and timeline rollups. |
| `/api/server.py` | FastAPI Server | FastAPI server runner binding to default port 30000 or config/env overrides. |
| `/api/utils/__init__.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/utils/ingest_requests.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/utils/loaders.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/utils/media_projection.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/api/utils/response_models.py` | FastAPI Server | API endpoint, schema, or system server configuration. |
| `/branding/README.md` | Generic | No description provided. |
| `/branding/favicon.ico` | Generic | No description provided. |
| `/branding/goodbrand.svg` | Generic | No description provided. |
| `/branding/site.webmanifest` | Generic | No description provided. |
| `/cli/__init__.py` | Script / CLI | CLI commands |
| `/cli/conduits_build.py` | Script / CLI | Conduit Pack v1 builder (offline/on-demand). |
| `/cli/conduits_kg.py` | Script / CLI | Conduit Pack v1: UI-safe conduits for knowledge_graph.db (derived tables only). |
| `/cli/conduits_memory.py` | Script / CLI | Conduit Pack v1: UI-safe conduits for memory.db (derived tables only). |
| `/cli/conduits_processing.py` | Script / CLI | Conduit Pack v1: UI-safe conduits for processing artifacts (derived tables only). |
| `/cli/conduits_sensitive_sources.py` | Script / CLI | Sensitive Source Wiring Pack v1: UI-safe reserved conduits (derived-only; empty by default). |
| `/cli/conduits_store_stats.py` | Script / CLI | Conduit Pack v1: UI-safe store stats conduits (counts/dims only). |
| `/cli/control_recurrence_report.py` | Script / CLI | CLI entry point command or runner. |
| `/cli/goodq_doctor.py` | Script / CLI | GoodQ Doctor - Read-only ingestion preflight validator. |
| `/cli/graph_query.py` | Script / CLI | Retired compatibility shell for the historical graph query surface. |
| `/cli/links.py` | Script / CLI | Utility script for links. |
| `/cli/list_inbox.py` | Script / CLI | Utility script for list inbox. |
| `/cli/list_runs.py` | Script / CLI | Retired compatibility shell for the old run-index surface. |
| `/cli/media_refs.py` | Script / CLI | GoodQ UI-safe media reference tokens (local-only). |
| `/cli/memory.py` | Script / CLI | exit non-zero if error or warning |
| `/cli/monitor_ingestion.py` | Script / CLI | GoodQ4All - Live Ingestion Monitor |
| `/cli/monitor_live.bat` | Script / CLI | Live Ingestion Monitor - Shows real-time progress |
| `/cli/nl_query.py` | Script / CLI | Natural Language Query Interface for Knowledge Graph |
| `/cli/observability_health.py` | Script / CLI | GoodQ Observability Health Report (read-only). |
| `/cli/observability_rollup.py` | Script / CLI | GoodQ Observability Rollups (offline/on-demand). |
| `/cli/persistent_store_alignment_audit.py` | Script / CLI | CLI entry point command or runner. |
| `/cli/print_config.py` | Script / CLI | Utility script for print config. |
| `/cli/retrieve.py` | Script / CLI | Utility script for retrieve. |
| `/cli/run_ingestion.py` | Script / CLI | Setup logger |
| `/cli/run_narrative.py` | Script / CLI | Retired compatibility shell for the old narrative reporting surface. |
| `/cli/run_summary.py` | Script / CLI | Retired compatibility shell for the old run-summary surface. |
| `/cli/step_runner.py` | Script / CLI | Add repo root to Python path so "steps.*" modules can be imported |
| `/cli/system_status.py` | Script / CLI | GoodQ4All System Status Dashboard |
| `/cli/test_ingestion.py` | Script / CLI | GoodQ4All End-to-End Ingestion Test Suite |
| `/cli/ui_conduits_rollup.py` | Script / CLI | GoodQ UI-Safe Conduits v1 (offline/on-demand). |
| `/cli/watchdog.py` | Script / CLI | GoodQ Watchdog - Automatic File Ingestion Monitor |
| `/common/gpu_manager.py` | Generic | No description provided. |
| `/common/gpu_monitor.py` | Generic | No description provided. |
| `/common/progress_tracker.py` | Generic | No description provided. |
| `/configs/__init__.py` | Generic | No description provided. |
| `/configs/config.local.example.yaml` | Generic | No description provided. |
| `/configs/config.yaml` | Configuration | Canonical system config defining directories, API port, and pipeline parameters. |
| `/configs/entities.yaml` | Generic | No description provided. |
| `/configs/model_registry.yaml` | Configuration | Hugging Face model names and commit hashes for lock-down. |
| `/configs/models_config.yaml` | Generic | No description provided. |
| `/configs/open_config.yaml` | Generic | No description provided. |
| `/configs/paths.py` | Generic | No description provided. |
| `/configs/python_paths.py` | Generic | No description provided. |
| `/docs/AGENT_CAPABILITIES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/AUDIT_SUMMARY_QUICK.txt` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/CHEAT_SHEET.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/CLI-REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/CONTROL_AGENT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/HANDOFF_BASEMENT_PHASE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/PHASE6_MULTIMODAL_FUSION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/QDRANT_QUICKREF.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/QUICK_START.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/ROADMAP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/RUNTIME_AUTHORITY_MEMO.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/SCENE_MANIFEST_SPECIFICATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/SESSION_COMPLETE_WSL2_AUDIT.txt` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/START_HERE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/SYSTEM_SNAPSHOT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/TESTING_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/TROUBLESHOOTING.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/WSL2_CONSISTENCY_AUDIT_DEC15.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/WSL2_SCRIPTS_ADDED.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/agent/CURRENT_STATE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/agent/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/agent/current_state.json` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/agent/workflows/CLEAN_MEMORY_START.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/AGENT_DECISION_PROTOCOL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/AGENT_SYSTEM.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/ARCHITECTURE_REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/CANONICAL_SENSITIVE_EVENTS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/CONFIG_LOADING_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/DATA_STRUCTURE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/DOCUMENTATION_REORGANIZATION_PLAN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/DOCUMENTATION_REORGANIZATION_REPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/EPISTEMIC_READ_MODEL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/GOODQ_EXECPLAN_PROTOCOL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/HITL_STITCHING_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/IDENTITY_STITCHING_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/INGESTION_PERFORMANCE_TIMINGS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/LEGACY_WORKFLOWS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/LLM_CLIENT_INJECTION_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/MEMORY_STORAGE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/NON_ACTION_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/OFFLINE_DEPENDENCIES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/ORGANIZATION_COMPLETE_2025-11-15.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/OUTPUT_SCHEMA_INVENTORY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/PIPELINES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/PORT_ARCHITECTURE_ASSESSMENT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/PROJECT_STRUCTURE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/SUMMARY_CONSOLE_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/SYSTEM_ARCHITECTURE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/SYSTEM_MAP_v1.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/components/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/components/VISION_PIPELINE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/diagrams/PIPELINE_FLOW.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/diagrams/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/diagrams/knowledge_graph_architecture.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/diagrams/watchdog_flow.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/architecture/narrative_layer.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/CORPUS_PACK_MANIFEST.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/INSTALL_BOOTSTRAP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/REPO_GROUNDED_CLEANUP_CHECKLIST.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/SCRIPT_REGISTRY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/bootstrap_manifest.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/doc_archive_plan.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/doc_authority_map.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/doc_authority_policy.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/doc_governance_summary.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/doc_lint_ci_snippet.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/bootstrap/smoke_matrix_phase_a.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/data_epochs.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/ENV_DISCOVERY_REPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/ENV_RECONCILIATION_REPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/HOME_MEMORY_WITNESS_RUN_2026-05-22.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/HOST_COMPAT_PATCH_NOTES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/LAUNCHER_PORTABILITY_DISCOVERY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/LAUNCHER_PORTABILITY_PATCH_NOTES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/MEMORY_CLEAN_START_AUDIT_2026-05-20.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/PERCEPTION_SURFACE_AUDIT_2026-04-09.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/POWER_LOSS_INGESTION_AUDIT_2026-05-20.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/README.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x03_2026-04-11.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/SCENE_SUMMARIZER_AUDIT_2026-04-09.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/diagnostics/SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/goodq4all_agent_status.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/CONSOLIDATION_EXPLAINED.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/DEMO.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/FIRST_RUN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/QDRANT_SETUP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/SCENE_OPTIMIZATION_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/API_DEBUG_INSTRUCTIONS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/GITHUB_SETUP_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/INSTALL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/LAPTOP_INSTALL_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/LAUNCH_INSTRUCTIONS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/PROCESS_MANAGEMENT_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/PROCESS_MANAGER_QUICK_REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/PYTHON_PATH_CONFIGURATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/QUICK_START_CLEAN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/QUICK_START_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/REMAINING_STEPS_AND_RUNTIME_TESTING.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/SCRIPTS_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/USER_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/general/WATCHDOG_QUICKSTART.txt` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_FIX_SUMMARY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_ISOLATION_STRATEGY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_LLM_WSL_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_MANAGEMENT_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_MONITORING_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_OPTIMIZATION_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_PHASE_1_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_PHASE_1_TEST_RESULTS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_QUICK_START.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_REFACTOR_PROGRESS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_SCENE_DETECTION_IMPLEMENTATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/gpu/GPU_SETUP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/install/INSTALL.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/install/LAPTOP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/install/QUICKSTART.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/LLM_CLIENT_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/LLM_IMPLEMENTATION_PLAN_PHASE1.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/LLM_INFRASTRUCTURE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/LLM_INTEGRATION_ANALYSIS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/LLM_INTEGRATION_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/VLLM_SYSTEMD_SETUP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/VLLM_WSL_INSTALL_VERIFY_2026-04-10.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/llm/WSL2_AUDIO_SETUP.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/ui/JUSTIFICATION_UI.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/watchdog/WATCHDOG_CHANGELOG.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/watchdog/WATCHDOG_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/watchdog/WATCHDOG_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/watchdog/WATCHDOG_QUICKREF.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/PIPELINE_UPGRADE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/QUICK_REFERENCE_WSL2.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/START_HERE_WSL2.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/WSL2_AUDIO_FEASIBILITY_ANALYSIS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/WSL2_BENCHMARKS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/guides/wsl2/test_pipeline.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/API.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/DEPENDENCIES.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/GPU_CAPABILITY_MATRIX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/PLATFORM_SUPPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/WSL_AUDIO_RUNTIME.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/AGENT_COMMS_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/ANALYTICS_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/CODE_CLEANUP_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/DOCS_FORENSICS_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/DOCUMENTATION_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/ENVIRONMENT_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/QUICK_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/indexes/TROUBLESHOOTING_INDEX.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/quick-refs/CLI_COMMANDS_REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/quick-refs/QUICK_REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/quick-refs/QUICK_REFERENCE_CARD.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/reference/quick-refs/QUICK_REFERENCE_SETTINGS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_SHARED_RUNTIME_SCOPING_2026-05-03.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_TREND_DESIGN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_v0.4.0.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_v0.4.1.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_v0.4.2.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/RELEASE_0.1.0.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/RELEASE_0.1.1.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/SHIP_PROFILE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/releases/VENDOR_PAYLOAD_EXIT_PLAN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-04-22-truthful-ingest-facade.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-05-07-docs-root-forensics.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-05-08-wsl-wav2vec-transformers-lane.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-05-17-first-run-truth-closure.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-05-19-pipeline-surface-audit.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/superpowers/plans/2026-05-20-agent-state-and-memory-clean-start.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/systems/ERROR_HANDLING_RECOVERY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/systems/WATCHDOG_SYSTEM.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/ANALYTICS_PAGES_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/ANALYTICS_QUICK_REFERENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/ARTIFACT_LOCATION_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/AUDIO_DIARIZATION_OPTIMIZATION_PLAN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/AUDIO_GPU_IMPLEMENTATION_SUMMARY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/AUDIO_GPU_OPTIMIZATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/AUDIO_GPU_QUICK_START.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/AUDIO_VAD_OPTIMIZATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/DATA_FLOW_DIAGRAM.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/KNOWLEDGE_GRAPH_IMPLEMENTATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/LEGACY_PATHS_DEPRECATED.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/LIB_COMPONENTS.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/LOGGING_AND_RESILIENCE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/MODEL_LOCKDOWN.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/MODEL_LOCKDOWN_IMPLEMENTATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/MODEL_LOCKDOWN_QUICK_REF.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PHASE5_FINAL_ACTIVATION_SUMMARY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PIPELINE_DEEP_DIVE_REPORT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PIPELINE_DIAGNOSIS_2025-11-11.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PIPELINE_ENGINES_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PIPELINE_ENGINES_UI_UPDATE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/PIPELINE_RESTORATION_BACKLOG.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/SCENE_EXPLORER_DEPLOYMENT_GUIDE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/SECRETS_ENV_MIGRATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/SESSION_SUMMARY_2025-12-05.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/VAD_AND_GPU_OPTIMIZATION_COMPLETE.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/VAD_IMPLEMENTATION_SUMMARY.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/VISION_GPU_OPTIMIZATION.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/technical/knowledge_graph.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON1_MAIN_BENCHMARK_MEMO_2026-04-08.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON1_SEASON2_FORENSIC_COMPARISON_MEMO_2026-04-25.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON3_FIVE_EPISODE_RUNBOOK_2026-04-11.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/SEASON3_TREATMENT_LADDER_MEMO_2026-04-11.md` | Documentation | System guide, architecture reference, or release notes. |
| `/docs/testing/validation/run_narrative_validation.md` | Documentation | System guide, architecture reference, or release notes. |
| `/environment.gpu.yml` | Generic | No description provided. |
| `/environment.yml` | Generic | No description provided. |
| `/envs/audio_diarize/requirements.txt` | Generic | No description provided. |
| `/envs/audio_embed/requirements.txt` | Generic | No description provided. |
| `/envs/audio_emotion/requirements.txt` | Generic | No description provided. |
| `/envs/audio_metadata/requirements.txt` | Generic | No description provided. |
| `/envs/audio_transcribe/requirements.txt` | Generic | No description provided. |
| `/envs/emotion_classify/requirements.txt` | Generic | No description provided. |
| `/envs/face_embed/KNOWN_ISSUES.md` | Generic | No description provided. |
| `/envs/face_embed/requirements.txt` | Generic | No description provided. |
| `/envs/home_assistant_status/requirements.txt` | Generic | No description provided. |
| `/envs/image_caption/requirements.txt` | Generic | No description provided. |
| `/envs/llm_chat/requirements.txt` | Generic | No description provided. |
| `/envs/locks/README.md` | Generic | No description provided. |
| `/envs/locks/audio_diarize.lock.txt` | Generic | No description provided. |
| `/envs/locks/audio_embed.lock.txt` | Generic | No description provided. |
| `/envs/locks/audio_emotion.lock.txt` | Generic | No description provided. |
| `/envs/locks/audio_metadata.lock.txt` | Generic | No description provided. |
| `/envs/locks/audio_transcribe.lock.txt` | Generic | No description provided. |
| `/envs/locks/emotion_classify.lock.txt` | Generic | No description provided. |
| `/envs/locks/face_embed.lock.txt` | Generic | No description provided. |
| `/envs/locks/home_assistant_status.lock.txt` | Generic | No description provided. |
| `/envs/locks/image_caption.lock.txt` | Generic | No description provided. |
| `/envs/locks/llm_chat.lock.txt` | Generic | No description provided. |
| `/envs/locks/object_detect.lock.txt` | Generic | No description provided. |
| `/envs/locks/object_track_yolo.lock.txt` | Generic | No description provided. |
| `/envs/locks/ocr.lock.txt` | Generic | No description provided. |
| `/envs/locks/pdf_text.lock.txt` | Generic | No description provided. |
| `/envs/locks/sentiment.lock.txt` | Generic | No description provided. |
| `/envs/locks/system_metrics.lock.txt` | Generic | No description provided. |
| `/envs/locks/tagger.lock.txt` | Generic | No description provided. |
| `/envs/locks/text_embed.lock.txt` | Generic | No description provided. |
| `/envs/locks/tts.lock.txt` | Generic | No description provided. |
| `/envs/locks/video_scene_detect.lock.txt` | Generic | No description provided. |
| `/envs/object_detect/requirements.txt` | Generic | No description provided. |
| `/envs/object_track_yolo/requirements.txt` | Generic | No description provided. |
| `/envs/ocr/requirements.txt` | Generic | No description provided. |
| `/envs/pdf_text/requirements.txt` | Generic | No description provided. |
| `/envs/sentiment/requirements.txt` | Generic | No description provided. |
| `/envs/system_metrics/requirements.txt` | Generic | No description provided. |
| `/envs/tagger/requirements.txt` | Generic | No description provided. |
| `/envs/text_embed/requirements.txt` | Generic | No description provided. |
| `/envs/tts/requirements.txt` | Generic | No description provided. |
| `/envs/video_scene_detect/requirements.txt` | Generic | No description provided. |
| `/goodq_version.py` | Generic | No description provided. |
| `/lib/control_recurrence_hygiene.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/control_recurrence_index.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/control_recurrence_recommendations.py` | Core Logic | Calculates and emits operator warnings/hints based on latency and errors. |
| `/lib/control_recurrence_report.py` | Core Logic | Orchestrates and writes the recurrence reports comparing different run ledgers. |
| `/lib/control_recurrence_trend.py` | Core Logic | Computes performance trends and regressions across sequential runs. |
| `/lib/goodq_logger.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/identity_ledger.py` | Core Logic | Manages read/write mapping updates to human-in-the-loop manual voice stitching JSON. |
| `/lib/kg_realtime_integration.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/knowledge_graph.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/llm_client.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/mission_components.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/observability/__init__.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/observability/event_types.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/observability/observer.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/persistent_store_alignment.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/run_index.py` | Core Logic | Builds the index of completed ingestion runs and direct CLI output directories. |
| `/lib/run_narrative.py` | Core Logic | Core database, vector, or reasoning engine module. |
| `/lib/run_summary.py` | Core Logic | Parses individual scene_ingest_results.json files to produce run-wide summary stats. |
| `/lib/summary_aggregator.py` | Core Logic | Aggregates temporal, emotion, and entity metrics across scenes for the Summary Console. |
| `/pipelines/__init__.py` | Generic | No description provided. |
| `/pipelines/direct_ingestion.py` | Generic | No description provided. |
| `/processing_onboarding/_resolved_config.json` | Generic | No description provided. |
| `/pytest.ini` | Generic | No description provided. |
| `/reports/README.md` | Generic | No description provided. |
| `/reports/control_recurrence/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness.md` | Generic | No description provided. |
| `/reports/control_recurrence/20260424_182406_season2_fresh_witness.md` | Generic | No description provided. |
| `/reports/reference_anchors/seinfeld/episodes/03x10_the_stranded.reference.json` | Generic | No description provided. |
| `/reports/reference_anchors/seinfeld/episodes/03x11_the_alternate_side.reference.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/README.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/POST_WITNESS_ANALYTICS_COMPARISON_2026-03-09.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/SEASON1_WITNESS_RUN_2026-03-09.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/embedding_health_report.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/entity_analysis_report.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/experiment_summary.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/kg_structure_report.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/post_witness_analytics_metrics_2026-03-09.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/scene_segmentation_report.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/diagnostics/semantic_pattern_report.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/README.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/artifact_manifest.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/ingestion_stderr.log` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/optional_step_failures.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/per_episode_coverage.csv` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_metrics_2026-03-10.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_optional_status_2026-03-10.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/reliability_validation_stderr_2026-03-10.log` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/resolved_config_snapshot.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/resolved_config_snapshot_2026-03-10.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/retrieval_anchor_checks.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10.csv` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10.svg` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_2026-03-10_metadata.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/scene_embedding_map_2d_labeled_2026-03-10.svg` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/semantic_comparison_metrics_2026-03-10.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/semantic_comparison_report_2026-03-10.md` | Generic | No description provided. |
| `/reports/seinfeld_experiment/releases/season1_witness_run_2026-03-09/witness_metrics.json` | Generic | No description provided. |
| `/reports/seinfeld_experiment/umap/generate_umap_clip_text.py` | Generic | No description provided. |
| `/reports/seinfeld_experiment/umap/scene_umap_clip_text_coords.csv` | Generic | No description provided. |
| `/reports/seinfeld_experiment/umap/scene_umap_clip_text_meta.json` | Generic | No description provided. |
| `/reports/ui_surface_audits/2026-05-19-pipeline-surface-audit.md` | Generic | No description provided. |
| `/retrieval/__init__.py` | Generic | No description provided. |
| `/retrieval/multimodal_search.py` | Generic | No description provided. |
| `/samples/README.md` | Generic | No description provided. |
| `/samples/assets/avatar/S02_opening_presenter_alpha.webm` | Generic | No description provided. |
| `/samples/assets/avatar/S02_opening_presenter_audio_matched.webm` | Generic | No description provided. |
| `/samples/assets/avatar/S05_preflight_presenter_alpha.webm` | Generic | No description provided. |
| `/samples/assets/avatar/S05_preflight_presenter_audio_matched.webm` | Generic | No description provided. |
| `/samples/assets/avatar/S14_final_landing_presenter_alpha.webm` | Generic | No description provided. |
| `/samples/assets/avatar/S14_final_landing_presenter_audio_matched.webm` | Generic | No description provided. |
| `/samples/assets/manifest.json` | Generic | No description provided. |
| `/samples/ingestion/anger_elimination.pdf` | Generic | No description provided. |
| `/scripts/INSTALL_AUDIO_DIARIZE_ENV.bat` | Script / CLI | ================================================================================ |
| `/scripts/INSTALL_WSL2_AUDIO.bat` | Script / CLI | GoodQ4All - WSL2 Audio Setup Launcher |
| `/scripts/PIN_MODEL_VERSIONS.bat` | Script / CLI | Fetch and pin exact model versions (commit SHAs) from HuggingFace Hub |
| `/scripts/README.md` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/RUN_GPU_OPTIMIZATION.bat` | Script / CLI | ============================================================================= |
| `/scripts/SETUP_WEB_DEPENDENCIES.bat` | Script / CLI | GoodQ Environment Setup & Dependency Installer |
| `/scripts/TEST_GPU_PIPELINE.bat` | Script / CLI | ================================================================================ |
| `/scripts/VERIFY_MODEL_LOCKDOWN.bat` | Script / CLI | Verify that all models are properly locked down with exact versions |
| `/scripts/_lib/interpreter_bindings.bat` | Script / CLI | Shared interpreter binding helpers for GoodQ4All batch scripts. |
| `/scripts/_lib/interpreter_bindings.ps1` | Script / CLI | Shared interpreter binding helpers for GoodQ4All scripts. |
| `/scripts/analytics_cli.py` | Script / CLI | GoodQ Analytics CLI |
| `/scripts/analytics_dashboard.py` | Script / CLI | GoodQ Analytics Dashboard |
| `/scripts/analytics_engine.py` | Script / CLI | GoodQ Analytics Engine - Phase 7 |
| `/scripts/analytics_query.py` | Script / CLI | Interactive Analytics Query Interface |
| `/scripts/analyze_database.py` | Script / CLI | Get all tables |
| `/scripts/analyze_kg_gaps.py` | Script / CLI | Analyze what data is available vs what's being extracted to knowledge graph |
| `/scripts/analyze_sample_output.py` | Script / CLI | Analyze sample.mp4 processing output from memory.db. |
| `/scripts/analyze_unified_kg.py` | Script / CLI | Analyze Unified Knowledge Graph - Phase 8 |
| `/scripts/apply_performance_fixes.py` | Script / CLI | Apply performance optimizations to GoodQ configuration. |
| `/scripts/apply_scene_summaries.py` | Script / CLI | Apply Scene Summarization to All Existing Scenes |
| `/scripts/audio_gpu_monitor.py` | Script / CLI | Real-Time Audio GPU Monitor |
| `/scripts/audio_gpu_report.py` | Script / CLI | Audio GPU Performance Report Generator |
| `/scripts/audit_all_exceptions.py` | Script / CLI | [SEARCH] Comprehensive Exception Handler Audit for GoodQ |
| `/scripts/audit_codebase.py` | Script / CLI | Comprehensive code audit to find silent failures and suspicious patterns |
| `/scripts/audit_vision_gpu.py` | Script / CLI | Comprehensive Vision Stack Audit |
| `/scripts/audit_vision_pipeline.py` | Script / CLI | GoodQ4All - Vision Pipeline Functionality Audit |
| `/scripts/bootstrap_install.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/bootstrap_models.py` | Script / CLI | Ensure vendored dependencies (e.g., huggingface_hub) are importable |
| `/scripts/bootstrap_onboarding.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/bootstrap_validate.bat` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/bootstrap_verify.py` | Script / CLI | Read-only bootstrap verification for clone readiness. |
| `/scripts/build_identity_ledger.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/build_kg_standalone.py` | Script / CLI | Build Knowledge Graph from Database - Standalone Version |
| `/scripts/build_knowledge_graph_from_db.py` | Script / CLI | Build Knowledge Graph from Database |
| `/scripts/build_unified_kg.py` | Script / CLI | Build Unified Knowledge Graph - Phase 8 |
| `/scripts/cache_readiness_check.py` | Script / CLI | Cache readiness checker for goodq4all assets and models. |
| `/scripts/clean_old_processing.py` | Script / CLI | Clean Old Processing Files |
| `/scripts/comprehensive_gpu_setup.py` | Script / CLI | Comprehensive GPU Setup & Verification for GoodQ4All |
| `/scripts/config_schema.py` | Script / CLI | GoodQ4All Canonical Configuration Schema |
| `/scripts/dataset_specs.py` | Script / CLI | Utility script for dataset specs. |
| `/scripts/debug_kg_input.py` | Script / CLI | Test with debug output to see what's being passed to KG functions |
| `/scripts/debug_kg_structure.py` | Script / CLI | Debug why certain fields aren't being extracted |
| `/scripts/deep_scene_analysis.py` | Script / CLI | Get video hash |
| `/scripts/dev/run_pytest.ps1` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnose_gpu_issue.py` | Script / CLI | Comprehensive GPU and processing diagnostics |
| `/scripts/diagnose_gpu_pipeline.py` | Script / CLI | Comprehensive GPU Pipeline Diagnostic Tool |
| `/scripts/diagnose_transcription.py` | Script / CLI | Diagnostic script for audio transcription issues. |
| `/scripts/diagnostics/FULL_SYSTEM_AUDIT.py` | Script / CLI | COMPREHENSIVE SYSTEM AUDIT & CLEAN TEST |
| `/scripts/diagnostics/FULL_SYSTEM_TEST.bat` | Script / CLI | ================================================================================ |
| `/scripts/diagnostics/RUN_FULL_DIAGNOSTIC.ps1` | Script / CLI | ============================================================================ |
| `/scripts/diagnostics/RUN_HEALTH_CHECK.lnk` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/audit_gpu_steps.py` | Script / CLI | Scan all step directories |
| `/scripts/diagnostics/check_atomic_writes.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/check_dbs.py` | Script / CLI | Validation/test utility for check dbs. |
| `/scripts/diagnostics/check_drive_roots.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/check_latest_results.py` | Script / CLI | Check latest processing results |
| `/scripts/diagnostics/check_silent_suppression.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/episode_reference_eval.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/monitor_progress.py` | Script / CLI | Real-time progress monitor for GoodQ pipeline |
| `/scripts/diagnostics/native_model_stability_smoke.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/diagnostics/quick_laptop_test.ps1` | Script / CLI | Quick Laptop Installation Test Script |
| `/scripts/diagnostics/scene_context_debug.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/docs/doc_drift_lint.py` | Script / CLI | Lint documentation drift against Bootstrap Contract semantics. |
| `/scripts/docs/runtime_path_authority_audit.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/download_datasets.py` | Script / CLI | Load project .env so HF_TOKEN and related flags are picked up when invoked standalone |
| `/scripts/extract_test_frame.bat` | Script / CLI | Extract test frame for vision testing |
| `/scripts/extract_test_frame.py` | Script / CLI | Quick script to extract a test frame from video for vision testing |
| `/scripts/final_validation_report.py` | Script / CLI | Final Validation Report - Scene Summarization Fix |
| `/scripts/find_transcription_data.py` | Script / CLI | Get video hash |
| `/scripts/fix_imports.py` | Script / CLI | Pattern to replace |
| `/scripts/fix_pyannote_gpu.py` | Script / CLI | Fix PyAnnote GPU transfer API usage across the codebase |
| `/scripts/full_diagnostic_check.py` | Script / CLI | Full Diagnostic Check - Analyze Complete Ingestion Results |
| `/scripts/generate_goodq4all_agent_status.py` | Script / CLI | Monitoring/status utility for generate goodq4all agent status. |
| `/scripts/generate_system_snapshot.py` | Script / CLI | Utility script for generate system snapshot. |
| `/scripts/get_processing_report.py` | Script / CLI | Generate real-time processing report for the UI |
| `/scripts/gpu_config.py` | Script / CLI | GoodQ4All GPU Configuration |
| `/scripts/gpu_config_injector.py` | Script / CLI | Inject GPU Configuration into Pipeline Steps |
| `/scripts/gpu_config_tuner.py` | Script / CLI | GPU Configuration Tuner |
| `/scripts/gpu_pipeline_optimizer.py` | Script / CLI | GoodQ4All GPU Pipeline Optimizer |
| `/scripts/gpu_setup_windows.py` | Script / CLI | GPU Setup for Windows - Install PyTorch with CUDA in all GPU-capable environments |
| `/scripts/health/pull_health_export.py` | Script / CLI | Make repo-root imports work when invoked as `python scripts/health/pull_health_export.py`. |
| `/scripts/implement_comprehensive_vad.py` | Script / CLI | Comprehensive VAD Implementation Across All Audio Steps |
| `/scripts/init_qdrant_collections.py` | Script / CLI | Initialize Qdrant collections for GoodQ4All. |
| `/scripts/inspect_db.py` | Script / CLI | Quick database inspection script |
| `/scripts/install_audio_deps_retry.bat` | Script / CLI | Setup/installation utility for install audio deps retry. |
| `/scripts/install_gpu_support.ps1` | Script / CLI | GoodQ4All - Install GPU Support in All Environments |
| `/scripts/install_pipeline_windows.ps1` | Script / CLI | GoodQ4All – 00Q Pipeline Installer (Windows) |
| `/scripts/install_pipeline_wsl.py` | Script / CLI | WSL pipeline installer/repair script. |
| `/scripts/install_vad.bat` | Script / CLI | Setup/installation utility for install vad. |
| `/scripts/install_vision_gpu.bat` | Script / CLI | GoodQ4All - Vision GPU Setup Launcher |
| `/scripts/install_vision_gpu.py` | Script / CLI | Comprehensive Vision GPU Setup Script |
| `/scripts/internal/verify_entity_quality.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/monitor_gpu_pipeline.py` | Script / CLI | Real-time GPU Pipeline Monitor |
| `/scripts/monitor_ingestion.py` | Script / CLI | Real-time Ingestion Monitor with Alerting |
| `/scripts/monitor_ingestion_progress.py` | Script / CLI | GoodQ Mission Progress Monitor |
| `/scripts/monitor_ingestion_realtime.py` | Script / CLI | Real-time Ingestion Monitor |
| `/scripts/monitor_processing.py` | Script / CLI | Real-time processing monitor for GoodQ ingestion |
| `/scripts/monitoring/monitor_ingestion.bat` | Script / CLI | GoodQ4All - Live Ingestion Monitor (Non-Intrusive) |
| `/scripts/monitoring/monitor_live.bat` | Script / CLI | Check running processes |
| `/scripts/optimize_config.py` | Script / CLI | GoodQ Configuration Optimizer |
| `/scripts/optimize_vision_gpu.py` | Script / CLI | GoodQ4All - Vision Stack GPU Optimization |
| `/scripts/phase2_completion_report.py` | Script / CLI | PHASE 2 COMPLETION REPORT |
| `/scripts/phase2_embedding_analysis.py` | Script / CLI | Phase 2: Comprehensive Embedding and Knowledge Graph Analysis |
| `/scripts/phase2_fixes.py` | Script / CLI | Phase 2 Comprehensive Fixes: Embedding & Knowledge Graph Integration |
| `/scripts/phase2_llm_integration.py` | Script / CLI | Phase 2: LLM-Enhanced Semantic Analysis Integration (legacy / quarantined; requires explicit `--allow-legacy-run`) |
| `/scripts/phase2_progress_report.py` | Script / CLI | Phase 2 Progress Report |
| `/scripts/phase2_verify.py` | Script / CLI | Phase 2 Verification Script |
| `/scripts/phase3_diagnostic.py` | Script / CLI | Phase 3 Diagnostic - Identify exact issues with scene processing |
| `/scripts/phase5_full_validation.py` | Script / CLI | Phase 5: Full System Validation |
| `/scripts/pin_model_versions.py` | Script / CLI | Fetch and pin exact model versions (commit SHAs) for all HuggingFace models. |
| `/scripts/preflight_check.ps1` | Script / CLI | GoodQ Pre-Flight Check & Auto-Launcher |
| `/scripts/prepare_step_envs.ps1` | Script / CLI | Repair the supported specialized step-env pack or targeted `-Steps` selection while keeping core env variables aligned. |
| `/scripts/promote_wsl_audio.py` | Script / CLI | WSL Audio Output Promotion Script |
| `/scripts/qdrant/CHECK_QDRANT.bat` | Script / CLI | GoodQ4All - Qdrant Health Check |
| `/scripts/qdrant/INIT_QDRANT.bat` | Script / CLI | GoodQ4All - Initialize Qdrant Collections |
| `/scripts/qdrant/INSTALL_QDRANT_SERVICE.bat` | Script / CLI | GoodQ4All - Install Qdrant as Windows Service |
| `/scripts/qdrant/START_QDRANT.bat` | Script / CLI | GoodQ4All - Start Qdrant Vector Database |
| `/scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat` | Script / CLI | GoodQ4All - Uninstall Qdrant Windows Service |
| `/scripts/query_db_simple.py` | Script / CLI | Check tables |
| `/scripts/quick_analysis.py` | Script / CLI | Get counts |
| `/scripts/quick_gpu_test.py` | Script / CLI | Validation/test utility for quick gpu test. |
| `/scripts/repair_temporal_projection_gaps.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/rotate_logs.py` | Script / CLI | Log Rotation Script |
| `/scripts/run_audio_diarize_test.bat` | Script / CLI | Direct environment test for audio diarization |
| `/scripts/run_control_agent.py` | Script / CLI | Control Agent Runner - Convenience script |
| `/scripts/run_gpu_optimization_tests.py` | Script / CLI | Full GPU Pipeline Optimization Test Suite |
| `/scripts/run_vision_audit.bat` | Script / CLI | GoodQ4All - Vision Pipeline Audit |
| `/scripts/run_vision_optimization.bat` | Script / CLI | GoodQ4All - Vision Stack GPU Optimization Launcher |
| `/scripts/season3_feature_ladder.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/seg_p5_authoritative_compare.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/seg_p5_promotion_envelope.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/segmentation_shadow_campaign.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/setup-qdrant-net.ps1` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/setup/INSTALL_WEB_DEPS.ps1` | Script / CLI | GoodQ Quick Fix - Install Web Dependencies |
| `/scripts/setup/VALIDATE_PYTHON_PATHS.bat` | Script / CLI | Use conda run to avoid shell-state activation requirements. |
| `/scripts/setup/configure_envs_pythonpath.py` | Script / CLI | Configure all goodq conda environments to include the repo parent in PYTHONPATH. |
| `/scripts/setup/install_goodq.py` | Script / CLI | GoodQ4All Automated Installer |
| `/scripts/setup/install_package_all_envs.py` | Script / CLI | Install goodq4all package in editable mode across all conda environments. |
| `/scripts/setup/setup_agents.ps1` | Script / CLI | GoodQ Multi-Agent System Setup |
| `/scripts/setup/start_agents.ps1` | Script / CLI | GoodQ Agent System - Startup Script |
| `/scripts/setup_gpu_environments.bat` | Script / CLI | ================================================================================ |
| `/scripts/setup_wsl2_audio.py` | Script / CLI | GoodQ4All - WSL2 Audio Processing Setup |
| `/scripts/setup_wsl2_audio_fast.py` | Script / CLI | GoodQ4All - Fast WSL2 Audio Setup (No Sudo Required) |
| `/scripts/setup_wsl2_audio_userspace.py` | Script / CLI | GoodQ4All - WSL2 Audio Setup (User-Space Only) |
| `/scripts/show_intelligence_report.ps1` | Script / CLI | Requires -Version 5.1 |
| `/scripts/show_kg_insights.py` | Script / CLI | -*- coding: utf-8 -*- |
| `/scripts/show_phase2_enhancement.py` | Script / CLI | Utility script for show phase2 enhancement. |
| `/scripts/smoke_phase_a.py` | Script / CLI | Utility script for smoke phase a. |
| `/scripts/start_api.ps1` | Script / CLI | Manual PowerShell wrapper for the canonical local `api.server` bind surface. |
| `/scripts/start_ollama_fallback.ps1` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/start_vllm_servers.bat` | Script / CLI | GoodQ4All vLLM service startup wrapper for the current systemd-backed primary endpoint plus the WSL keepalive anchor. |
| `/scripts/status_vllm_servers.bat` | Script / CLI | GoodQ4All vLLM Server Status Check |
| `/scripts/stop_vllm_servers.bat` | Script / CLI | GoodQ4All vLLM stop wrapper; stops the canonical service and clears the WSL keepalive anchor/stale vLLM processes. |
| `/scripts/sync_env_local.ps1` | Script / CLI | Utility script for sync env local. |
| `/scripts/sync_faiss_to_qdrant.py` | Script / CLI | One-time helper to push FAISS vectors into Qdrant for long-term storage. |
| `/scripts/system_readiness_check.py` | Script / CLI | System readiness checker for the goodq4all stack. |
| `/scripts/system_status_check.py` | Script / CLI | Comprehensive System Status Check |
| `/scripts/test_all_endpoints.py` | Script / CLI | Phase 2: Comprehensive Endpoint Validation |
| `/scripts/test_gpu_config.py` | Script / CLI | Quick GPU Test - Verify GPU configuration is working |
| `/scripts/test_gpu_scene_detection.py` | Script / CLI | Test GPU-Accelerated Scene Detection |
| `/scripts/test_llm_client.py` | Script / CLI | GoodQ4All LLM client integration test for the current injected vLLM primary + Ollama fallback contract. |
| `/scripts/test_vad_gpu_usage.py` | Script / CLI | Test VAD Implementation and GPU Usage |
| `/scripts/test_vision_gpu.py` | Script / CLI | Test Vision GPU Setup |
| `/scripts/test_vllm_from_windows.ps1` | Script / CLI | Quick Windows Test Script |
| `/scripts/test_wsl2_bridge.py` | Script / CLI | Test WSL2 Audio Bridge End-to-End |
| `/scripts/test_wsl2_bridge_integrity.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/utilities/gpu_config.py` | Script / CLI | GPU Isolation and Memory Management Configuration |
| `/scripts/utilities/llm_client.py` | Script / CLI | LLM Integration Module for GoodQ |
| `/scripts/utils/check_watchdog_status.py` | Script / CLI | One-time status snapshot for the canonical watchdog runtime. |
| `/scripts/utils/verify_command_center.py` | Script / CLI | Quick verification that Command Center is fully operational |
| `/scripts/utils/verify_model_lockdown.py` | Script / CLI | Verify that all models are properly locked down with exact versions. |
| `/scripts/utils/verify_phase1_fix.py` | Script / CLI | Comprehensive verification of Phase 1 fix - Segment text storage |
| `/scripts/validate_gpu_setup.bat` | Script / CLI | ================================================================================ |
| `/scripts/verify_audio_provisioning.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/vllm_control.bat` | Script / CLI | Utility script for vllm control. |
| `/scripts/wsl/install_audio_service.sh` | Script / CLI | Install/enable systemd service for GoodQ WSL2 audio_service.py |
| `/scripts/wsl/install_vllm_service.sh` | Script / CLI | Install/enable the vLLM Llama-1B systemd service inside WSL. |
| `/scripts/wsl/monitor.sh` | Script / CLI | ============================================================================ |
| `/scripts/wsl/qdrant_network_validator.sh` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/scripts/wsl/smoke_wsl_memory.sh` | Script / CLI | One-stop smoke test + light self-heal for GoodQ memory stack on WSL. |
| `/scripts/wsl/update_vllm_service_port.sh` | Script / CLI | Helper to retarget the vllm-llama1b systemd unit to the normalized port (38005). |
| `/scripts/wsl2_audio_bridge.py` | Script / CLI | GoodQ4All WSL2 Audio Bridge |
| `/scripts/wsl2_process_audio.py` | Script / CLI | GoodQ4All WSL2 Audio Processor |
| `/scripts/wsl2_quick_install.sh` | Script / CLI | GoodQ4All - WSL2 Audio Quick Install |
| `/scripts/wsl_audio_preflight.py` | Script / CLI | Developer utility, diagnostic, or environment setup script. |
| `/setup.py` | Generic | No description provided. |
| `/steps/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/audio_wsl2_bridge.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/orchestrator.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase0_normalization.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase1_vad_segmentation.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase2_pyannote.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase3_chunk_builder.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase4_audio_processor.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase5_video_scene_integration.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio/segmentation/phase6_integration.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_diarize/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_diarize/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_diarize/step_wsl2.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_diarize/vad_preprocessor.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_embed_clap/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_emotion/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_ingest_unified/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_ingest_unified/step_wsl2.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_metadata/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_music_events/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_speaker_merge/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_time_hints/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_transcribe/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_transcribe/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/audio_transcribe/step_wsl2.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/atomic_io.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/audio_gpu_optimizer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/canonical_sensitive_events.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/conda_runner.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/config_loader.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/config_redaction.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/context_analyzer_llm.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/epistemic_diff.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/epistemic_formatter.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/faiss_utils.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/gpu_config.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/gpu_guard.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/lexicon.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/llm_model_factory.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_commit_events.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_context_writer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_manager.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_provenance.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_router.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_store.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_stores.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/memory_writer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/non_action_contract.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/profile_config.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/progress_tracker.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/qdrant_client.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/retrieval_events.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/retry.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/safe_access.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/scene_summarizer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/sensitive_staging.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/step_logger.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/tag_utils.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/tool_paths.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/common/vad_preprocessor.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/discover_sources/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/discover_sources/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/emotion_classify/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/emotion_classify/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/face_embed/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/face_embed/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/graph_builder/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/graph_builder/emotion_arc_analyzer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/graph_builder/graph_builder.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/graph_builder/llm_enrichment.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/health_auto_export/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/health_auto_export/adapter.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/health_auto_export/normalizer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/home_assistant_status/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/home_assistant_status/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_caption/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_caption/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_embed_clip/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_embed_dino/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_exif/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_ocr/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/image_ocr/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/llm_chat/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/llm_chat/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/object_detect/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/object_detect/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/object_track_yolo/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/overview/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/pdf_text/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/pdf_text/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/sentiment/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/sentiment/step_fixed.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/system_metrics/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/system_metrics/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/tagger/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/tagger/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/tagger/step_llm_enhanced.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/text_embed/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/text_embed/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/tts/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/tts/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/cross_modal_harmonizer.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/embedding_pooler.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/entity_extractor.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/scene_embedder.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/scene_frame_extractor.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video/scene_visual_embeddings.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video_ingest/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video_scene_detect/gpu_scene_detect.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video_scene_detect/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video_summarizer/__init__.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/steps/video_summarizer/step.py` | Pipeline Steps | Common step helper or configuration loader. |
| `/tests/README.md` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/__init__.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/check_syntax.bat` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/conftest.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/integration/__init__.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/integration/test_watchdog.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/LAUNCH_WEB_INTERFACE.bat.old` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/LAUNCH_WEB_INTERFACE_FIXED.bat.old` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/README.md` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/integration_harnesses/test_ingestion_verbose.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/integration_harnesses/test_scene_comprehensive.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/integration_harnesses/verify_clip.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/run_test_ingestion.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_analytics_query.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_analytics_sample.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_audio_diarize_optimized.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_audio_pipeline_comprehensive.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_config_nesting.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_consolidation.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_diarization_chunking.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_diarize_status.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_direct_run.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_entities.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_full_pipeline_llm.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_gpu_management.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_ingestion.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_ingestion_debug.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_ingestion_fix.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_ingestion_simple.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_kg_build.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_llm_client.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_llm_integration.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_module_import.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase2_verification.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase3_llm_integration.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase3_standalone.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase4_audio.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase6.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase6_harness.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase6_kg_integration.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_phase7_analytics.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_pipeline_gpu.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_python_paths.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_sample.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_scene_detection_config.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_scene_structure.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_scene_summarizer.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_segment_text.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_vad_diarization.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_validation.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/test_wsl_audio.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/root_harnesses/validate_analytics.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/test_db_creation.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/test_knowledge_graph.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/test_memory_context.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/__init__.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/quick_test_storage.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/test_clean_run.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/test_hf_auth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/test_mission_logger.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/validate_all_steps.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/validate_ingestion_output.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/legacy/utilities/validate_results.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_face_output.json` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_input.json` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_launcher.ps1` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_sample_ingest.bat` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_scene_input.json` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_scene_output.json` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/test_system.bat` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/__init__.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_api_main_legacy_prune_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_api_surface_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_atomic_json_write.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_diarize_cuda_path.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_duration_wave_fallback.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_segment_timeline_normalization.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_speaker_merge_step.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_transcribe_backend_unavailable.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_audio_transcribe_fw_contract.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_baseline_audio_profile_invariant.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_bootstrap_install_console.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_bootstrap_install_qdrant.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_bootstrap_install_wsl.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_bootstrap_models_resilience.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_bootstrap_verify_model_cache.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_cache_readiness_check.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_config_redaction.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_config_values.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_context_analyzer_llm.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_agent_disable_invariant.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_recurrence_api.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_recurrence_output_contract.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_recurrence_recommendations.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_recurrence_report.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_control_recurrence_trend.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_crash_family_env_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_dev_pytest_wrapper.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_entity_extractor_logging.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_entity_extractor_semantic_quality.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_episode_reference_eval.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_epistemic_diff_smoke.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_epistemic_formatter_smoke.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_face_embed_fallback.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_faiss_id_mapping.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_gpu_config_console.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_healer_retry_ceiling.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_health_intake_normalizer_smoke.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_hitl_stitching.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_identity_ledger.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_image_embed_dino_diagnostics.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_image_ocr_observability.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_ingest_request_ledger.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_ingest_status_route.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_ingest_submit_route.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_kg_realtime_relationship_enrichment.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_legacy_wsl_audio_bridge_compat.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_memory_embedding_keying.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_memory_ephemeral_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_multimodal_search_audio.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_multimodal_search_similar_scene.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_native_model_stability_smoke.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_non_action_contract_smoke.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_operator_console_static.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_optional_vision_observability.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_overview_semantic_quality.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_persistent_store_alignment.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_phase6_audio_artifact_path_unified.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_phase6_critical_integrity.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_phase6_exception_persists_false.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_phase6_rerun_safety.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_phase6_truth_invariant.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_print_config.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_profile_override_metadata.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_artifact_persisted_on_failure_exit.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_index.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_audio_backend_reducer.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_audio_entity_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_content_state.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_modality_status.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_progress_tracking.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_step_json_errors.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_ingestion_step_observer_metadata.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_run_summary.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_runtime_run_preview.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_runtime_status.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_scene_bundle_transaction_atomicity.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_scene_embedder_clip_fallback.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_scene_embedder_device_fallback.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_scene_frame_extractor_zero_duration.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_scene_summarizer_semantic_quality.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_search_route_audio.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_search_route_enrichment.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_search_route_sentiment.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_season3_feature_ladder.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_seg_p5_authoritative_compare.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_seg_p5_promotion_envelope.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_segmentation_shadow_campaign.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_segmentation_shadow_mode.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_self_healing_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_step_runner_openmp_guard.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_summary_console.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_system_engine_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_system_route_policy.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_tag_utils_taxonomy.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_tagger_llm_enhanced_semantic_quality.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_tagger_semantic_quality.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_temporal_projection_repair.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_text_embedding_identity.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_time_hint_truth.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_tool_paths_piper.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_ui_conduits_audio_doctrine.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_vector_parity_artifact_persistence.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_verify_entity_quality_metrics.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_video_ingest_semantic_summary.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_video_scene_detect_duration_fallback.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_video_scene_detect_entity_refine_retired.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_vision_gpu_import_contract.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_vision_step_diagnostics.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_watchdog_processed_prefix_idempotent.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_watchdog_registry_deadlock.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_wsl2_audio_bridge_preflight.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_wsl_audio_preflight.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_wsl_audio_unified_bridge.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_wsl_diarization_model_authority.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/tests/unit/test_wsl_process_audio_diarization.py` | Testing Suite | Unit or integration test for verified capability checkpoints. |
| `/ui/justification_v1/index.html` | Generic | No description provided. |
| `/ui/justification_v1/inspector/README.md` | Generic | No description provided. |
| `/ui/justification_v1/inspector/inspector.js` | Generic | No description provided. |
| `/ui/justification_v1/inspector/inspector_log.jsonl` | Generic | No description provided. |
| `/ui/justification_v1/static/css/app.css` | Generic | No description provided. |
| `/ui/justification_v1/static/js/app.js` | Generic | No description provided. |
| `/ui/justification_v1/static/js/integrity.js` | Generic | No description provided. |
| `/ui/justification_v1/static/js/test_render.js` | Generic | No description provided. |
| `/ui/justification_v1/static/js/types_epistemic.js` | Generic | No description provided. |
| `/ui/justification_v1/static/js/types_non_action.js` | Generic | No description provided. |
| `/ui/operator_console_v1/README.md` | Generic | No description provided. |
| `/ui/operator_console_v1/index.html` | Frontend UI | Guided and Operator modes cockpit layout for system diagnostics. |
| `/ui/operator_console_v1/static/css/app.css` | Frontend UI | Styling sheet for the Classic Operator Console. |
| `/ui/operator_console_v1/static/js/app.js` | Frontend UI | Dashboard rendering logic for Classic Operator Console. |
| `/ui/retro_console_v1/README.md` | Frontend UI | Design details for the Cyber-CRT Retro Memory Explorer UI. |
| `/ui/retro_console_v1/index.html` | Frontend UI | CRT-themed Retro Memory Explorer viewport container. |
| `/ui/retro_console_v1/static/css/retro.css` | Frontend UI | Vibrant phosphor-green and cyber-blue styling rules for the Retro UI. |
| `/ui/retro_console_v1/static/js/retro.js` | Frontend UI | Autopilot graph flight, 3D Spinning Globe, and timeline checklists logic. |
| `/ui/stitching_workbench/index.html` | Frontend UI | Interactive manual voice stitching workbench view. |
| `/ui/stitching_workbench/static/css/stitching.css` | Frontend UI | Styling rules for the stitching workbench UI. |
| `/ui/stitching_workbench/static/js/stitching.js` | Frontend UI | Renders unstitched voice patterns and confirms database-mutation stitch requests. |
| `/ui/summary_console/index.html` | Frontend UI | Unified memory summary browser cockpit. |
| `/ui/summary_console/static/css/summary.css` | Frontend UI | Styling sheet for the Summary Console layout. |
| `/ui/summary_console/static/js/summary.js` | Frontend UI | Exposes PEOPLE, PLACES, MOODS, and OCCASIONS tabs and collection exports. |
| `/vendor/_yaml/__init__.py` | Generic | No description provided. |
| `/vendor/bin/hf.exe` | Generic | No description provided. |
| `/vendor/bin/huggingface-cli.exe` | Generic | No description provided. |
| `/vendor/bin/normalizer.exe` | Generic | No description provided. |
| `/vendor/bin/tiny-agents.exe` | Generic | No description provided. |
| `/vendor/bin/tqdm.exe` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/certifi-2025.8.3.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/certifi/__init__.py` | Generic | No description provided. |
| `/vendor/certifi/__main__.py` | Generic | No description provided. |
| `/vendor/certifi/core.py` | Generic | No description provided. |
| `/vendor/certifi/py.typed` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/entry_points.txt` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/charset_normalizer-3.4.3.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/charset_normalizer/__init__.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/__main__.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/api.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/cd.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/cli/__init__.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/cli/__main__.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/constant.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/legacy.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/md.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/models.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/py.typed` | Generic | No description provided. |
| `/vendor/charset_normalizer/utils.py` | Generic | No description provided. |
| `/vendor/charset_normalizer/version.py` | Generic | No description provided. |
| `/vendor/colorama-0.4.6.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/colorama-0.4.6.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/colorama-0.4.6.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/colorama-0.4.6.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/colorama-0.4.6.dist-info/licenses/LICENSE.txt` | Generic | No description provided. |
| `/vendor/colorama/__init__.py` | Generic | No description provided. |
| `/vendor/colorama/ansi.py` | Generic | No description provided. |
| `/vendor/colorama/ansitowin32.py` | Generic | No description provided. |
| `/vendor/colorama/initialise.py` | Generic | No description provided. |
| `/vendor/colorama/tests/__init__.py` | Generic | No description provided. |
| `/vendor/colorama/tests/ansi_test.py` | Generic | No description provided. |
| `/vendor/colorama/tests/ansitowin32_test.py` | Generic | No description provided. |
| `/vendor/colorama/tests/initialise_test.py` | Generic | No description provided. |
| `/vendor/colorama/tests/isatty_test.py` | Generic | No description provided. |
| `/vendor/colorama/tests/utils.py` | Generic | No description provided. |
| `/vendor/colorama/tests/winterm_test.py` | Generic | No description provided. |
| `/vendor/colorama/win32.py` | Generic | No description provided. |
| `/vendor/colorama/winterm.py` | Generic | No description provided. |
| `/vendor/filelock-3.19.1.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/filelock-3.19.1.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/filelock-3.19.1.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/filelock-3.19.1.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/filelock-3.19.1.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/filelock/__init__.py` | Generic | No description provided. |
| `/vendor/filelock/_api.py` | Generic | No description provided. |
| `/vendor/filelock/_error.py` | Generic | No description provided. |
| `/vendor/filelock/_soft.py` | Generic | No description provided. |
| `/vendor/filelock/_unix.py` | Generic | No description provided. |
| `/vendor/filelock/_util.py` | Generic | No description provided. |
| `/vendor/filelock/_windows.py` | Generic | No description provided. |
| `/vendor/filelock/asyncio.py` | Generic | No description provided. |
| `/vendor/filelock/py.typed` | Generic | No description provided. |
| `/vendor/filelock/version.py` | Generic | No description provided. |
| `/vendor/fsspec-2025.9.0.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/fsspec-2025.9.0.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/fsspec-2025.9.0.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/fsspec-2025.9.0.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/fsspec-2025.9.0.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/fsspec/__init__.py` | Generic | No description provided. |
| `/vendor/fsspec/_version.py` | Generic | No description provided. |
| `/vendor/fsspec/archive.py` | Generic | No description provided. |
| `/vendor/fsspec/asyn.py` | Generic | No description provided. |
| `/vendor/fsspec/caching.py` | Generic | No description provided. |
| `/vendor/fsspec/callbacks.py` | Generic | No description provided. |
| `/vendor/fsspec/compression.py` | Generic | No description provided. |
| `/vendor/fsspec/config.py` | Generic | No description provided. |
| `/vendor/fsspec/conftest.py` | Generic | No description provided. |
| `/vendor/fsspec/core.py` | Generic | No description provided. |
| `/vendor/fsspec/dircache.py` | Generic | No description provided. |
| `/vendor/fsspec/exceptions.py` | Generic | No description provided. |
| `/vendor/fsspec/fuse.py` | Generic | No description provided. |
| `/vendor/fsspec/generic.py` | Generic | No description provided. |
| `/vendor/fsspec/gui.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/__init__.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/arrow.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/asyn_wrapper.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/cache_mapper.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/cache_metadata.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/cached.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/dask.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/data.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/dbfs.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/dirfs.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/ftp.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/gist.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/git.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/github.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/http.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/http_sync.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/jupyter.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/libarchive.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/local.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/memory.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/reference.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/sftp.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/smb.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/tar.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/webhdfs.py` | Generic | No description provided. |
| `/vendor/fsspec/implementations/zip.py` | Generic | No description provided. |
| `/vendor/fsspec/json.py` | Generic | No description provided. |
| `/vendor/fsspec/mapping.py` | Generic | No description provided. |
| `/vendor/fsspec/parquet.py` | Generic | No description provided. |
| `/vendor/fsspec/registry.py` | Generic | No description provided. |
| `/vendor/fsspec/spec.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/__init__.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/common.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/copy.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/get.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/mv.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/open.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/pipe.py` | Generic | No description provided. |
| `/vendor/fsspec/tests/abstract/put.py` | Generic | No description provided. |
| `/vendor/fsspec/transaction.py` | Generic | No description provided. |
| `/vendor/fsspec/utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/LICENSE` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/REQUESTED` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/entry_points.txt` | Generic | No description provided. |
| `/vendor/huggingface_hub-0.35.3.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/huggingface_hub/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_commit_api.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_commit_scheduler.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_inference_endpoints.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_jobs_api.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_local_folder.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_login.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_oauth.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_snapshot_download.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_space_api.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_tensorboard_logger.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_upload_large_folder.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_webhooks_payload.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/_webhooks_server.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/_cli_utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/auth.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/cache.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/download.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/hf.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/jobs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/lfs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/repo.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/repo_files.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/system.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/upload.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/cli/upload_large_folder.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/_cli_utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/delete_cache.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/download.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/env.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/huggingface_cli.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/lfs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/repo.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/repo_files.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/scan_cache.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/tag.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/upload.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/upload_large_folder.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/user.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/commands/version.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/community.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/constants.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/dataclasses.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/errors.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/fastai_utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/file_download.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/hf_api.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/hf_file_system.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/hub_mixin.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_client.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_common.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/_async_client.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/audio_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/audio_to_audio.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/automatic_speech_recognition.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/base.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/chat_completion.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/depth_estimation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/document_question_answering.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/feature_extraction.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/fill_mask.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/image_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/image_segmentation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/image_to_image.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/image_to_text.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/image_to_video.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/object_detection.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/question_answering.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/sentence_similarity.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/summarization.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/table_question_answering.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text2text_generation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_generation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_to_audio.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_to_image.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_to_speech.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/text_to_video.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/translation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/video_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/visual_question_answering.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/zero_shot_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/zero_shot_image_classification.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_generated/types/zero_shot_object_detection.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/_cli_hacks.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/agent.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/cli.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/constants.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/mcp_client.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/types.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_mcp/utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/_common.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/black_forest_labs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/cerebras.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/cohere.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/fal_ai.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/featherless_ai.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/fireworks_ai.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/groq.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/hf_inference.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/hyperbolic.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/nebius.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/novita.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/nscale.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/openai.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/publicai.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/replicate.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/sambanova.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/scaleway.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/together.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference/_providers/zai_org.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/inference_api.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/keras_mixin.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/lfs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/py.typed` | Generic | No description provided. |
| `/vendor/huggingface_hub/repocard.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/repocard_data.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/repository.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/serialization/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/serialization/_base.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/serialization/_dduf.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/serialization/_tensorflow.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/serialization/_torch.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/templates/datasetcard_template.md` | Generic | No description provided. |
| `/vendor/huggingface_hub/templates/modelcard_template.md` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/__init__.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_auth.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_cache_assets.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_cache_manager.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_chunk_utils.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_datetime.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_deprecation.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_dotenv.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_experimental.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_fixes.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_git_credential.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_headers.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_hf_folder.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_http.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_lfs.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_pagination.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_paths.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_runtime.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_safetensors.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_subprocess.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_telemetry.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_typing.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_validators.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_xet.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/_xet_progress_reporting.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/endpoint_helpers.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/insecure_hashlib.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/logging.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/sha.py` | Generic | No description provided. |
| `/vendor/huggingface_hub/utils/tqdm.py` | Generic | No description provided. |
| `/vendor/idna-3.10.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/idna-3.10.dist-info/LICENSE.md` | Generic | No description provided. |
| `/vendor/idna-3.10.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/idna-3.10.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/idna-3.10.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/idna/__init__.py` | Generic | No description provided. |
| `/vendor/idna/codec.py` | Generic | No description provided. |
| `/vendor/idna/compat.py` | Generic | No description provided. |
| `/vendor/idna/core.py` | Generic | No description provided. |
| `/vendor/idna/idnadata.py` | Generic | No description provided. |
| `/vendor/idna/intranges.py` | Generic | No description provided. |
| `/vendor/idna/package_data.py` | Generic | No description provided. |
| `/vendor/idna/py.typed` | Generic | No description provided. |
| `/vendor/idna/uts46data.py` | Generic | No description provided. |
| `/vendor/nssm.exe` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/licenses/LICENSE.APACHE` | Generic | No description provided. |
| `/vendor/packaging-25.0.dist-info/licenses/LICENSE.BSD` | Generic | No description provided. |
| `/vendor/packaging/__init__.py` | Generic | No description provided. |
| `/vendor/packaging/_elffile.py` | Generic | No description provided. |
| `/vendor/packaging/_manylinux.py` | Generic | No description provided. |
| `/vendor/packaging/_musllinux.py` | Generic | No description provided. |
| `/vendor/packaging/_parser.py` | Generic | No description provided. |
| `/vendor/packaging/_structures.py` | Generic | No description provided. |
| `/vendor/packaging/licenses/__init__.py` | Generic | No description provided. |
| `/vendor/packaging/licenses/_spdx.py` | Generic | No description provided. |
| `/vendor/packaging/markers.py` | Generic | No description provided. |
| `/vendor/packaging/metadata.py` | Generic | No description provided. |
| `/vendor/packaging/py.typed` | Generic | No description provided. |
| `/vendor/packaging/requirements.py` | Generic | No description provided. |
| `/vendor/packaging/specifiers.py` | Generic | No description provided. |
| `/vendor/packaging/tags.py` | Generic | No description provided. |
| `/vendor/packaging/utils.py` | Generic | No description provided. |
| `/vendor/packaging/version.py` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/pyyaml-6.0.3.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/qdrant/.qdrant-initialized` | Generic | No description provided. |
| `/vendor/qdrant/LICENSE` | Generic | No description provided. |
| `/vendor/qdrant/config.yaml` | Generic | No description provided. |
| `/vendor/qdrant/qdrant.exe` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/requests-2.32.5.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/requests/__init__.py` | Generic | No description provided. |
| `/vendor/requests/__version__.py` | Generic | No description provided. |
| `/vendor/requests/_internal_utils.py` | Generic | No description provided. |
| `/vendor/requests/adapters.py` | Generic | No description provided. |
| `/vendor/requests/api.py` | Generic | No description provided. |
| `/vendor/requests/auth.py` | Generic | No description provided. |
| `/vendor/requests/certs.py` | Generic | No description provided. |
| `/vendor/requests/compat.py` | Generic | No description provided. |
| `/vendor/requests/cookies.py` | Generic | No description provided. |
| `/vendor/requests/exceptions.py` | Generic | No description provided. |
| `/vendor/requests/help.py` | Generic | No description provided. |
| `/vendor/requests/hooks.py` | Generic | No description provided. |
| `/vendor/requests/models.py` | Generic | No description provided. |
| `/vendor/requests/packages.py` | Generic | No description provided. |
| `/vendor/requests/sessions.py` | Generic | No description provided. |
| `/vendor/requests/status_codes.py` | Generic | No description provided. |
| `/vendor/requests/structures.py` | Generic | No description provided. |
| `/vendor/requests/utils.py` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/LICENCE` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/entry_points.txt` | Generic | No description provided. |
| `/vendor/tqdm-4.67.1.dist-info/top_level.txt` | Generic | No description provided. |
| `/vendor/tqdm/__init__.py` | Generic | No description provided. |
| `/vendor/tqdm/__main__.py` | Generic | No description provided. |
| `/vendor/tqdm/_dist_ver.py` | Generic | No description provided. |
| `/vendor/tqdm/_main.py` | Generic | No description provided. |
| `/vendor/tqdm/_monitor.py` | Generic | No description provided. |
| `/vendor/tqdm/_tqdm.py` | Generic | No description provided. |
| `/vendor/tqdm/_tqdm_gui.py` | Generic | No description provided. |
| `/vendor/tqdm/_tqdm_notebook.py` | Generic | No description provided. |
| `/vendor/tqdm/_tqdm_pandas.py` | Generic | No description provided. |
| `/vendor/tqdm/_utils.py` | Generic | No description provided. |
| `/vendor/tqdm/asyncio.py` | Generic | No description provided. |
| `/vendor/tqdm/auto.py` | Generic | No description provided. |
| `/vendor/tqdm/autonotebook.py` | Generic | No description provided. |
| `/vendor/tqdm/cli.py` | Generic | No description provided. |
| `/vendor/tqdm/completion.sh` | Generic | No description provided. |
| `/vendor/tqdm/contrib/__init__.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/bells.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/concurrent.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/discord.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/itertools.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/logging.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/slack.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/telegram.py` | Generic | No description provided. |
| `/vendor/tqdm/contrib/utils_worker.py` | Generic | No description provided. |
| `/vendor/tqdm/dask.py` | Generic | No description provided. |
| `/vendor/tqdm/gui.py` | Generic | No description provided. |
| `/vendor/tqdm/keras.py` | Generic | No description provided. |
| `/vendor/tqdm/notebook.py` | Generic | No description provided. |
| `/vendor/tqdm/rich.py` | Generic | No description provided. |
| `/vendor/tqdm/std.py` | Generic | No description provided. |
| `/vendor/tqdm/tk.py` | Generic | No description provided. |
| `/vendor/tqdm/tqdm.1` | Generic | No description provided. |
| `/vendor/tqdm/utils.py` | Generic | No description provided. |
| `/vendor/tqdm/version.py` | Generic | No description provided. |
| `/vendor/typing_extensions-4.15.0.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/typing_extensions-4.15.0.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/typing_extensions-4.15.0.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/typing_extensions-4.15.0.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/typing_extensions-4.15.0.dist-info/licenses/LICENSE` | Generic | No description provided. |
| `/vendor/typing_extensions.py` | Generic | No description provided. |
| `/vendor/urllib3-2.5.0.dist-info/INSTALLER` | Generic | No description provided. |
| `/vendor/urllib3-2.5.0.dist-info/METADATA` | Generic | No description provided. |
| `/vendor/urllib3-2.5.0.dist-info/RECORD` | Generic | No description provided. |
| `/vendor/urllib3-2.5.0.dist-info/WHEEL` | Generic | No description provided. |
| `/vendor/urllib3-2.5.0.dist-info/licenses/LICENSE.txt` | Generic | No description provided. |
| `/vendor/urllib3/__init__.py` | Generic | No description provided. |
| `/vendor/urllib3/_base_connection.py` | Generic | No description provided. |
| `/vendor/urllib3/_collections.py` | Generic | No description provided. |
| `/vendor/urllib3/_request_methods.py` | Generic | No description provided. |
| `/vendor/urllib3/_version.py` | Generic | No description provided. |
| `/vendor/urllib3/connection.py` | Generic | No description provided. |
| `/vendor/urllib3/connectionpool.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/__init__.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/__init__.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/connection.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/emscripten_fetch_worker.js` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/fetch.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/request.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/emscripten/response.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/pyopenssl.py` | Generic | No description provided. |
| `/vendor/urllib3/contrib/socks.py` | Generic | No description provided. |
| `/vendor/urllib3/exceptions.py` | Generic | No description provided. |
| `/vendor/urllib3/fields.py` | Generic | No description provided. |
| `/vendor/urllib3/filepost.py` | Generic | No description provided. |
| `/vendor/urllib3/http2/__init__.py` | Generic | No description provided. |
| `/vendor/urllib3/http2/connection.py` | Generic | No description provided. |
| `/vendor/urllib3/http2/probe.py` | Generic | No description provided. |
| `/vendor/urllib3/poolmanager.py` | Generic | No description provided. |
| `/vendor/urllib3/py.typed` | Generic | No description provided. |
| `/vendor/urllib3/response.py` | Generic | No description provided. |
| `/vendor/urllib3/util/__init__.py` | Generic | No description provided. |
| `/vendor/urllib3/util/connection.py` | Generic | No description provided. |
| `/vendor/urllib3/util/proxy.py` | Generic | No description provided. |
| `/vendor/urllib3/util/request.py` | Generic | No description provided. |
| `/vendor/urllib3/util/response.py` | Generic | No description provided. |
| `/vendor/urllib3/util/retry.py` | Generic | No description provided. |
| `/vendor/urllib3/util/ssl_.py` | Generic | No description provided. |
| `/vendor/urllib3/util/ssl_match_hostname.py` | Generic | No description provided. |
| `/vendor/urllib3/util/ssltransport.py` | Generic | No description provided. |
| `/vendor/urllib3/util/timeout.py` | Generic | No description provided. |
| `/vendor/urllib3/util/url.py` | Generic | No description provided. |
| `/vendor/urllib3/util/util.py` | Generic | No description provided. |
| `/vendor/urllib3/util/wait.py` | Generic | No description provided. |
| `/vendor/yaml/__init__.py` | Generic | No description provided. |
| `/vendor/yaml/composer.py` | Generic | No description provided. |
| `/vendor/yaml/constructor.py` | Generic | No description provided. |
| `/vendor/yaml/cyaml.py` | Generic | No description provided. |
| `/vendor/yaml/dumper.py` | Generic | No description provided. |
| `/vendor/yaml/emitter.py` | Generic | No description provided. |
| `/vendor/yaml/error.py` | Generic | No description provided. |
| `/vendor/yaml/events.py` | Generic | No description provided. |
| `/vendor/yaml/loader.py` | Generic | No description provided. |
| `/vendor/yaml/nodes.py` | Generic | No description provided. |
| `/vendor/yaml/parser.py` | Generic | No description provided. |
| `/vendor/yaml/reader.py` | Generic | No description provided. |
| `/vendor/yaml/representer.py` | Generic | No description provided. |
| `/vendor/yaml/resolver.py` | Generic | No description provided. |
| `/vendor/yaml/scanner.py` | Generic | No description provided. |
| `/vendor/yaml/serializer.py` | Generic | No description provided. |
| `/vllm_wsl/INSTALLATION_REPORT.md` | Generic | No description provided. |
| `/vllm_wsl/LLAMA_TEST_RESULTS.md` | Generic | No description provided. |
| `/vllm_wsl/MODEL_DOWNLOAD_REPORT.md` | Generic | No description provided. |
| `/vllm_wsl/MODEL_SCAN_REPORT.md` | Generic | No description provided. |
| `/vllm_wsl/MODEL_SCAN_UPDATED.md` | Generic | No description provided. |
| `/vllm_wsl/OLLAMA_INTEGRATION.md` | Generic | No description provided. |
| `/vllm_wsl/README.md` | Generic | No description provided. |
| `/vllm_wsl/activate.sh` | Generic | No description provided. |
| `/vllm_wsl/configs/default.yaml` | Generic | No description provided. |
| `/vllm_wsl/configs/models.yaml` | Generic | No description provided. |
| `/wsl2_audio/CUDA_SETUP.md` | Generic | No description provided. |
| `/wsl2_audio/HF_CLI_LOGIN_GUIDE.md` | Generic | No description provided. |
| `/wsl2_audio/HF_QUICK_REF.txt` | Generic | No description provided. |
| `/wsl2_audio/INSTALL_STATUS.txt` | Generic | No description provided. |
| `/wsl2_audio/OOM_FIX.md` | Generic | No description provided. |
| `/wsl2_audio/PIPELINE_UPGRADE.md` | Generic | No description provided. |
| `/wsl2_audio/QUICKSTART.md` | Generic | No description provided. |
| `/wsl2_audio/QUICK_REFERENCE.md` | Generic | No description provided. |
| `/wsl2_audio/QUICK_START.md` | Generic | No description provided. |
| `/wsl2_audio/README.md` | Generic | No description provided. |
| `/wsl2_audio/TEST_RESULTS.md` | Generic | No description provided. |
| `/wsl2_audio/WSL2_AUDIO_FIX_COMPLETE.md` | Generic | No description provided. |
| `/wsl2_audio/audio_bridge.py` | WSL2 Audio | Bridge interface communicating between Windows host and WSL audio service. |
| `/wsl2_audio/audio_service.py` | WSL2 Audio | WSL system daemon handling faster-whisper, PyAnnote, and wav2vec. |
| `/wsl2_audio/bridge_config.json` | Generic | No description provided. |
| `/wsl2_audio/check_cuda.py` | WSL2 Audio | Verifies CUDA access and PyTorch compatibility inside the WSL shell. |
| `/wsl2_audio/config.json` | Generic | No description provided. |
| `/wsl2_audio/config_wsl2_audio.json` | Generic | No description provided. |
| `/wsl2_audio/fw_transcribe.py` | Generic | No description provided. |
| `/wsl2_audio/process.sh` | Script / CLI | Check if arguments are provided |
| `/wsl2_audio/process_audio.py` | WSL2 Audio | WSL processing entry point for transcribing and diarizing raw audio WAVs. |
| `/wsl2_audio/process_minimal.sh` | Script / CLI | Minimal GoodQ Audio Processing - Transcription Only |
| `/wsl2_audio/requirements-bootstrap-constraints.txt` | Generic | No description provided. |
| `/wsl2_audio/requirements-locked.txt` | Generic | No description provided. |
| `/wsl2_audio/setup_cuda_env.sh` | WSL2 Audio | Sets up CUDA and cache directories for HuggingFace/PyAnnote in WSL. |
| `/wsl2_audio/setup_windows.ps1` | WSL2 Audio | Configures Windows-side WSL distro network port forward mappings. |
| `/wsl2_audio/setup_wsl2_audio.sh` | WSL2 Audio | Bootstrap script to provision the WSL core packages and virtual environment. |
| `/wsl2_audio/start_wsl2_service.bat` | Script / CLI | ============================================================================ |
| `/wsl2_audio/test_bridge.py` | Script / CLI | Test script for WSL2 audio bridge |
| `/wsl2_audio/test_pipeline.py` | Script / CLI | Comprehensive Audio Processing Pipeline Test |
| `/wsl2_audio/test_simple.sh` | Script / CLI | Validation/test utility for test simple. |