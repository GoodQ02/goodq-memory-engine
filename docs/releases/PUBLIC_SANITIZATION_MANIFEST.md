<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# Public Release Sanitization Manifest

## Purpose

This public mirror is derived from the verified private development release,
then independently sanitized for portability, privacy, licensing, and a clean
first-run experience. It is not a second development authority.

## Candidate source

- Private source branch: `dev`
- Source revision: `9886b36d`
- Candidate branch: `codex/public-release-candidate`
- Public branch target: `main` (not updated by preparing this candidate)

## Excluded from the public tree

- root archive material that contains retired scripts or local runtime
  artifacts;
- generated reports, evidence snapshots, and runtime receipts;
- witness records, evaluation anchors, TurboQuant experiment material, and
  control-recurrence outputs;
- personal media, local memory stores, model caches, indexes, logs, and local
  configuration or credentials.
- orphaned, host-specific launch helpers that are not part of the documented
  public launcher contract.

The exclusions remain preserved in private development. They are not deleted
from the canonical project source.

Documentation-only historical records under `docs/archive/` remain available
as noncanonical reference material; they are not runtime inputs or release
evidence.

## Required gates before publication

1. Verify the candidate has no secrets, workstation paths, private runtime
   evidence, or unlicensed fixture material.
2. Regenerate and validate documentation indexes after sanitization.
3. Run the public portability and focused test gates in this candidate.
4. Review the exact candidate diff and release notes.
5. Obtain explicit approval before updating public `main` or creating a tag.
