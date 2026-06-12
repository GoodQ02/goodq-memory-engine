<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# GoodQ4All Troubleshooting & Fixes Index

**Purpose:** Central entrypoint for current troubleshooting guides and archived fix-specific reports.

---

## Canonical Troubleshooting Guides

- `docs/guides/general/TROUBLESHOOTING.md` – Primary, canonical troubleshooting guide for common issues and workflows.
- `docs/archive/audits/TROUBLESHOOTING_EMPTY_ANALYSIS.md` – Historical specialized guide for no-output / empty-analysis scenarios.
- `docs/reference/WSL_AUDIO_RUNTIME.md` – Current WSL audio runtime truth surfaces, readiness states, and bridge error fields.

---

## High-Impact Fix Summaries

- `docs/archive/fix-reports/CRITICAL_FIXES_APPLIED.md`
- `docs/archive/fix-reports/IMMEDIATE_FIXES.md`
- `docs/archive/status-reports/SYSTEM_FIX_SUMMARY.md`
- `docs/archive/fix-reports/PERFORMANCE_FIXES.md`
- `docs/archive/fix-reports/FIXES_APPLIED_2025-10-17.md`

Agent-facing fix summaries:

- `docs/archive/agent-comms/CORE_FIXES_COMPLETE.md`
- `docs/archive/agent-comms/FIXES_APPLIED.md`
- `docs/archive/agent-comms/COMMIT_MESSAGE_CORE_FIXES.md`
- `docs/archive/agent-comms/RECENT_FIXES.md`

---

## Subsystem Fix Reports

### Audio / Transcription

- `docs/archive/fix-reports/AUDIO_DIARIZATION_FIX.md`
- `docs/archive/fix-reports/AUDIO_DIARIZATION_COMPLETE_FIX.md`
- `docs/archive/agent-comms/TRANSCRIPTION_FIX_APPLIED.md`
- `docs/archive/fix-reports/HUGGINGFACE_COMPLETE_FIX.md`
- `docs/archive/fix-reports/SENTIMENT_TIMEOUT_FIX.md`
- `docs/archive/fix-reports/SILENT_FAILURE_FIX_REPORT.md`

### GPU / Vision / Scene Detection

- `docs/archive/fix-reports/SCENE_CONFIG_FIX_COMPLETE.md`
- `docs/archive/fix-reports/SCENE_DETECTION_FIX_APPLIED.md`
- `docs/archive/fix-reports/SCENE_DETECTION_FIX_COMPLETE.md`
- `docs/archive/fix-reports/SCENE_DETECTION_FIX_COMPLETE_2025-11-09.md`
- `docs/archive/fix-reports/SCENE_DETECTION_FIX_REPORT.md`
- `docs/archive/fix-reports/SCENE_DETECTION_FIX_2025-10-13.md`
- `docs/archive/fix-reports/SCENE_SUMMARIZATION_FIX_PLAN.md`
- `docs/guides/gpu/GPU_FIX_SUMMARY.md`
- `docs/archive/fix-reports/PHASE4_EMOTION_DETECTION_FIXES.md`
- `docs/technical/VISION_GPU_OPTIMIZATION.md`

### Configuration / Dependencies

- `docs/archive/fix-reports/MISSING_DEPS_QUICK_FIX.md`
- `docs/archive/fix-reports/OPENCV_MISSING_FIX.md`
- `docs/archive/fix-reports/PYTHON_PATH_FIX.md`
- `docs/archive/fix-reports/WEB_INTERFACE_FIX_REPORT.md`
- `docs/archive/project-mgmt/CRITICAL_FIX_REQUIRED.md`
- `docs/archive/project-mgmt/SETTINGS_FIX_COMPLETE.md`
- `docs/archive/archived_docs/BUGFIX_HEREDOC.md`

---

## When To Use What

- Start with:
  - `docs/guides/general/TROUBLESHOOTING.md` for general issues
  - `docs/archive/audits/TROUBLESHOOTING_EMPTY_ANALYSIS.md` for historical no-output context
  - `docs/reference/WSL_AUDIO_RUNTIME.md` for WSL audio readiness and bridge failures
- Then consult:
  - archived fix reports only for past incident context
  - subsystem-specific current docs when symptoms match
- For GPU, LLM, WSL2, and Watchdog-specific docs, prefer:
  - `docs/guides/gpu/GPU_LLM_WSL_INDEX.md`
  - `docs/guides/watchdog/WATCHDOG_INDEX.md`
