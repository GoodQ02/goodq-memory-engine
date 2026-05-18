<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: COMPLETE_EXECPLAN -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# First-Run Truth Closure Implementation Plan

> Status note (2026-05-17): This checklist is complete and preserved as the
> implementation trail for first-run truth closure, not as an active TODO queue.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development where available, or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the first-time-user audit findings from `<scratch_root>\OPUS_AUDIT-5.17.26.md` without changing runtime defaults.

**Architecture:** Documentation-first onboarding repair, small template cleanup, and root fixture hygiene. Runtime behavior remains Windows-first, local-first, and config-loader governed.

**Tech Stack:** Markdown docs, PowerShell/batch launch surfaces, Python bootstrap tests, Git-managed public/profile mirrors.

---

## Scope Lock

Allowed:
- Update first-run, install, bootstrap, watchdog, sample, changelog, and agent-facing docs.
- Update `.env.template` comments/default placeholders.
- Remove or ignore duplicated root fixture directories that are not active runtime inputs.
- Adjust stale sample harnesses that point to missing sample media.
- Mirror public-safe front-door docs to `goodq4all_public` and profile wording only if needed.

Forbidden:
- No runtime default change for `DEFAULT_DATA_ROOT`.
- No broad docs reorganization.
- No ingestion, witness reruns, or package installation.
- No edits to local untracked `branding/`, `reports/control_recurrence/`, or `scratch/` artifacts.

## Tasks

- [x] Patch first-run docs with host prerequisites, non-Windows exit ramp, `.env.local.template` guidance, installer prompt preview, Qdrant skipped-service warning, and data-root derivation clarity.
- [x] Patch `.env.template` so active templates do not contain literal Windows drive roots.
- [x] Remove duplicated root fixtures from tracked source or mark them local-only, then fix `samples/README.md` and stale sample harnesses.
- [x] Refresh agent-facing status/snapshot docs and changelog for the May 17 visual first-run/demo state.
- [x] Mirror only public-safe updates to `goodq4all_public` and update `goodq02_profile` only if its front-door text drifts.
- [x] Validate with doc lint, focused bootstrap tests, and final `git status --short --branch` checks.

## Acceptance Criteria

- A first-time Windows user can identify prerequisites before running any command.
- A non-Windows visitor sees a clear supported-host boundary before the installer command.
- The inbox path is described as `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\` with `GOODQ_DATA_ROOT` defined as the base root.
- Active templates no longer pin `GOODQ_DATA_ROOT` to a literal drive root.
- Root `smoke_inbox/` and `test_input/` no longer look like supported first-run drop zones.
- Current docs no longer claim stale branch/head checkpoints as live truth.
