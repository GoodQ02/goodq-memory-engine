# GoodQ4All Code Cleanup Index

**Purpose:** Provide a non-destructive map of scripts and utilities that appear less used or historical, so future cleanup work can focus on the right areas without guessing. No files are removed by this document.

---

## Methodology (High-Level)

- Scanned `scripts/` and `cli/` for executable files (`.py`, `.ps1`, `.bat`, `.cmd`).
- Counted references to each file name in `docs/`, `scripts/`, and `cli/` using `rg`.
- Cross-checked with `docs/SHIP_PROFILE.md` and other canonical docs to avoid touching supported entrypoints.
- Classified files into:
  - **Likely In Use** – referenced by other scripts/docs or part of the shipping profile.
  - **Cleanup Candidates (Manual Review)** – zero in-repo references in docs/scripts/cli and not part of the ship profile, suggesting they may be legacy or one-off utilities.

> Note: “Cleanup candidate” does **not** mean “safe to delete”; it means “deserves a closer look before future cleanup/refactor work.”

---

## Likely In Use (Examples, Not Exhaustive)

These scripts are referenced multiple times and/or are explicitly part of the shipping profile:

- Core orchestration and CLI:
  - `cli/run_ingestion.py`
  - `cli/graph_query.py`
  - `cli/memory.py`
- Health & readiness:
  - `scripts/system_readiness_check.py`
  - `scripts/cache_readiness_check.py`
  - `scripts/check_db.py`, `scripts/check_schema.py`
- GPU/LLM/WSL:
  - `scripts/gpu_config.py`
  - `scripts/quick_gpu_setup.py`
  - `scripts/test_gpu_scene_detection.py`
  - `scripts/test_llm_client.py`
  - `scripts/test_wsl2_bridge.py`
- Watchdog:
  - `cli/watchdog.py`
  - `scripts/utils/check_watchdog_status.py`
  - `tests/integration/test_watchdog.py`
- Diagnostics / dashboards:
  - `scripts/command_center.ps1`
  - `scripts/diagnostics/diagnose_system.py`
  - `scripts/diagnostics/monitor_progress.py`

These are in-scope for the shipping profile and should be treated as supported interfaces.

---

## Cleanup Candidates (Manual Review)

The following scripts had **zero references** in `docs/`, `scripts/`, and `cli/` and are not mentioned in `docs/SHIP_PROFILE.md`. They are good candidates for manual review to decide whether to:
- Keep as-is (if used ad-hoc).
- Mark explicitly as archived/legacy.
- Remove in a future cleanup pass.

### Phase- and Report-Related Helpers

- `scripts/phase2_clean_and_reingest.py`
- `scripts/phase2_completion_report.py`
- `scripts/phase2_embedding_analysis.py`
- `scripts/phase2_fixes.py`
- `scripts/phase2_progress_report.py`
- `scripts/phase2_verify.py`
- `scripts/phase3_diagnostic.py`
- `scripts/phase5_full_validation.py`

### Diagnostics and Deep Analysis

- `scripts/analyze_database.py`
- `scripts/analyze_sample_output.py`
- `scripts/build_knowledge_graph_from_db.py`
- `scripts/check_missing_data.py`
- `scripts/check_nested.py`
- `scripts/check_scene_ids.py`
- `scripts/check_scene_results.py`
- `scripts/clear_scene_data.py`
- `scripts/deep_scene_analysis.py`
- `scripts/diagnostics/audit_gpu_steps.py`
- `scripts/diagnostics/check_dbs.py`
- `scripts/diagnostics/check_latest_results.py`

### GPU / Installation Utilities

- `scripts/FIX_SCENE_DETECTION_CRITICAL.py`
- `scripts/gpu_setup_windows.py`
- `scripts/install_gpu_support.ps1`
- `scripts/install_vision_gpu.bat`

### VLLM & Environment Utilities

- `scripts/stop_vllm_servers.bat`
- `scripts/setup/install_package_all_envs.py`

### Monitoring / Flow Helpers

- `scripts/monitor_ingestion.py`
- `scripts/reset_for_production.ps1`

### Tests / Verification Helpers

- `scripts/Test-AudioDiarization.ps1`
- `scripts/diagnostics/verify_phase1.ps1`
- `scripts/find_transcription_data.py`
- `scripts/test_control_agent_phase2.py`
- `scripts/test_control_integration.py`
- `scripts/test_from_windows_simple.py`
- `scripts/test_phase2_integration.py`
- `scripts/test_recovery_system.py`
- `scripts/test_vad_simple.py`
- `scripts/test_vllm_from_windows.ps1`
- `scripts/verify_command_center.py`
- `scripts/verify_phase1_fix.py`

---

## Suggested Future Actions

1. **Per-Script Review**
   - For each cleanup candidate, decide:
     - Is it still used manually (e.g. during ops/troubleshooting)?
     - If yes, consider referencing it from a canonical doc or index.
     - If no, consider moving it into `_ARCHIVE/goodq4all_scripts/legacy/` in a future pass.

2. **Align With Ship Profile**
   - Before any deletions, ensure no path referenced in `docs/SHIP_PROFILE.md` or other canonical docs is removed or renamed.

3. **Mark Legacy Scripts In-Place**
   - For scripts that must stay but are no longer part of the supported surface, consider adding a short header comment such as:
     - `# LEGACY UTILITY – kept for reference, not part of shipping surface.`

This index is intended as an aid for future cleanup and refactor work; it does not change runtime behavior by itself.

