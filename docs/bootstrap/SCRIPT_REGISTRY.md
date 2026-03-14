# SCRIPT_REGISTRY

_Generated: 2026-02-15_

## Scope

- Included: `scripts/**`, `cli/**`, `agents/**`, `wsl2_audio/**`, root launchers (`LAUNCH_GOODQ.bat`, `LAUNCH_GOODQ.ps1`).
- Excluded from main table: `scripts/archive/**` (listed separately under Archived/Migrations).
- Classification is heuristic (references + naming + inline comments/docstrings + capability scan).

## Category Summary

- Bootstrap-Critical: **30**
- Runtime Utility: **97**
- Dev Utility: **36**
- One-Time Migration: **0**
- Unclear/Obsolete: **122**
- Archived/Migrations (`scripts/archive/**`): **3**

## Danger Capability Flags (Human Review)

- `destructive actions`: SQL deletion/drop, recursive delete, force-delete commands.
- `environment mutation`: `setx`, `set`, `export`, `$env:` writes.
- `absolute path operations`: hardcoded drive/mount paths used with file operations.
- `binary/network download`: script downloads binaries/content from network.

## Main Script Registry

| Script Path | Category | Purpose Summary | Safe to Run on Clean Install? | Risk Notes |
|---|---|---|---|---|
| `LAUNCH_GOODQ.bat` | Bootstrap-Critical | GoodQ4All Master Launcher (Batch Wrapper) | Yes | None detected |
| `LAUNCH_GOODQ.ps1` | Bootstrap-Critical | GoodQ4All Master Launcher | Manual Review | environment mutation |
| `agents/__init__.py` | Runtime Utility | GoodQ Agent System | Yes | None detected |
| `agents/analysis/__init__.py` | Runtime Utility | GoodQ Agent System | Yes | None detected |
| `agents/base_agent.py` | Runtime Utility | Base agent class for GoodQ agents. | Yes | None detected |
| `agents/config_healer.py` | Runtime Utility | GoodQ4All Config Auto-Healer - Phase 2: Autonomous Recovery | Yes | None detected |
| `agents/control_agent.py` | Runtime Utility | GoodQ4All Pipeline Control Agent - Phase 2: Observer, Advisor & Healer | Manual Review | absolute path operations |
| `agents/ingestion/__init__.py` | Runtime Utility | GoodQ Agent System | Yes | None detected |
| `agents/ingestion/scene_detector.py` | Runtime Utility | Scene Detector Agent - Detects scene boundaries in videos. | Manual Review | absolute path operations |
| `agents/knowledge/__init__.py` | Runtime Utility | GoodQ Agent System | Yes | None detected |
| `agents/llm_agent.py` | Runtime Utility | LLM Agent - Provides LLM capabilities for analysis, summarization, and self-healing | Manual Review | absolute path operations |
| `agents/orchestrator.py` | Unclear/Obsolete | GoodQ Agent Orchestrator (retired) | No | absolute path operations |
| `agents/pipeline_integration.py` | Unclear/Obsolete | Pipeline Agent Integration (retired) | No | absolute path operations |
| `agents/recovery_db.py` | Runtime Utility | GoodQ4All Recovery Database - Phase 2 | Yes | None detected |
| `agents/recovery_strategies.py` | Runtime Utility | Recovery Strategies Database for Control Agent Self-Healing | Manual Review | absolute path operations |
| `agents/self_healing_monitor.py` | Runtime Utility | Self-Healing Monitor | Manual Review | absolute path operations |
| `agents/watchdog_agent_integration.py` | Unclear/Obsolete | Watchdog Integration with Agent Orchestrator (retired) | No | absolute path operations |
| `cli/__init__.py` | Runtime Utility | CLI commands | Yes | None detected |
| `cli/chroma_store.py` | Runtime Utility | OCR + caption | Yes | None detected |
| `cli/conduits_build.py` | Runtime Utility | Conduit Pack v1 builder (offline/on-demand). | Yes | None detected |
| `cli/conduits_kg.py` | Runtime Utility | Conduit Pack v1: UI-safe conduits for knowledge_graph.db (derived tables only). | Yes | None detected |
| `cli/conduits_memory.py` | Runtime Utility | Conduit Pack v1: UI-safe conduits for memory.db (derived tables only). | Yes | None detected |
| `cli/conduits_processing.py` | Runtime Utility | Conduit Pack v1: UI-safe conduits for processing artifacts (derived tables only). | No | destructive actions |
| `cli/conduits_sensitive_sources.py` | Runtime Utility | Sensitive Source Wiring Pack v1: UI-safe conduit stubs (derived-only; empty by default). | Yes | None detected |
| `cli/conduits_store_stats.py` | Runtime Utility | Conduit Pack v1: UI-safe store stats conduits (counts/dims only). | Yes | None detected |
| `cli/goodq_doctor.py` | Runtime Utility | GoodQ Doctor - Read-only ingestion preflight validator. | Manual Review | absolute path operations |
| `cli/graph_query.py` | Runtime Utility | Knowledge Graph Query CLI | Manual Review | absolute path operations |
| `cli/links.py` | Runtime Utility | Utility script for links. | Yes | None detected |
| `cli/list_inbox.py` | Runtime Utility | Utility script for list inbox. | Yes | None detected |
| `cli/list_runs.py` | Runtime Utility | Utility script for list runs. | Yes | None detected |
| `cli/media_refs.py` | Runtime Utility | GoodQ UI-safe media reference tokens (local-only). | Yes | None detected |
| `cli/memory.py` | Runtime Utility | exit non-zero if error or warning | No | destructive actions |
| `cli/monitor_ingestion.py` | Runtime Utility | GoodQ4All - Live Ingestion Monitor | Manual Review | absolute path operations |
| `cli/monitor_live.bat` | Runtime Utility | Live Ingestion Monitor - Shows real-time progress | Yes | None detected |
| `cli/nl_query.py` | Runtime Utility | Natural Language Query Interface for Knowledge Graph | Manual Review | absolute path operations |
| `cli/observability_health.py` | Runtime Utility | GoodQ Observability Health Report (read-only). | Yes | None detected |
| `cli/observability_rollup.py` | Runtime Utility | GoodQ Observability Rollups (offline/on-demand). | Yes | None detected |
| `cli/print_config.py` | Runtime Utility | Utility script for print config. | Yes | None detected |
| `cli/retrieve.py` | Runtime Utility | Utility script for retrieve. | Yes | None detected |
| `cli/run_ingestion.py` | Runtime Utility | Setup logger | Manual Review | absolute path operations |
| `cli/run_narrative.py` | Runtime Utility | Utility script for run narrative. | Yes | None detected |
| `cli/run_summary.py` | Runtime Utility | Utility script for run summary. | Yes | None detected |
| `cli/step_runner.py` | Runtime Utility | Add repo root to Python path so "steps.*" modules can be imported | Manual Review | absolute path operations |
| `cli/system_status.py` | Runtime Utility | GoodQ4All System Status Dashboard | Manual Review | absolute path operations |
| `cli/test_ingestion.py` | Runtime Utility | GoodQ4All End-to-End Ingestion Test Suite | Yes | None detected |
| `cli/ui_conduits_rollup.py` | Runtime Utility | GoodQ UI-Safe Conduits v1 (offline/on-demand). | Yes | None detected |
| `cli/watchdog.py` | Runtime Utility | GoodQ Watchdog - Automatic File Ingestion Monitor | Manual Review | absolute path operations |
| `scripts/INSTALL_AUDIO_DIARIZE_ENV.bat` | Unclear/Obsolete | ================================================================================ | No | None detected |
| `scripts/INSTALL_WSL2_AUDIO.bat` | Bootstrap-Critical | GoodQ4All - WSL2 Audio Setup Launcher | Yes | None detected |
| `scripts/PIN_MODEL_VERSIONS.bat` | Runtime Utility | Fetch and pin exact model versions (commit SHAs) from HuggingFace Hub | Yes | None detected |
| `scripts/RUN_GPU_OPTIMIZATION.bat` | Unclear/Obsolete | ============================================================================= | No | None detected |
| `scripts/SETUP_WEB_DEPENDENCIES.bat` | Unclear/Obsolete | GoodQ Environment Setup & Dependency Installer | No | None detected |
| `scripts/TEST_AUDIO_DIARIZE_BREAKDOWN.bat` | Unclear/Obsolete | Test Audio Diarization - Component Breakdown | No | None detected |
| `scripts/TEST_AUDIO_GPU.bat` | Unclear/Obsolete | ============================================================================= | No | None detected |
| `scripts/TEST_GPU_PIPELINE.bat` | Unclear/Obsolete | ================================================================================ | No | destructive actions; absolute path operations |
| `scripts/TEST_VISION_GPU.bat` | Unclear/Obsolete | Vision GPU Installation and Testing Script | No | None detected |
| `scripts/Test-AudioDiarization.ps1` | Dev Utility | > | Manual Review | None detected |
| `scripts/VERIFY_MODEL_LOCKDOWN.bat` | Dev Utility | Verify that all models are properly locked down with exact versions | Manual Review | None detected |
| `scripts/_lib/interpreter_bindings.bat` | Runtime Utility | Shared interpreter binding helpers for GoodQ4All batch scripts. | Yes | None detected |
| `scripts/_lib/interpreter_bindings.ps1` | Runtime Utility | Shared interpreter binding helpers for GoodQ4All scripts. | Manual Review | absolute path operations |
| `scripts/analytics_cli.py` | Runtime Utility | GoodQ Analytics CLI | Yes | None detected |
| `scripts/analytics_dashboard.py` | Runtime Utility | GoodQ Analytics Dashboard | Yes | None detected |
| `scripts/analytics_engine.py` | Runtime Utility | GoodQ Analytics Engine - Phase 7 | Manual Review | absolute path operations |
| `scripts/analytics_query.py` | Runtime Utility | Interactive Analytics Query Interface | Manual Review | absolute path operations |
| `scripts/analyze_database.py` | Runtime Utility | Get all tables | Yes | None detected |
| `scripts/analyze_kg_gaps.py` | Unclear/Obsolete | Analyze what data is available vs what's being extracted to knowledge graph | No | None detected |
| `scripts/analyze_sample_output.py` | Runtime Utility | Analyze sample.mp4 processing output from memory.db. | Yes | None detected |
| `scripts/analyze_unified_kg.py` | Unclear/Obsolete | Analyze Unified Knowledge Graph - Phase 8 | No | absolute path operations |
| `scripts/api_server.py (retired)` | Unclear/Obsolete | Legacy API monolith removed from tracked surface; restore from local quarantine only if needed | No | absolute path operations |
| `scripts/apply_performance_fixes.py` | Unclear/Obsolete | Apply performance optimizations to GoodQ configuration. | No | absolute path operations |
| `scripts/apply_scene_summaries.py` | Unclear/Obsolete | Apply Scene Summarization to All Existing Scenes | No | destructive actions |
| `scripts/audio_gpu_monitor.py` | Runtime Utility | Real-Time Audio GPU Monitor | Manual Review | absolute path operations |
| `scripts/audio_gpu_report.py` | Runtime Utility | Audio GPU Performance Report Generator | Manual Review | absolute path operations |
| `scripts/audit_all_exceptions.py` | Unclear/Obsolete | [SEARCH] Comprehensive Exception Handler Audit for GoodQ | No | absolute path operations |
| `scripts/audit_codebase.py` | Unclear/Obsolete | Comprehensive code audit to find silent failures and suspicious patterns | No | absolute path operations |
| `scripts/audit_vision_gpu.py` | Dev Utility | Comprehensive Vision Stack Audit | Manual Review | None detected |
| `scripts/audit_vision_pipeline.py` | Dev Utility | GoodQ4All - Vision Pipeline Functionality Audit | Manual Review | absolute path operations |
| `scripts/bootstrap_models.py` | Bootstrap-Critical | Ensure vendored dependencies (e.g., huggingface_hub) are importable | Manual Review | absolute path operations |
| `scripts/bootstrap_verify.py` | Bootstrap-Critical | Read-only bootstrap verification for clone readiness. | Yes | None detected |
| `scripts/build_kg_standalone.py` | Unclear/Obsolete | Build Knowledge Graph from Database - Standalone Version | No | absolute path operations |
| `scripts/build_knowledge_graph_from_db.py` | Runtime Utility | Build Knowledge Graph from Database | Manual Review | absolute path operations |
| `scripts/build_unified_kg.py` | Unclear/Obsolete | Build Unified Knowledge Graph - Phase 8 | No | absolute path operations |
| `scripts/cache_readiness_check.py` | Dev Utility | Cache readiness checker for goodq4all assets and models. | Manual Review | absolute path operations |
| `scripts/clean_old_processing.py` | Unclear/Obsolete | Clean Old Processing Files | No | destructive actions; absolute path operations |
| `scripts/command_center.ps1` | Runtime Utility | Utility script for command center. | No | destructive actions; absolute path operations |
| `scripts/comprehensive_clean_run.py` | Runtime Utility | Comprehensive Clean Run Test with Full Monitoring | No | destructive actions; absolute path operations |
| `scripts/comprehensive_gpu_setup.py` | Unclear/Obsolete | Comprehensive GPU Setup & Verification for GoodQ4All | No | absolute path operations |
| `scripts/config_schema.py` | Runtime Utility | GoodQ4All Canonical Configuration Schema | Manual Review | absolute path operations |
| `scripts/dataset_specs.py` | Unclear/Obsolete | Utility script for dataset specs. | No | absolute path operations |
| `scripts/debug_kg_input.py` | Unclear/Obsolete | Test with debug output to see what's being passed to KG functions | No | None detected |
| `scripts/debug_kg_structure.py` | Unclear/Obsolete | Debug why certain fields aren't being extracted | No | None detected |
| `scripts/deep_scene_analysis.py` | Runtime Utility | Get video hash | Yes | None detected |
| `scripts/diagnose_gpu_issue.py` | Unclear/Obsolete | Comprehensive GPU and processing diagnostics | No | absolute path operations |
| `scripts/diagnose_gpu_pipeline.py` | Unclear/Obsolete | Comprehensive GPU Pipeline Diagnostic Tool | No | None detected |
| `scripts/diagnose_transcription.py` | Unclear/Obsolete | Diagnostic script for audio transcription issues. | No | absolute path operations |
| `scripts/diagnostics/FULL_SYSTEM_AUDIT.py` | Unclear/Obsolete | COMPREHENSIVE SYSTEM AUDIT & CLEAN TEST | No | destructive actions; absolute path operations |
| `scripts/diagnostics/FULL_SYSTEM_TEST.bat` | Unclear/Obsolete | ================================================================================ | No | destructive actions; absolute path operations; binary/network download |
| `scripts/diagnostics/RUN_FULL_DIAGNOSTIC.ps1` | Unclear/Obsolete | ============================================================================ | No | environment mutation |
| `scripts/diagnostics/audit_gpu_steps.py` | Dev Utility | Scan all step directories | Manual Review | None detected |
| `scripts/diagnostics/check_db.py` | Unclear/Obsolete | Validation/test utility for check db. | No | None detected |
| `scripts/diagnostics/check_db_stats.py` | Unclear/Obsolete | Get all tables | No | None detected |
| `scripts/diagnostics/check_db_status.py` | Unclear/Obsolete | Check main database | No | None detected |
| `scripts/diagnostics/check_dbs.py` | Dev Utility | Validation/test utility for check dbs. | Manual Review | None detected |
| `scripts/diagnostics/check_latest_results.py` | Dev Utility | Check latest processing results | Manual Review | None detected |
| `scripts/diagnostics/check_processing_results.py` | Unclear/Obsolete | Check latest processing results | No | None detected |
| `scripts/diagnostics/check_schema.py` | Unclear/Obsolete | Validation/test utility for check schema. | No | None detected |
| `scripts/diagnostics/diagnose_system.py` | Dev Utility | GoodQ System Diagnostic Tool | Manual Review | absolute path operations |
| `scripts/diagnostics/monitor_progress.py` | Dev Utility | Real-time progress monitor for GoodQ pipeline | Manual Review | absolute path operations |
| `scripts/diagnostics/quick_laptop_test.ps1` | Unclear/Obsolete | Quick Laptop Installation Test Script | No | binary/network download |
| `scripts/diagnostics/verify_phase1.ps1` | Dev Utility | Phase 1 Audio Diarization Optimization - Verification | Manual Review | None detected |
| `scripts/docs/doc_drift_lint.py` | Bootstrap-Critical | Lint documentation drift against Bootstrap Contract semantics. | Manual Review | absolute path operations |
| `scripts/download_datasets.py` | Unclear/Obsolete | Load project .env so HF_TOKEN and related flags are picked up when invoked standalone | No | absolute path operations; environment mutation |
| `scripts/extract_test_frame.bat` | Unclear/Obsolete | Extract test frame for vision testing | No | None detected |
| `scripts/extract_test_frame.py` | Unclear/Obsolete | Quick script to extract a test frame from video for vision testing | No | absolute path operations |
| `scripts/final_validation_report.py` | Unclear/Obsolete | Final Validation Report - Scene Summarization Fix | No | None detected |
| `scripts/find_transcription_data.py` | Runtime Utility | Get video hash | Yes | None detected |
| `scripts/fix_imports.py` | Unclear/Obsolete | Pattern to replace | No | absolute path operations |
| `scripts/fix_pyannote_gpu.py` | Unclear/Obsolete | Fix PyAnnote GPU transfer API usage across the codebase | No | None detected |
| `scripts/fix_scene_detection_config.py` | Unclear/Obsolete | Fix scene detection configuration to use 5-minute minimum scenes | No | None detected |
| `scripts/full_diagnostic_check.py` | Unclear/Obsolete | Full Diagnostic Check - Analyze Complete Ingestion Results | No | absolute path operations |
| `scripts/generate_goodq4all_agent_status.py` | Runtime Utility | Monitoring/status utility for generate goodq4all agent status. | Yes | None detected |
| `scripts/generate_system_snapshot.py` | Runtime Utility | Utility script for generate system snapshot. | Yes | None detected |
| `scripts/get_processing_report.py` | Unclear/Obsolete | Generate real-time processing report for the UI | No | None detected |
| `scripts/gpu_config.py` | Runtime Utility | GoodQ4All GPU Configuration | Yes | None detected |
| `scripts/gpu_config_injector.py` | Runtime Utility | Inject GPU Configuration into Pipeline Steps | Yes | None detected |
| `scripts/gpu_config_tuner.py` | Unclear/Obsolete | GPU Configuration Tuner | No | None detected |
| `scripts/gpu_pipeline_optimizer.py` | Runtime Utility | GoodQ4All GPU Pipeline Optimizer | Yes | None detected |
| `scripts/gpu_setup_windows.py` | Bootstrap-Critical | GPU Setup for Windows - Install PyTorch with CUDA in all GPU-capable environments | Manual Review | absolute path operations |
| `scripts/health/pull_health_export.py` | Runtime Utility | Make repo-root imports work when invoked as `python scripts/health/pull_health_export.py`. | Manual Review | absolute path operations; environment mutation |
| `scripts/implement_comprehensive_vad.py` | Runtime Utility | Comprehensive VAD Implementation Across All Audio Steps | Yes | None detected |
| `scripts/init_qdrant_collections.py` | Unclear/Obsolete | Initialize Qdrant collections for GoodQ4All. | No | absolute path operations; binary/network download |
| `scripts/inspect_db.py` | Unclear/Obsolete | Quick database inspection script | No | None detected |
| `scripts/install_audio_deps_retry.bat` | Unclear/Obsolete | Setup/installation utility for install audio deps retry. | No | None detected |
| `scripts/install_gpu_support.ps1` | Bootstrap-Critical | GoodQ4All - Install GPU Support in All Environments | Yes | None detected |
| `scripts/install_pipeline_windows.ps1` | Unclear/Obsolete | GoodQ4All – 00Q Pipeline Installer (Windows) | No | None detected |
| `scripts/install_pipeline_wsl.py` | Bootstrap-Critical | WSL pipeline installer/repair script. | No | destructive actions; absolute path operations |
| `scripts/install_vad.bat` | Unclear/Obsolete | Setup/installation utility for install vad. | No | absolute path operations |
| `scripts/install_vision_gpu.bat` | Bootstrap-Critical | GoodQ4All - Vision GPU Setup Launcher | Manual Review | environment mutation |
| `scripts/install_vision_gpu.py` | Unclear/Obsolete | Comprehensive Vision GPU Setup Script | No | None detected |
| `scripts/mission_launch.ps1` | Bootstrap-Critical | Updated 2025-12-07: uses direct_ingestion instead of deprecated legacy orchestration pipelines. | No | destructive actions; absolute path operations; environment mutation |
| `scripts/monitor_gpu_pipeline.py` | Runtime Utility | Real-time GPU Pipeline Monitor | Yes | None detected |
| `scripts/monitor_ingestion.py` | Runtime Utility | Real-time Ingestion Monitor with Alerting | Manual Review | absolute path operations |
| `scripts/monitor_ingestion_progress.py` | Unclear/Obsolete | GoodQ Mission Progress Monitor | No | absolute path operations |
| `scripts/monitor_ingestion_realtime.py` | Unclear/Obsolete | Real-time Ingestion Monitor | No | absolute path operations |
| `scripts/monitor_processing.py` | Unclear/Obsolete | Real-time processing monitor for GoodQ ingestion | No | None detected |
| `scripts/monitor_scene_detection.py` | Unclear/Obsolete | Monitor GoodQ ingestion with scene detection verification | No | None detected |
| `scripts/monitoring/monitor_ingestion.bat` | Unclear/Obsolete | GoodQ4All - Live Ingestion Monitor (Non-Intrusive) | No | environment mutation |
| `scripts/monitoring/monitor_live.bat` | Unclear/Obsolete | Check running processes | No | None detected |
| `scripts/optimize_config.py` | Unclear/Obsolete | GoodQ Configuration Optimizer | No | absolute path operations |
| `scripts/optimize_vision_gpu.py` | Runtime Utility | GoodQ4All - Vision Stack GPU Optimization | Manual Review | absolute path operations |
| `scripts/organize_project.py` | Unclear/Obsolete | GoodQ4All Project Organizer | No | absolute path operations |
| `scripts/phase2_completion_report.py` | Runtime Utility | PHASE 2 COMPLETION REPORT | Manual Review | absolute path operations |
| `scripts/phase2_embedding_analysis.py` | Runtime Utility | Phase 2: Comprehensive Embedding and Knowledge Graph Analysis | Manual Review | absolute path operations |
| `scripts/phase2_fixes.py` | Runtime Utility | Phase 2 Comprehensive Fixes: Embedding & Knowledge Graph Integration | Manual Review | absolute path operations |
| `scripts/phase2_llm_integration.py` | Unclear/Obsolete | Phase 2: LLM-Enhanced Semantic Analysis Integration | No | absolute path operations; environment mutation; binary/network download |
| `scripts/phase2_progress_report.py` | Runtime Utility | Phase 2 Progress Report | Manual Review | absolute path operations |
| `scripts/phase2_verify.py` | Dev Utility | Phase 2 Verification Script | Manual Review | absolute path operations |
| `scripts/phase3_diagnostic.py` | Dev Utility | Phase 3 Diagnostic - Identify exact issues with scene processing | Manual Review | None detected |
| `scripts/phase5_full_validation.py` | Runtime Utility | Phase 5: Full System Validation | Manual Review | absolute path operations |
| `scripts/pin_model_versions.py` | Runtime Utility | Fetch and pin exact model versions (commit SHAs) for all HuggingFace models. | Manual Review | absolute path operations |
| `scripts/preflight_check.ps1` | Unclear/Obsolete | GoodQ Pre-Flight Check & Auto-Launcher | No | absolute path operations; binary/network download |
| `scripts/prepare_step_envs.ps1` | Runtime Utility | Ensure critical environment variables are set and persisted consistently | No | destructive actions; absolute path operations; environment mutation |
| `scripts/promote_wsl_audio.py` | Runtime Utility | WSL Audio Output Promotion Script | Manual Review | absolute path operations |
| `scripts/qdrant/CHECK_QDRANT.bat` | Unclear/Obsolete | GoodQ4All - Qdrant Health Check | No | binary/network download |
| `scripts/qdrant/INIT_QDRANT.bat` | Unclear/Obsolete | GoodQ4All - Initialize Qdrant Collections | No | None detected |
| `scripts/qdrant/INSTALL_QDRANT_SERVICE.bat` | Bootstrap-Critical | GoodQ4All - Install Qdrant as Windows Service | No | destructive actions; absolute path operations; binary/network download |
| `scripts/qdrant/START_QDRANT.bat` | Bootstrap-Critical | GoodQ4All - Start Qdrant Vector Database | Yes | None detected |
| `scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat` | Bootstrap-Critical | GoodQ4All - Uninstall Qdrant Windows Service | Manual Review | absolute path operations |
| `scripts/query_db_simple.py` | Unclear/Obsolete | Check tables | No | None detected |
| `scripts/quick_analysis.py` | Unclear/Obsolete | Get counts | No | None detected |
| `scripts/quick_gpu_setup.py` | Bootstrap-Critical | Quick GPU Setup - Install PyTorch with CUDA in all GPU-capable environments | Yes | None detected |
| `scripts/quick_gpu_test.py` | Unclear/Obsolete | Validation/test utility for quick gpu test. | No | None detected |
| `scripts/refresh_vllm_portproxy.bat` (retired) | Unclear/Obsolete | Legacy Windows->WSL portproxy helper removed from the tracked surface; retained only as historical context in archive/docs. | No | destructive actions; binary/network download |
| `scripts/rotate_logs.py` | Runtime Utility | Log Rotation Script | No | destructive actions; absolute path operations |
| `scripts/run_audio_diarize_test.bat` | Unclear/Obsolete | Direct environment test for audio diarization | No | environment mutation |
| `scripts/run_control_agent.py` | Bootstrap-Critical | Control Agent Runner - Convenience script | Yes | None detected |
| `scripts/run_gpu_optimization_tests.py` | Dev Utility | Full GPU Pipeline Optimization Test Suite | No | destructive actions; absolute path operations |
| `scripts/run_vision_audit.bat` | Unclear/Obsolete | GoodQ4All - Vision Pipeline Audit | No | None detected |
| `scripts/run_vision_optimization.bat` | Unclear/Obsolete | GoodQ4All - Vision Stack GPU Optimization Launcher | No | None detected |
| `scripts/setup/INSTALL_WEB_DEPS.ps1` | Unclear/Obsolete | GoodQ Quick Fix - Install Web Dependencies | No | None detected |
| `scripts/setup/VALIDATE_PYTHON_PATHS.bat` | Unclear/Obsolete | Use conda run to avoid shell-state activation requirements. | No | environment mutation |
| `scripts/setup/configure_envs_pythonpath.py` | Bootstrap-Critical | Configure all goodq conda environments to include the repo parent in PYTHONPATH. | Manual Review | absolute path operations |
| `scripts/setup/install_goodq.py` | Bootstrap-Critical | GoodQ4All Automated Installer | Manual Review | absolute path operations |
| `scripts/setup/install_package_all_envs.py` | Bootstrap-Critical | Install goodq4all package in editable mode across all conda environments. | Yes | None detected |
| `scripts/setup/setup_agents.ps1` | Unclear/Obsolete | GoodQ Multi-Agent System Setup | No | absolute path operations |
| `scripts/setup/start_agents.ps1` | Unclear/Obsolete | GoodQ Agent System - Startup Script | No | absolute path operations; binary/network download |
| `scripts/setup_gpu_environments.bat` | Bootstrap-Critical | ================================================================================ | Yes | None detected |
| `scripts/setup_wsl2_audio.py` | Unclear/Obsolete | GoodQ4All - WSL2 Audio Processing Setup | No | absolute path operations; binary/network download |
| `scripts/setup_wsl2_audio_fast.py` | Unclear/Obsolete | GoodQ4All - Fast WSL2 Audio Setup (No Sudo Required) | No | absolute path operations |
| `scripts/setup_wsl2_audio_userspace.py` | Unclear/Obsolete | GoodQ4All - WSL2 Audio Setup (User-Space Only) | No | absolute path operations |
| `scripts/show_intelligence_report.ps1` | Unclear/Obsolete | Requires -Version 5.1 | No | None detected |
| `scripts/show_kg_insights.py` | Unclear/Obsolete | -*- coding: utf-8 -*- | No | None detected |
| `scripts/show_phase2_enhancement.py` | Unclear/Obsolete | Utility script for show phase2 enhancement. | No | None detected |
| `scripts/smoke_phase_a.py` | Runtime Utility | Utility script for smoke phase a. | Manual Review | absolute path operations |
| `scripts/start_api.ps1` | Unclear/Obsolete | Experimental FastAPI launcher; scaffolded API helper, not part of the canonical bootstrap/runtime path. | No | environment mutation |
| `scripts/start_llm_servers.bat` | Bootstrap-Critical | ============================================================================ | Manual Review | absolute path operations |
| `scripts/start_vllm_servers.bat` | Bootstrap-Critical | GoodQ4All vLLM Server Startup Script | Yes | None detected |
| `scripts/status_vllm_servers.bat` | Runtime Utility | GoodQ4All vLLM Server Status Check | Yes | None detected |
| `scripts/stop_vllm_servers.bat` | Runtime Utility | GoodQ4All vLLM Server Stop Script | Yes | None detected |
| `scripts/sync_env_local.ps1` | Unclear/Obsolete | Utility script for sync env local. | No | None detected |
| `scripts/sync_faiss_to_qdrant.py` | Runtime Utility | One-time helper to push FAISS vectors into Qdrant for long-term storage. | Yes | None detected |
| `scripts/system_readiness_check.py` | Dev Utility | System readiness checker for the goodq4all stack. | Manual Review | absolute path operations |
| `scripts/system_status_check.py` | Unclear/Obsolete | Comprehensive System Status Check | No | absolute path operations |
| `scripts/test_all_endpoints.py` | Dev Utility | Phase 2: Comprehensive Endpoint Validation | Manual Review | absolute path operations; binary/network download |
| `scripts/test_clap_clustering.py` | Unclear/Obsolete | Phase 1 Validation: Test CLAP-based Speaker Clustering | No | absolute path operations |
| `scripts/test_control_agent_phase2.py` | Dev Utility | Test Control Agent Phase 2: Auto-Healing Capabilities | Manual Review | absolute path operations |
| `scripts/test_control_agent_phase3.py` | Unclear/Obsolete | Phase 3 Test: Control Agent Pipeline Integration | No | absolute path operations |
| `scripts/test_control_integration.py` | Dev Utility | Test Control Agent integration with ingestion pipeline | Manual Review | None detected |
| `scripts/test_from_windows_simple.py` | Dev Utility | Simple test to check if Windows can reach vLLM | Manual Review | absolute path operations; binary/network download |
| `scripts/test_full_system.py` | Unclear/Obsolete | FULL SYSTEM TEST - Complete Pipeline Validation | No | absolute path operations |
| `scripts/test_gpu_allocation.py` | Unclear/Obsolete | Test GPU allocation and memory limits across all environments | No | absolute path operations |
| `scripts/test_gpu_config.py` | Dev Utility | Quick GPU Test - Verify GPU configuration is working | Manual Review | absolute path operations |
| `scripts/test_gpu_pipeline.py` | Unclear/Obsolete | Test GPU allocation with a small video | No | None detected |
| `scripts/test_gpu_scene_detection.py` | Dev Utility | Test GPU-Accelerated Scene Detection | Manual Review | absolute path operations |
| `scripts/test_llm_client.py` | Dev Utility | GoodQ4All LLM Client Integration Test | Manual Review | None detected |
| `scripts/test_llm_client_simple.py` | Unclear/Obsolete | Test LLM Client from Windows | No | absolute path operations |
| `scripts/test_llm_connectivity.py` | Dev Utility | GoodQ4All - LLM Connectivity Test | Manual Review | absolute path operations; binary/network download |
| `scripts/test_osd_integration.py` | Unclear/Obsolete | OSD Integration Test Script | No | None detected |
| `scripts/test_phase2_integration.py` | Dev Utility | Phase 2 Control Agent Integration Test | Manual Review | None detected |
| `scripts/test_phase3_healing.py` | Dev Utility | Test script for Phase 3: Self-Healing & Learning | Manual Review | None detected |
| `scripts/test_recovery_system.py` | Dev Utility | Test Recovery System (Phase 2) | Manual Review | absolute path operations |
| `scripts/test_transcribe_integration.py` | Unclear/Obsolete | Integration Test: Audio Transcribe with WSL2 Fallback | No | absolute path operations |
| `scripts/test_vad_gpu_usage.py` | Dev Utility | Test VAD Implementation and GPU Usage | Manual Review | None detected |
| `scripts/test_vad_simple.py` | Dev Utility | Simple standalone test for Silero VAD on audio file. | No | destructive actions; absolute path operations |
| `scripts/test_vision_gpu.py` | Dev Utility | Test Vision GPU Setup | Manual Review | None detected |
| `scripts/test_vllm_from_windows.ps1` | Dev Utility | Quick Windows Test Script | Manual Review | absolute path operations; binary/network download |
| `scripts/test_wsl2_bridge.py` | Dev Utility | Test WSL2 Audio Bridge End-to-End | Manual Review | None detected |
| `scripts/utilities/backup_gpu_steps.py` | Unclear/Obsolete | Steps that need refactoring | No | None detected |
| `scripts/utilities/gpu_config.py` | Unclear/Obsolete | GPU Isolation and Memory Management Configuration | No | absolute path operations |
| `scripts/utilities/llm_client.py` | Runtime Utility | LLM Integration Module for GoodQ | Manual Review | absolute path operations; binary/network download |
| `scripts/utilities/process_manager.py` (retired) | Unclear/Obsolete | Legacy process-manager cluster removed from the tracked surface after its API/watchdog helpers were retired. | No | absolute path operations |
| `scripts/utils/check_api_data.py` | Unclear/Obsolete | Quick check of what data is available for the API | No | absolute path operations |
| `scripts/utils/check_databases.py` | Unclear/Obsolete | Check memory.db | No | absolute path operations |
| `scripts/utils/check_db.py` | Unclear/Obsolete | Validation/test utility for check db. | No | None detected |
| `scripts/utils/check_db2.py` | Unclear/Obsolete | List all tables | No | None detected |
| `scripts/utils/check_db_schema.py` | Unclear/Obsolete | Check database schema and tables. | No | None detected |
| `scripts/utils/check_gpu_status.py` | Unclear/Obsolete | GPU Status and Diagnostics Tool | No | None detected |
| `scripts/utils/check_ingestion_status.py` | Unclear/Obsolete | Check current ingestion status and progress | No | absolute path operations |
| `scripts/utils/check_kg_schema.py` | Unclear/Obsolete | Check knowledge graph database schema and content. | No | None detected |
| `scripts/utils/check_llm_availability.py` | Unclear/Obsolete | GoodQ LLM Availability Checker | No | absolute path operations; binary/network download |
| `scripts/utils/check_memory_db.py` | Unclear/Obsolete | Check memory database contents | No | absolute path operations |
| `scripts/utils/check_missing_data.py` | Unclear/Obsolete | Check what face, speaker, and emotion data exists | No | None detected |
| `scripts/utils/check_nested.py` | Unclear/Obsolete | Get a scene with faces | No | None detected |
| `scripts/utils/check_sample_data.py` | Unclear/Obsolete | Check sample.mp4 processing data in the knowledge graph. | No | None detected |
| `scripts/utils/check_scene_ids.py` | Unclear/Obsolete | Validation/test utility for check scene ids. | No | None detected |
| `scripts/utils/check_scene_keys.py` | Unclear/Obsolete | Get a fully enriched scene | No | None detected |
| `scripts/utils/check_scene_meta.py` | Unclear/Obsolete | Check scene metadata in memory.db | No | None detected |
| `scripts/utils/check_scene_results.py` | Unclear/Obsolete | Check database for scene data | No | None detected |
| `scripts/utils/check_schema.py` | Unclear/Obsolete | Get schema for each table | No | None detected |
| `scripts/utils/check_tables.py` | Unclear/Obsolete | Get all tables | No | None detected |
| `scripts/utils/check_watchdog_status.py` | Unclear/Obsolete | GoodQ Watchdog Status Checker | No | absolute path operations |
| `scripts/utils/validate_critical_fixes.py` | Unclear/Obsolete | Validate that all critical fixes are working | No | None detected |
| `scripts/utils/validate_environment_fix.py` | Unclear/Obsolete | Validate that all environment fixes are working | No | None detected |
| `scripts/utils/validate_models.py` | Unclear/Obsolete | Comprehensive model validation script to ensure all steps produce actual output. | No | absolute path operations |
| `scripts/utils/validate_phase3_integration.py` | Unclear/Obsolete | Phase 3 Pipeline Integration Validator | No | absolute path operations |
| `scripts/utils/validate_pipeline_flow.py` | Unclear/Obsolete | Pipeline Flow Validator for GoodQ Multimodal Ingestion | No | absolute path operations |
| `scripts/utils/validate_ui_config.py` | Unclear/Obsolete | GoodQ UI Configuration Validator | No | absolute path operations |
| `scripts/utils/verify_command_center.py` | Unclear/Obsolete | Quick verification that Command Center is fully operational | No | binary/network download |
| `scripts/utils/verify_model_lockdown.py` | Dev Utility | Verify that all models are properly locked down with exact versions. | Manual Review | absolute path operations |
| `scripts/utils/verify_phase1_fix.py` | Unclear/Obsolete | Comprehensive verification of Phase 1 fix - Segment text storage | No | None detected |
| `scripts/validate_gpu_setup.bat` | Bootstrap-Critical | ================================================================================ | Manual Review | environment mutation |
| `scripts/vllm_control.bat` | Runtime Utility | Utility script for vllm control. | Yes | None detected |
| `scripts/wsl/install_audio_service.sh` | Bootstrap-Critical | Install/enable systemd service for GoodQ WSL2 audio_service.py | Yes | None detected |
| `scripts/wsl/install_vllm_service.sh` | Runtime Utility | Install/enable the vLLM Llama-1B systemd service inside WSL. | Manual Review | privileged systemd mutation; environment mutation |
| `scripts/wsl/monitor.sh` | Unclear/Obsolete | ============================================================================ | No | binary/network download |
| `scripts/wsl/smoke_wsl_memory.sh` | Runtime Utility | One-stop smoke test + light self-heal for GoodQ memory stack on WSL. | Manual Review | absolute path operations; environment mutation; binary/network download |
| `scripts/wsl/start_all_vllm.sh` | Bootstrap-Critical | GoodQ4All - Start All vLLM Servers | Manual Review | absolute path operations; binary/network download |
| `scripts/wsl/update_vllm_service_port.sh` | Runtime Utility | Helper to retarget the vllm-llama1b systemd unit to the normalized port (38005). | Yes | None detected |
| `scripts/wsl2_audio_bridge.py` | Runtime Utility | GoodQ4All WSL2 Audio Bridge | Yes | None detected |
| `scripts/wsl2_process_audio.py` | Unclear/Obsolete | GoodQ4All WSL2 Audio Processor | No | None detected |
| `scripts/wsl2_quick_install.sh` | Bootstrap-Critical | GoodQ4All - WSL2 Audio Quick Install | Manual Review | absolute path operations |
| `wsl2_audio/audio_bridge.py` | Runtime Utility | GoodQ4All - Windows to WSL2 Audio Bridge | Manual Review | absolute path operations |
| `wsl2_audio/audio_service.py` | Bootstrap-Critical | GoodQ4All - WSL2 Audio Processing Service | Yes | None detected |
| `wsl2_audio/check_cuda.py` | Dev Utility | CUDA/cuDNN Diagnostic Script for GoodQ Audio Processing | Manual Review | None detected |
| `wsl2_audio/enable_in_pipeline.py` | Runtime Utility | Script to enable WSL2 audio processing in the pipeline | Yes | None detected |
| `wsl2_audio/process.sh` | Runtime Utility | Check if arguments are provided | Yes | None detected |
| `wsl2_audio/process_audio.py` | Runtime Utility | GoodQ Audio Processing Script - Full Classification | Yes | None detected |
| `wsl2_audio/process_minimal.sh` | Runtime Utility | Minimal GoodQ Audio Processing - Transcription Only | Yes | None detected |
| `wsl2_audio/setup_cuda_env.sh` | Bootstrap-Critical | CUDA/cuDNN Environment Setup for GoodQ Audio Processing | Manual Review | environment mutation |
| `wsl2_audio/setup_windows.ps1` | Bootstrap-Critical | GoodQ4All - Windows Setup for WSL2 Audio Offload | Manual Review | absolute path operations |
| `wsl2_audio/setup_wsl2_audio.sh` | Bootstrap-Critical | GoodQ4All - WSL2 Audio Processing Environment Setup | Manual Review | binary/network download |
| `wsl2_audio/start_wsl2_service.bat` | Runtime Utility | ============================================================================ | Yes | None detected |
| `wsl2_audio/test_bridge.py` | Dev Utility | Test script for WSL2 audio bridge | Manual Review | absolute path operations |
| `wsl2_audio/test_pipeline.py` | Dev Utility | Comprehensive Audio Processing Pipeline Test | Manual Review | None detected |
| `wsl2_audio/test_simple.sh` | Dev Utility | Validation/test utility for test simple. | Manual Review | None detected |

## Archived/Migrations (Excluded from Main Table)

| Script Path | Category | Purpose Summary | Safe to Run on Clean Install? | Risk Notes |
|---|---|---|---|---|
| `scripts/archive/migrations/CRITICAL_EMOJI_PURGE.py` | One-Time Migration | CRITICAL EMOJI PURGE - Remove ALL emojis from Python files | No | absolute path operations |
| `scripts/archive/migrations/Fix-SystemPaths.ps1` | One-Time Migration | > | No | absolute path operations; environment mutation |
| `scripts/archive/migrations/migrate_data_paths.ps1` | One-Time Migration | GoodQ4All Data Path Migration Script | No | destructive actions; absolute path operations |

## Danger Review Queue

| Script Path | Category | Risk Notes |
|---|---|---|
| `LAUNCH_GOODQ.ps1` | Bootstrap-Critical | environment mutation |
| `agents/control_agent.py` | Runtime Utility | absolute path operations |
| `agents/ingestion/scene_detector.py` | Runtime Utility | absolute path operations |
| `agents/llm_agent.py` | Runtime Utility | absolute path operations |
| `agents/orchestrator.py` | Unclear/Obsolete | absolute path operations |
| `agents/pipeline_integration.py` | Unclear/Obsolete | absolute path operations |
| `agents/recovery_strategies.py` | Runtime Utility | absolute path operations |
| `agents/self_healing_monitor.py` | Runtime Utility | absolute path operations |
| `agents/watchdog_agent_integration.py` | Unclear/Obsolete | absolute path operations |
| `cli/conduits_processing.py` | Runtime Utility | destructive actions |
| `cli/goodq_doctor.py` | Runtime Utility | absolute path operations |
| `cli/graph_query.py` | Runtime Utility | absolute path operations |
| `cli/memory.py` | Runtime Utility | destructive actions |
| `cli/monitor_ingestion.py` | Runtime Utility | absolute path operations |
| `cli/nl_query.py` | Runtime Utility | absolute path operations |
| `cli/run_ingestion.py` | Runtime Utility | absolute path operations |
| `cli/step_runner.py` | Runtime Utility | absolute path operations |
| `cli/system_status.py` | Runtime Utility | absolute path operations |
| `cli/watchdog.py` | Runtime Utility | absolute path operations |
| `scripts/TEST_GPU_PIPELINE.bat` | Unclear/Obsolete | destructive actions; absolute path operations |
| `scripts/_lib/interpreter_bindings.ps1` | Runtime Utility | absolute path operations |
| `scripts/analytics_engine.py` | Runtime Utility | absolute path operations |
| `scripts/analytics_query.py` | Runtime Utility | absolute path operations |
| `scripts/analyze_unified_kg.py` | Unclear/Obsolete | absolute path operations |
| `scripts/api_server.py (retired)` | Unclear/Obsolete | absolute path operations |
| `scripts/apply_performance_fixes.py` | Unclear/Obsolete | absolute path operations |
| `scripts/apply_scene_summaries.py` | Unclear/Obsolete | destructive actions |
| `scripts/audio_gpu_monitor.py` | Runtime Utility | absolute path operations |
| `scripts/audio_gpu_report.py` | Runtime Utility | absolute path operations |
| `scripts/audit_all_exceptions.py` | Unclear/Obsolete | absolute path operations |
| `scripts/audit_codebase.py` | Unclear/Obsolete | absolute path operations |
| `scripts/audit_vision_pipeline.py` | Dev Utility | absolute path operations |
| `scripts/bootstrap_models.py` | Bootstrap-Critical | absolute path operations |
| `scripts/build_kg_standalone.py` | Unclear/Obsolete | absolute path operations |
| `scripts/build_knowledge_graph_from_db.py` | Runtime Utility | absolute path operations |
| `scripts/build_unified_kg.py` | Unclear/Obsolete | absolute path operations |
| `scripts/cache_readiness_check.py` | Dev Utility | absolute path operations |
| `scripts/clean_old_processing.py` | Unclear/Obsolete | destructive actions; absolute path operations |
| `scripts/command_center.ps1` | Runtime Utility | destructive actions; absolute path operations |
| `scripts/comprehensive_clean_run.py` | Runtime Utility | destructive actions; absolute path operations |
| `scripts/comprehensive_gpu_setup.py` | Unclear/Obsolete | absolute path operations |
| `scripts/config_schema.py` | Runtime Utility | absolute path operations |
| `scripts/dataset_specs.py` | Unclear/Obsolete | absolute path operations |
| `scripts/diagnose_gpu_issue.py` | Unclear/Obsolete | absolute path operations |
| `scripts/diagnose_transcription.py` | Unclear/Obsolete | absolute path operations |
| `scripts/diagnostics/FULL_SYSTEM_AUDIT.py` | Unclear/Obsolete | destructive actions; absolute path operations |
| `scripts/diagnostics/FULL_SYSTEM_TEST.bat` | Unclear/Obsolete | destructive actions; absolute path operations; binary/network download |
| `scripts/diagnostics/RUN_FULL_DIAGNOSTIC.ps1` | Unclear/Obsolete | environment mutation |
| `scripts/diagnostics/diagnose_system.py` | Dev Utility | absolute path operations |
| `scripts/diagnostics/monitor_progress.py` | Dev Utility | absolute path operations |
| `scripts/diagnostics/quick_laptop_test.ps1` | Unclear/Obsolete | binary/network download |
| `scripts/docs/doc_drift_lint.py` | Bootstrap-Critical | absolute path operations |
| `scripts/download_datasets.py` | Unclear/Obsolete | absolute path operations; environment mutation |
| `scripts/extract_test_frame.py` | Unclear/Obsolete | absolute path operations |
| `scripts/fix_imports.py` | Unclear/Obsolete | absolute path operations |
| `scripts/full_diagnostic_check.py` | Unclear/Obsolete | absolute path operations |
| `scripts/gpu_setup_windows.py` | Bootstrap-Critical | absolute path operations |
| `scripts/health/pull_health_export.py` | Runtime Utility | absolute path operations; environment mutation |
| `scripts/init_qdrant_collections.py` | Unclear/Obsolete | absolute path operations; binary/network download |
| `scripts/install_pipeline_wsl.py` | Bootstrap-Critical | destructive actions; absolute path operations |
| `scripts/install_vad.bat` | Unclear/Obsolete | absolute path operations |
| `scripts/install_vision_gpu.bat` | Bootstrap-Critical | environment mutation |
| `scripts/mission_launch.ps1` | Bootstrap-Critical | destructive actions; absolute path operations; environment mutation |
| `scripts/monitor_ingestion.py` | Runtime Utility | absolute path operations |
| `scripts/monitor_ingestion_progress.py` | Unclear/Obsolete | absolute path operations |
| `scripts/monitor_ingestion_realtime.py` | Unclear/Obsolete | absolute path operations |
| `scripts/monitoring/monitor_ingestion.bat` | Unclear/Obsolete | environment mutation |
| `scripts/optimize_config.py` | Unclear/Obsolete | absolute path operations |
| `scripts/optimize_vision_gpu.py` | Runtime Utility | absolute path operations |
| `scripts/organize_project.py` | Unclear/Obsolete | absolute path operations |
| `scripts/phase2_completion_report.py` | Runtime Utility | absolute path operations |
| `scripts/phase2_embedding_analysis.py` | Runtime Utility | absolute path operations |
| `scripts/phase2_fixes.py` | Runtime Utility | absolute path operations |
| `scripts/phase2_llm_integration.py` | Unclear/Obsolete | absolute path operations; environment mutation; binary/network download |
| `scripts/phase2_progress_report.py` | Runtime Utility | absolute path operations |
| `scripts/phase2_verify.py` | Dev Utility | absolute path operations |
| `scripts/phase5_full_validation.py` | Runtime Utility | absolute path operations |
| `scripts/pin_model_versions.py` | Runtime Utility | absolute path operations |
| `scripts/preflight_check.ps1` | Unclear/Obsolete | absolute path operations; binary/network download |
| `scripts/prepare_step_envs.ps1` | Runtime Utility | destructive actions; absolute path operations; environment mutation |
| `scripts/promote_wsl_audio.py` | Runtime Utility | absolute path operations |
| `scripts/qdrant/CHECK_QDRANT.bat` | Unclear/Obsolete | binary/network download |
| `scripts/qdrant/INSTALL_QDRANT_SERVICE.bat` | Bootstrap-Critical | destructive actions; absolute path operations; binary/network download |
| `scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat` | Bootstrap-Critical | absolute path operations |
| `scripts/refresh_vllm_portproxy.bat` (retired) | Unclear/Obsolete | destructive actions; binary/network download |
| `scripts/rotate_logs.py` | Runtime Utility | destructive actions; absolute path operations |
| `scripts/run_audio_diarize_test.bat` | Unclear/Obsolete | environment mutation |
| `scripts/run_gpu_optimization_tests.py` | Dev Utility | destructive actions; absolute path operations |
| `scripts/setup/VALIDATE_PYTHON_PATHS.bat` | Unclear/Obsolete | environment mutation |
| `scripts/setup/configure_envs_pythonpath.py` | Bootstrap-Critical | absolute path operations |
| `scripts/setup/install_goodq.py` | Bootstrap-Critical | absolute path operations |
| `scripts/setup/setup_agents.ps1` | Unclear/Obsolete | absolute path operations |
| `scripts/setup/start_agents.ps1` | Unclear/Obsolete | absolute path operations; binary/network download |
| `scripts/setup_wsl2_audio.py` | Unclear/Obsolete | absolute path operations; binary/network download |
| `scripts/setup_wsl2_audio_fast.py` | Unclear/Obsolete | absolute path operations |
| `scripts/setup_wsl2_audio_userspace.py` | Unclear/Obsolete | absolute path operations |
| `scripts/smoke_phase_a.py` | Runtime Utility | absolute path operations |
| `scripts/start_api.ps1` | Unclear/Obsolete | environment mutation |
| `scripts/start_llm_servers.bat` | Bootstrap-Critical | absolute path operations |
| `scripts/system_readiness_check.py` | Dev Utility | absolute path operations |
| `scripts/system_status_check.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_all_endpoints.py` | Dev Utility | absolute path operations; binary/network download |
| `scripts/test_clap_clustering.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_control_agent_phase2.py` | Dev Utility | absolute path operations |
| `scripts/test_control_agent_phase3.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_from_windows_simple.py` | Dev Utility | absolute path operations; binary/network download |
| `scripts/test_full_system.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_gpu_allocation.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_gpu_config.py` | Dev Utility | absolute path operations |
| `scripts/test_gpu_scene_detection.py` | Dev Utility | absolute path operations |
| `scripts/test_llm_client_simple.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_llm_connectivity.py` | Dev Utility | absolute path operations; binary/network download |
| `scripts/test_recovery_system.py` | Dev Utility | absolute path operations |
| `scripts/test_transcribe_integration.py` | Unclear/Obsolete | absolute path operations |
| `scripts/test_vad_simple.py` | Dev Utility | destructive actions; absolute path operations |
| `scripts/test_vllm_from_windows.ps1` | Dev Utility | absolute path operations; binary/network download |
| `scripts/utilities/gpu_config.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utilities/llm_client.py` | Runtime Utility | absolute path operations; binary/network download |
| `scripts/utilities/process_manager.py` (retired) | Unclear/Obsolete | absolute path operations |
| `scripts/utils/check_api_data.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/check_databases.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/check_ingestion_status.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/check_llm_availability.py` | Unclear/Obsolete | absolute path operations; binary/network download |
| `scripts/utils/check_memory_db.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/check_watchdog_status.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/validate_models.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/validate_phase3_integration.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/validate_pipeline_flow.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/validate_ui_config.py` | Unclear/Obsolete | absolute path operations |
| `scripts/utils/verify_command_center.py` | Unclear/Obsolete | binary/network download |
| `scripts/utils/verify_model_lockdown.py` | Dev Utility | absolute path operations |
| `scripts/validate_gpu_setup.bat` | Bootstrap-Critical | environment mutation |
| `scripts/wsl/install_vllm_service.sh` | Runtime Utility | privileged systemd mutation; environment mutation |
| `scripts/wsl/monitor.sh` | Unclear/Obsolete | binary/network download |
| `scripts/wsl/smoke_wsl_memory.sh` | Runtime Utility | absolute path operations; environment mutation; binary/network download |
| `scripts/wsl/start_all_vllm.sh` | Bootstrap-Critical | absolute path operations; binary/network download |
| `scripts/wsl2_quick_install.sh` | Bootstrap-Critical | absolute path operations |
| `wsl2_audio/audio_bridge.py` | Runtime Utility | absolute path operations |
| `wsl2_audio/setup_cuda_env.sh` | Bootstrap-Critical | environment mutation |
| `wsl2_audio/setup_windows.ps1` | Bootstrap-Critical | absolute path operations |
| `wsl2_audio/setup_wsl2_audio.sh` | Bootstrap-Critical | binary/network download |
| `wsl2_audio/test_bridge.py` | Dev Utility | absolute path operations |
