# Documentation Archive Plan

<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

## Purpose

This plan defines how non-canonical documents are archived without losing audit history.

## Target Archive Structure

```text
docs/archive/
  agent-comms/
  audits/
  fix-reports/
  implementation-reports/
  project-history/
  releases/
  reports/
  session-reports/
  status-reports/
  misc/
```

## Migration Rules

1. Prefer move operations over deletion.
2. Preserve relative structure from original location where practical.
3. Add a HISTORICAL badge to every archived document.
4. Add `DOC_CANONICAL_POINTER` when topic overlaps active canonical scope.
5. Do not rewrite historical content beyond badge/pointer insertion.
6. Keep git history intact through file moves (no content-copy replacement).

## Naming Conventions

1. Preserve original filename whenever possible.
2. If destination conflict exists, append `__phaseb` before extension.
3. Keep extension unchanged (`.md`, `.txt`, etc.) unless conversion is explicitly approved.

## Redirect and Stub Guidance

1. For high-traffic legacy entry points (for example `START_HERE`/`QUICK_START`), keep a short stub in place.
2. Stubs must include:
   - current canonical pointer
   - phase/date note
   - minimal migration context
3. Stubs are OPERATIONAL docs and must not contain conflicting setup logic.

## Deletion Policy

Deletion is allowed only when all conditions are true:

1. File is marked `DELETE (safe)` in `docs/bootstrap/doc_authority_map.md`.
2. File has no inbound references from active docs (`docs/` and `README*.md`).
3. File is a duplicate/backup artifact with no unique technical content.
4. Deletion is performed in a docs-only commit with explicit rationale.
