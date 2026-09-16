<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-09-16 -->

# Public release sanitization manifest

## Source and authority

- Private development source: `fcb8dbfc037a9bf857c6c2d6a654a7ac0e911535` (`dev`).
- Public parent: `eca11dddf8c27e2483361d9f19adea9261bbc833` (`main`).
- Public destination: `GoodQ02/goodq-memory-engine`, branch `main`.
- The public commit is a sanitized snapshot, not a merge of private history.
- Workstation deployment continues to use the private checkout. This mirror is
  independently checked source, not a second local service instance.

## Exclusions and transformations

Private reports, archives, witness receipts, model/corpus data, onboarding media,
host-specific maintenance scripts, and local plans are omitted. Signed model
manifests and product code retain their upstream source bytes. Public-only
changes are documentation, fixture/config anonymization, four epoch examples in docstrings, and the declared
exclusions; no runtime feature is developed exclusively in this mirror.

The current-state files are generated from a public **unconfigured template**.
Their zero counts and `not_probed` states do not assert an empty or healthy
installation. Operator preferences and the runtime evidence manifest use
anonymous sample identity; they cannot qualify any real corpus.

## Validation boundary

Required gates are source parity, privacy and portability inspection,
documentation drift/authority/dependency checks, installer semantic contract
checks, and focused unit tests covering the changed source. Record terminal
results in the commit and local release receipt before publication.

This release updates source only. It does not replace published installer
assets, certify arbitrary hardware, or claim a restored backup. Existing public
history is retained; the snapshot prevents new private history from being pushed.

## Local verification

- Documentation drift, authority, dependency and banned-token gates pass.
- Installer semantic compatibility passes all 15 checks.
- The initial changed-source suite passed 554 tests and found two defects.
  Retiring obsolete candidate-only scripts cleared the catalog gate (51 tests).
  Cross-process fallback locking passed 43 targeted audit/privacy tests.
- Unconfigured-template truth and projection checks passed 65 tests.
- Product code and signed model-manifest bytes match the pinned private source,
  apart from the declared comment examples and privacy exclusions.
- Known source warnings: Pydantic class-based configuration is deprecated.

## Existing-store startup follow-up

The supervisor queries Qdrant before requesting service-start permission.
The regression fixture rejects a redundant start while still proving that a
stopped store is started and failed API startup blocks Watchdog. The five
native Windows startup checks pass on the private source.

Hosted CI did not execute for the initial publication: GitHub reported an
account billing lock before any job steps ran. Local results above remain the
verification evidence; this is not a green hosted-CI claim.
