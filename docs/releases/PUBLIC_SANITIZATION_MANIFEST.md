<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-09-26 -->

# Public release sanitization manifest

## Source and authority

- Private development source: `bddbd83206c78431036aac4aeb1160a7d511009f` (`dev`).
- Public parent: `d08ba886ef02a44845f6442b2dc4ea4a5c4f9571` (`main`).
- Public destination: `GoodQ02/goodq-memory-engine`, branch `main`.
- The public commit is a sanitized snapshot, not a merge of private history.
- Workstation deployment continues to use the private checkout. This mirror is
  independently checked source, not a second local service instance.

## Exclusions and transformations

Private reports, archives, witness receipts, model/corpus data, onboarding media,
host-specific maintenance scripts, and local plans are omitted. Signed model
manifests and product code retain their upstream source bytes. Public-only
changes are documentation, fixture/config anonymization, four epoch examples in
docstrings, public-scope test expectations, and the declared exclusions; no
runtime feature is developed exclusively in this mirror.

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

For the 2026-09-23 supervised dev-mode update, the eight changed source/test
files match the pinned private commit byte for byte. The four focused test
modules pass 56 tests with two existing Pydantic deprecation warnings.
Documentation drift, authority, dependency, banned-token, and installer
semantic checks pass. A CI-profile bootstrap check passes with the same
Baseline/GPU settings as hosted CI when this checkout's ignored workstation
`.env.local` is excluded from the check. Hosted results must still be matched
to the public commit after publication.

## Existing-store startup follow-up

The supervisor queries Qdrant before requesting service-start permission.
The regression fixture rejects a redundant start while still proving that a
stopped store is started and failed API startup blocks Watchdog. The five
native Windows startup checks pass on the private source.

## Supervised dev-mode follow-up

The portable supervisor, Dev On/Off scripts, dashboard labels, and focused tests
are copied from the pinned private source. Dev On reuses one verified existing
supervisor; Dev Off requests its receipt-bound drain before stopping the
configured GoodQ WSL compute extension. Ambient Ollama models and unrelated
workstation services are outside these scripts' scope. Public documentation
describes the portable behavior without GOOD-CUBE shortcut, panel, or distro
paths. The live sign-in shortcut and native panel remain private workstation
integration, not public installer content.

The initial publication was blocked by GitHub billing before job steps ran.
That block is cleared. Check the run matching the source commit in
[GitHub Actions](https://github.com/GoodQ02/goodq-memory-engine/actions)
for hosted results; local validation and hosted validation are separate evidence.

## Watchdog stale-owner follow-up

A stale lock could refer to a process ID recycled by Windows. The owner check
now requires the process to predate the lock and preserves an owner whose
identity cannot be read. Native lock, safety and real runtime lifecycle tests
pass (11 tests); the unrelated process is never terminated.

## Fresh-checkout hosted follow-up

Fresh-checkout verification caught two links to excluded internal archives in
the changelog. Those links now describe the public scope instead of implying
that private archives are available here.

The full hosted suite then passed 4,340 tests and found two public-scope fixture
mismatches. The retrieval-context matrix covers every published caller; the
private corpus-report case is replaced by an assertion that its excluded script
stays absent. The runtime-evidence listing test expects the explicitly unqualified
anonymous epoch from this snapshot. Both adaptations preserve the private
repository's original tests and change no product code or runtime behavior.

## Scoped operator documentation update (2026-09-26)

The concise agent guidance and operator skill are copied from the pinned private
source. The clean-memory workflow has the same current safety procedure, with a
public-checkout wording adjustment and a public reference boundary replacing its
private archive link. The private historical cleanup archive, workstation baseline,
runtime repair receipts, temporary-file backups, and worktree evidence are excluded.
Previously sanitized operator-lane and release-roadmap text is preserved.

This update changes documentation and instructions only. Product code, dependencies,
installer payloads, and runtime configuration are unchanged. It does not warrant
rebuilding an installer or restarting a user's services. Older local and hosted
verification results above belong to their named releases, not this commit.

Local gates for this documentation update passed: documentation drift and authority,
dependency drift, banned-token inspection, all 15 installer semantic checks, and
36 focused documentation-authority tests. The guidance and skill match the pinned
private source; only the declared workflow reference/checkout wording is adapted.
Hosted checks are verified separately against the resulting public commit.

## Context7 library rename correction - 2026-09-26

The root context7.json URL and README Context7 link now target
`https://context7.com/goodq02/goodq-memory-engine`. The public verification key
is unchanged; the JSON matches private dev. Only public URL metadata and this
release manifest changed. Documentation drift/authority, dependency drift,
banned-token, and all 15 installer semantic checks pass. Upstream claim status
and index completion are separate service-side checks, not release guarantees.