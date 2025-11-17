# GoodQ4All Agent & Copilot Communications Index

**Purpose:** Explain the role of `docs/agent-communications/` and `docs/copilot_user_communications/` and highlight which documents are guidance vs historical session logs.

---

## What Lives Here

- `docs/agent-communications/` – Agent-facing notes, checklists, cleanup summaries, and session-specific reports generated during development.
- `docs/copilot_user_communications/` – Copilot/user-facing session summaries and overnight work reports.
- `docs/releases/SESSION_SUMMARY.md` – Release-focused session summary.

Most files in these directories are **historical snapshots** of specific sessions. Canonical technical behavior is defined in the primary docs (architecture, phases, GPU/LLM/WSL, troubleshooting, etc.).

---

## Guidance-Oriented Agent Docs

These are more “how to work” than “what happened,” and are useful to revisit:

- `docs/agent-communications/README.md` – Directory overview and high-level structure.
- `docs/agent-communications/MORNING_CHECKLIST.md` – Example morning checklist for system review and next steps (older paths but useful pattern).
- `docs/agent-communications/START_HERE_AFTER_WORK.md` – Guidance for resuming work after a session.
- `docs/agent-communications/NEXT_STEPS.md` – High-level next-steps guidance at a point in time.
- `docs/agent-communications/WELCOME_BACK.md` – Orientation note for returning to the project.
- `docs/agent-communications/MODEL_LOADING_FIXES.md` – Detailed explanation of model-loading fixes; complements canonical fix docs.

---

## Historical Session & Fix Logs (Agent)

These are primarily historical records of specific efforts and should be read as snapshots:

- `docs/agent-communications/ALL_ISSUES_RESOLVED.md`
- `docs/agent-communications/CLEANUP_SUMMARY.md`
- `docs/agent-communications/CLEANUP_VISUAL_GUIDE.txt`
- `docs/agent-communications/COMMIT_MESSAGE.md`
- `docs/agent-communications/COMMIT_SUCCESS.md`
- `docs/agent-communications/DEDUPLICATION_COMPLETE.md`
- `docs/agent-communications/DIAGNOSIS_SUMMARY.md`
- `docs/agent-communications/IMPLEMENTATION_COMPLETE.md`
- `docs/agent-communications/LINT_CLEAN_SESSION.md`
- `docs/agent-communications/OVERNIGHT_AUDIT_SUMMARY.md`
- `docs/agent-communications/RECENT_FIXES.md`
- `docs/agent-communications/SCENE_DETECTION_BUG_FIXED.md`
- `docs/agent-communications/SESSION_COMPLETE.txt`
- `docs/agent-communications/SESSION_COMPLETE_20251015.md`
- `docs/agent-communications/SESSION_SUMMARY_2025-10-18.md`
- `docs/agent-communications/TRANSCRIPTION_FIX_APPLIED.md`
- `docs/agent-communications/VALIDATION_AND_NEXT_STEPS.md`
- `docs/agent-communications/WATCHDOG_CLEANUP.md`

For canonical status and timelines, prefer `docs/CURRENT_SYSTEM_STATUS.md` and `docs/project-history/CHANGELOG.md`.

---

## Copilot/User Communications

These are user-facing narratives of sessions and overnight work:

- `docs/copilot_user_communications/MORNING_BRIEFING.md` – Morning overview after overnight work.
- `docs/copilot_user_communications/OVERNIGHT_INDEX.md` – Navigation index for overnight deliverables.
- `docs/copilot_user_communications/OVERNIGHT_AUDIT_FINDINGS.md` – Technical audit findings.
- `docs/copilot_user_communications/COMPREHENSIVE_ENHANCEMENT_PLAN.md` – Enhancement roadmap (vision-level).
- `docs/copilot_user_communications/OVERNIGHT_WORK_COMPLETE.md` – Overnight completion summary.
- `docs/copilot_user_communications/OVERNIGHT_MONITORING_REPORT.md` – Monitoring/reporting snapshot.
- `docs/copilot_user_communications/SESSION_SUMMARY.md` – Session summary; historical snapshot.

Release-level session summary:

- `docs/releases/SESSION_SUMMARY.md` – Release-focused summary for a specific recovery session (historical).

---

## How Agents Should Treat These Docs

- **Primary truth:** Always prefer canonical technical docs first:
  - `docs/SHIP_PROFILE.md`
  - `docs/ARCHITECTURE_REFERENCE.md`
  - `docs/project-history/CHANGELOG.md`
  - `docs/CURRENT_SYSTEM_STATUS.md`
  - Phase, GPU/LLM/WSL, Watchdog, and Troubleshooting indexes.
- **Historical context:** Use agent & Copilot communications to understand:
  - Why certain decisions were made.
  - How past sessions approached fixes and planning.
  - Additional narrative context around major changes.

