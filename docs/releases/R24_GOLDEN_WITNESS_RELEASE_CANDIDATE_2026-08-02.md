<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: RELEASE_LEDGER -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# R-24 Golden Witness Release Candidate — 2026-08-02

## Scope

This candidate merges the isolated Golden Witness contract into private `dev`.
It hardens the explicit runtime snapshot, rejects mutable paths outside the
witness root, requires four distinct witness-named Qdrant collections for every
loopback endpoint, and pins Phase 6 vector writes to that candidate map.

The candidate also includes Dev On/Dev Off runtime hardening, strict WSL audio
worker hash deployment, local encoder pre-warm, and the live Qwen model identity
alignment.

## Verification

- R-24 focused suite: 39 passed.
- Isolated configuration regression: 8 passed, including a non-default
  loopback-port containment bypass regression.
- Documentation drift and dependency checks: passed.
- Banned-token lint: passed after excluding preserved sibling worktrees from the
  checkout-scoped scan; the new linter regression test passed.
- Full baseline suite: 1,236 tests passed before a pre-existing
  `clean_memory_filesystem` Windows held-handle observer test failed to see a
  temporary directory beneath the local user temp root. The R-24 change set does
  not touch that subsystem. This remains a release follow-up, not a passing
  full-suite claim.

## Guardrails retained

- Witness execution is isolated and does not authorize canonical promotion.
- Active TurboQuant retrieval remains disabled. Its candidate benchmark did not
  meet the performance gate, so corpus re-ingestion is not authorized.
- No model download, canonical data migration, or public release is implied by
  this candidate.

## Public-release gate

Before a public tag is created, prepare a sanitized downstream release from the
authorized public mirror, omit local-only witness records and experimental
TurboQuant material, validate that mirror independently, and resolve the
pre-existing full-suite observer failure or explicitly publish it as an accepted
known issue.
