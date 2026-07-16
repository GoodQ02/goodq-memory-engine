<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-04 Configuration Portability Checkpoint Evidence

## Invariant

Tracked configuration must be a portable, schema-valid baseline. Private
operator identity, machine topology, hardware descriptions, household service
addresses, voice preferences, active epochs, secrets, and literal workstation
roots belong in ignored local authority or supported environment references.
Applying the GOOD-CUBE local authority to the portable baseline must preserve
the effective private runtime configuration.

## Checkpoint Lineage

- Branch: `codex/r04-config-portability-checkpoint`
- R-03 evidence base: `45c741e1`
- Master-register checkpoint: `a1f57efb docs: establish master repair register`
- R-04 code checkpoint: `84c1d22d fix: sanitize portable runtime configuration`
- R-04 status: independently reviewed, verified, and privately checkpointed

## Included R-04 Surface

- generic tracked user, machine-topology, hardware, voice, and household-service
  defaults
- ignored local-override template coverage for every displaced private field
- `GOODQ_EPOCH_ID`-derived paths, Qdrant collections, and Phase 6 collection
  names instead of a dated tracked epoch
- environment-relative identity templates
- `%PROGRAMDATA%`-derived Windows Conda fallback paths
- a canonical loading contract that names tracked, ignored, environment, and
  resolved-runtime authority
- regression coverage for private network addresses, workstation roots, dated
  epochs, local topology, voice preferences, and missing local overlays

## Explicit Boundaries

- No private value or secret is recorded in this evidence document.
- The frozen mixed main checkout was not staged, reset, restored, cleaned, or
  rewritten.
- The active GOOD-CUBE ignored overlay remains local runtime authority and is
  not part of this Git checkpoint.
- This checkpoint does not reconcile all historical configuration documents;
  semantic documentation drift remains R-09/R-13/R-10 work.
- This checkpoint does not alter service binding, firewall, or LAN policy;
  those remain R-20.

## Verification Evidence

Fresh verification completed on 2026-07-11 in the isolated R-04 worktree.

- 25 configuration, redaction, print-config, platform, and installer tests
  passed.
- Python static parsing passed for the changed Python files.
- All four changed YAML files parsed successfully.
- `git diff --cached --check` passed.
- The owned portability scan found no literal drive root or RFC1918 address in
  the shipped R-04 configuration and contract surface.
- The staged seam contained exactly seven R-04 files.
- The mixed main checkout remained at the same 85-entry dirty inventory.
- Independent read-only review found no remaining machine, location, LAN,
  voice, secret, or scope blocker.

## Private Runtime Equivalence

The active main runtime and the portable checkpoint were resolved in separate
`goodq_core` processes. The target comparison applied the existing ignored
GOOD-CUBE overlay plus the newly displaced private fields in memory only.
Canonical sorted JSON was SHA-256 compared without printing private values.

- full resolved configuration: equal
- user, model, host, paths, Qdrant, Phase 6, identity, system, TTS, and Home
  Assistant sections: all equal
- no-overlay portable baseline: covered by focused tests and resolves generic
  `default` epoch/collection authority

## Adjacent Evidence Drift

The repository-wide documentation drift lint still reports pre-existing active
document path claims outside this seven-file seam. That baseline is unchanged
and remains assigned to R-13; it was not hidden as an R-04 pass.

## Resume

Continue R-17 extraction from the frozen mixed main checkout. R-06 progressive
ingestion is the next already-verified family to reconstruct in its own
worktree. Do not mix identity prototypes, current-state reconstruction, or
generated report repair into that checkpoint.
