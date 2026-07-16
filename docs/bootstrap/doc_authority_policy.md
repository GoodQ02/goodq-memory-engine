# Documentation Authority Policy

<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

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

## Durable Documentation Shape

GoodQ documentation should prefer durable contract sheets over completion
snapshots. A subsystem should normally have:

1. one canonical contract or specification when it defines runtime behavior
2. one operational guide or index when operators need commands or navigation
3. historical notes only under `docs/archive/` or clearly marked
   `HISTORICAL`/`REFERENCE_ONLY`

Avoid creating new "final", "complete", "phase", or task-completion documents
for ordinary fixes. Record small task outcomes in commit messages, release
notes, status snapshots, or the relevant existing contract only when the
runtime contract changes.

If a document name overstates its authority, rename or rebadge it in a
docs-only cleanup pass before treating it as current truth.

## Folder Purpose Rules

Use the existing folders as authority boundaries:

- `docs/architecture/`: runtime contracts, cross-component boundaries, and
  architecture maps
- `docs/architecture/components/`: subsystem-specific architecture contracts
- `docs/bootstrap/`: bootstrap, documentation governance, and installation
  contract surfaces
- `docs/reference/`: stable operator and API references
- `docs/guides/`: task-oriented operational guides
- `docs/systems/`: current system runbooks and daemon/service doctrine
- `docs/technical/`: implementation notes and technical contracts; historical
  items must be explicitly marked
- `docs/testing/` and `docs/diagnostics/`: evidence, witness memos, and
  targeted audits
- `docs/releases/`: release notes and release-scoped status
- `docs/archive/`: historical material only; never current runtime authority

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
7. `DOC_BADGE` values are limited to `CANONICAL`, `OPERATIONAL`,
   `HISTORICAL`, and `EXPERIMENTAL`; narrower roles belong in `DOC_STATUS`.
8. Active Markdown must contain exactly one badge, one uppercase status, and
   one valid, non-future ISO `DOC_LAST_VERIFIED` date in its header.
9. Schema-governed `SKILL.md` files are exempt because their YAML frontmatter
   must remain first. Their package schema and skill verifier govern metadata.
10. Generated indexes use `OPERATIONAL / GENERATED_INDEX`; they are discovery
    surfaces and cannot claim canonical authority.
11. `DOC_STATUS` uses the closed compatibility registry
    `ALLOWED_DOC_STATUSES` in `scripts/docs/doc_authority_lint.py`. Adding a
    status requires a policy review plus a focused regression test; arbitrary
    uppercase labels are not accepted.

## Canonical Location Rules

1. Canonical bootstrap contract docs live under `docs/bootstrap/` plus approved root-level contract artifacts.
2. Runtime architecture contracts live in approved `docs/architecture/`, `docs/systems/`, and component authority files.
3. New canonical docs require explicit reference in `docs/bootstrap/doc_authority_map.md` under the curated canonical authority set.

## Update and Verification Rules

1. Update canonical docs first, then operational docs, then historical references.
2. If an operational guide conflicts with canonical doctrine, treat the guide as stale until corrected.
3. Every phase checkpoint must record verified date and commit hash in canonical docs.
4. `docs/bootstrap/doc_authority_map.md` is a curated authority index, not a whole-repo generated snapshot.
5. Run `python scripts/docs/doc_authority_lint.py verify` to check metadata,
   active links, bounded mission naming, generated-index parity, current-state
   parity, active epoch claims, and Qdrant storage-root semantics.

## Precedence Rules

Precedence, highest to lowest:

1. CANONICAL
2. OPERATIONAL
3. HISTORICAL
4. EXPERIMENTAL

If conflicts exist, CANONICAL supersedes all other categories.
