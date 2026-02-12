# Documentation Governance Summary

<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

## What Changed

- Introduced formal documentation governance and precedence policy.
- Added an archive migration policy for non-canonical documents.
- Applied document badges to classify authority level.
- Moved historical/experimental material into `docs/archive/` buckets.
- Added drift lint tooling to catch future documentation contract drift.

## Why This Changed

- Reduce documentation entropy and contradictory guidance.
- Make canonical runtime and bootstrap contracts explicit.
- Preserve history without letting historical docs override active doctrine.
- Enforce Phase A profile semantics consistently across docs.

## How To Update Docs Going Forward

1. Decide document type first: `CANONICAL`, `OPERATIONAL`, `HISTORICAL`, or `EXPERIMENTAL`.
2. Add the correct badge block at the top of the file.
3. If replacing a legacy guide, add `DOC_CANONICAL_POINTER` in the legacy doc.
4. For historical material, move it under `docs/archive/` instead of deleting.
5. Update `DOC_LAST_VERIFIED` when semantics or contracts change.
6. Run `python scripts/docs/doc_drift_lint.py` before merge.

## Badge Rules

- `CANONICAL`: authoritative contract; supersedes all lower classes.
- `OPERATIONAL`: active guide; must align with canonical docs.
- `HISTORICAL`: archived record; immutable except metadata/pointers.
- `EXPERIMENTAL`: draft or exploratory; never authoritative.

See canonical policy details in:

- `docs/bootstrap/doc_authority_policy.md`
- `docs/bootstrap/doc_archive_plan.md`

## Archive Policy

- Prefer moves to `docs/archive/...` over deletion.
- Preserve relative structure where practical.
- Add `HISTORICAL` badge and canonical pointer when topics overlap.
- Delete only when explicitly marked `DELETE (safe)` and unreferenced.
