# Documentation Authority Policy

<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

## Purpose

This policy locks documentation governance for GoodQ4All and enforces a single source of truth for runtime behavior and operator decisions.

## Document Types

### CANONICAL

Authoritative contract documents that define runtime behavior, platform doctrine, and precedence rules.

### OPERATIONAL

Active setup, runbook, and troubleshooting guidance. Must align with CANONICAL docs.

### HISTORICAL

Time-bound release notes, prior states, and session snapshots preserved for auditability.

### EXPERIMENTAL

Drafts, analysis notes, exploratory docs, and temporary planning artifacts.

## Badge Templates (HTML Comments)

Use these comment badges at the top of each document.

```html
<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: YYYY-MM-DD -->
```

```html
<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: YYYY-MM-DD -->
```

```html
<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: path/to/canonical.md -->
<!-- DOC_ARCHIVED_ON: YYYY-MM-DD -->
```

```html
<!-- DOC_BADGE: EXPERIMENTAL -->
<!-- DOC_STATUS: DRAFT -->
<!-- DOC_REVIEW_OWNER: team-or-person -->
```

## Governance Rules

1. CANONICAL documents are the highest authority.
2. OPERATIONAL docs must never contradict CANONICAL docs.
3. HISTORICAL docs are immutable records except for archival badges/pointers.
4. EXPERIMENTAL docs cannot be cited as runtime contract.
5. Every doc update must refresh `DOC_LAST_VERIFIED` when semantics change.
6. New docs must declare a type badge before merge.

## Canonical Location Rules

1. Canonical bootstrap contract docs live under `docs/bootstrap/` plus approved root-level contract artifacts.
2. Runtime architecture contracts live in approved `docs/architecture/`, `docs/systems/`, and component authority files.
3. New canonical docs require explicit reference in `docs/bootstrap/doc_authority_map.md` under the curated canonical authority set.

## Update and Verification Rules

1. Update canonical docs first, then operational docs, then historical references.
2. If an operational guide conflicts with canonical doctrine, treat the guide as stale until corrected.
3. Every phase checkpoint must record verified date and commit hash in canonical docs.
4. `docs/bootstrap/doc_authority_map.md` is a curated authority index, not a whole-repo generated snapshot.

## Precedence Rules

Precedence, highest to lowest:

1. CANONICAL
2. OPERATIONAL
3. HISTORICAL
4. EXPERIMENTAL

If conflicts exist, CANONICAL supersedes all other categories.
