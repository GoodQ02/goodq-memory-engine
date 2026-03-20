# GoodQ4All Troubleshooting & Fixes Index

**Purpose:** Central entrypoint for troubleshooting guides and fix-specific reports. Use this to find the right level of detail when diagnosing or resolving issues.

---

## Canonical Troubleshooting Guides

- `docs/TROUBLESHOOTING.md` – Primary, canonical troubleshooting guide for common issues and workflows.
- `docs/TROUBLESHOOTING_EMPTY_ANALYSIS.md` – Specialized guide for “empty analysis” / no-output scenarios.
- `docs/reference/FIXES_QUICK_REFERENCE.txt` – Historical quick reference for early critical fixes (still useful as a checklist).

---

## High-Impact Fix Summaries

Use these when you need to understand major fix sets that changed system behavior:

- `docs/CRITICAL_FIXES_APPLIED.md` – Log of critical fixes applied across the system.
- `docs/IMMEDIATE_FIXES.md` – High-priority fixes from early diagnostics.
- `docs/SYSTEM_FIX_SUMMARY.md` – System-wide fix summary.
- `docs/PERFORMANCE_FIXES.md` – Performance-focused fixes and optimizations.
- `docs/FIXES_APPLIED_2025-10-17.md` – Session-specific fix summary.

Agent-facing fix summaries:

- `docs/agent-communications/CORE_FIXES_COMPLETE.md`
- `docs/agent-communications/FIXES_APPLIED.md`
- `docs/agent-communications/COMMIT_MESSAGE_CORE_FIXES.md`
- `docs/agent-communications/RECENT_FIXES.md`

---

## Subsystem Fix Reports

### Audio / Transcription

- `docs/AUDIO_DIARIZATION_FIX.md`
- `docs/AUDIO_DIARIZATION_COMPLETE_FIX.md`
- `docs/TRANSCRIPTION_FIX_APPLIED.md` (agent-communications)
- `docs/HUGGINGFACE_COMPLETE_FIX.md`
- `docs/SENTIMENT_TIMEOUT_FIX.md`
- `docs/SILENT_FAILURE_FIX_REPORT.md`

### GPU / Vision / Scene Detection

- `docs/SCENE_CONFIG_FIX_COMPLETE.md`
- `docs/SCENE_DETECTION_FIX_APPLIED.md`
- `docs/SCENE_DETECTION_FIX_COMPLETE.md`
- `docs/SCENE_DETECTION_FIX_COMPLETE_2025-11-09.md`
- `docs/SCENE_DETECTION_FIX_REPORT.md`
- `docs/MISSION_BRIEFS/SCENE_DETECTION_FIX_2025-10-13.md`
- `docs/SCENE_SUMMARIZATION_FIX_PLAN.md`
- `docs/GPU_FIX_SUMMARY.md`
- `docs/PHASE4_EMOTION_DETECTION_FIXES.md`
- `docs/archive/proof_of_concept/ui/UI_PHASE2_FIXES.md` - Historical UI-fix note for the retired scaffolded web interface.
- `docs/technical/VISION_GPU_OPTIMIZATION.md` (see also `docs/guides/gpu/GPU_LLM_WSL_INDEX.md` for the current GPU/WSL surface).

### Configuration / Dependencies

- `docs/MISSING_DEPS_QUICK_FIX.md`
- `docs/OPENCV_MISSING_FIX.md`
- `docs/PYTHON_PATH_FIX.md`
- `docs/WEB_INTERFACE_FIX_REPORT.md`
- `docs/project_management/status_reports/CRITICAL_FIX_REQUIRED.md`
- `docs/project_management/status_reports/SETTINGS_FIX_COMPLETE.md`
- `docs/history/archived_docs/BUGFIX_HEREDOC.md`

---

## When to Use What

- Start with:
  - `docs/TROUBLESHOOTING.md` for general issues.
  - `docs/TROUBLESHOOTING_EMPTY_ANALYSIS.md` for “no output / empty analysis” cases.
- Then consult:
  - `docs/CRITICAL_FIXES_APPLIED.md` and `docs/SYSTEM_FIX_SUMMARY.md` for an overview of past critical fixes.
  - Specific subsystem fix reports (audio, scene detection, config) when symptoms match those areas.
- For GPU, LLM, WSL2, and Watchdog-specific troubleshooting, prefer:
  - `docs/GPU_LLM_WSL_INDEX.md`
  - `docs/WATCHDOG_INDEX.md`
