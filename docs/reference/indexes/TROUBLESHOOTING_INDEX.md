# GoodQ4All Troubleshooting & Fixes Index

**Purpose:** Central entrypoint for troubleshooting guides and fix-specific reports.

---

## Canonical Troubleshooting Guides

- `docs/TROUBLESHOOTING.md` – Primary, canonical troubleshooting guide for common issues and workflows.
- `docs/TROUBLESHOOTING_EMPTY_ANALYSIS.md` – Specialized guide for no-output / empty-analysis scenarios.
- `docs/reference/WSL_AUDIO_RUNTIME.md` – Current WSL audio runtime truth surfaces, readiness states, and bridge error fields.

---

## High-Impact Fix Summaries

- `docs/CRITICAL_FIXES_APPLIED.md`
- `docs/IMMEDIATE_FIXES.md`
- `docs/SYSTEM_FIX_SUMMARY.md`
- `docs/PERFORMANCE_FIXES.md`
- `docs/FIXES_APPLIED_2025-10-17.md`

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
- `docs/agent-communications/TRANSCRIPTION_FIX_APPLIED.md`
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
- `docs/technical/VISION_GPU_OPTIMIZATION.md`

### Configuration / Dependencies

- `docs/MISSING_DEPS_QUICK_FIX.md`
- `docs/OPENCV_MISSING_FIX.md`
- `docs/PYTHON_PATH_FIX.md`
- `docs/WEB_INTERFACE_FIX_REPORT.md`
- `docs/project_management/status_reports/CRITICAL_FIX_REQUIRED.md`
- `docs/project_management/status_reports/SETTINGS_FIX_COMPLETE.md`
- `docs/history/archived_docs/BUGFIX_HEREDOC.md`

---

## When To Use What

- Start with:
  - `docs/TROUBLESHOOTING.md` for general issues
  - `docs/TROUBLESHOOTING_EMPTY_ANALYSIS.md` for no-output cases
  - `docs/reference/WSL_AUDIO_RUNTIME.md` for WSL audio readiness and bridge failures
- Then consult:
  - `docs/CRITICAL_FIXES_APPLIED.md` and `docs/SYSTEM_FIX_SUMMARY.md` for system-wide overview
  - the subsystem-specific fix reports when symptoms match
- For GPU, LLM, WSL2, and Watchdog-specific docs, prefer:
  - `docs/guides/gpu/GPU_LLM_WSL_INDEX.md`
  - `docs/guides/watchdog/WATCHDOG_INDEX.md`
