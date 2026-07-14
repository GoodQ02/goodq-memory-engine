<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Authenticated Protected-Membership Composition Audit

## Outcome

Do not implement authenticated composition yet.

The completed configuration projection, cleanup-target filesystem observer,
protected-membership projection, external-pin reader, and candidate-plan core
remain valid closed checkpoints. Current source has no production-owned
manifest reader, protected-member observer, ProgramData lexical-locator
handoff, or authenticated composition authority.

The previous next-mission wording incorrectly included the cleanup-target
`FilesystemObservation` in protected-membership authentication. That evidence
belongs only to later `ResolvedCleanupScope` assembly. It does not read the
manifest, authenticate membership, or observe protected members.

The smallest safe next mission is a read-only boundary audit only for the
fixed-child manifest reader. The composition-owned ProgramData locator/recheck
requires its own later audit and must not share this reader's implementation or
test seam. No reader or composition code is authorized by this checkpoint.

## Governing Invariant

Configuration supplies routing, the manifest supplies protected-member content,
and the independently protected external pin authorizes only the exact manifest
bytes whose SHA-256 it contains. None of those sources proves the physical
state of protected members. Final protected authority requires a separate
no-follow protected-member observer and pin-chain physical-alias rejection.

The sole future production owner remains `python -m cli.clean_memory plan`.
That edge must invoke every reader and observer itself and may accept only the
operator's exact epoch identifier. It may not accept caller-built manifest
bytes, pin evidence, membership projections, protected observations, locators,
digests, or paths.

## No-Repeat Inventory

| Completed authority | Exact responsibility | Boundary that stays closed |
| --- | --- | --- |
| `cli.clean_memory` | Pure `ResolvedPlanConfiguration` and configuration digest | No command surface or observation yet |
| `cli.clean_memory_filesystem` | Epoch-root and cleanup-target pre-state | No manifest or protected-member authority |
| `cli.clean_memory_protected_membership` | Canonical 18-role structural membership from supplied bytes | No reader provenance, pin authentication, or physical observation |
| `cli.clean_memory_external_pin` | Fixed Windows trust-root observation and path-free ten-key evidence | No manifest read, locator export, enrollment, publication, or composition |
| `steps.common.clean_memory` | Injected candidate-plan validation and immutable first-writer storage | No production reader, observer, or runtime orchestration |

Repository-wide production search found no caller of
`resolve_plan_configuration()`, `observe_filesystem()`,
`project_protected_membership()`, `read_external_pin()`, or
`build_candidate_plan()` beyond their definitions. No production module joins
the pin and membership modules.

## Corrected Authority Graph

The future runtime order is exact:

1. load configuration exactly once and create the unchanged v1 projection;
2. call the completed no-argument external-pin reader;
3. pass that direct exact `ExternalPinEvidence` to a future fixed-child manifest
   reader that selects only `protected-boundaries.json` beneath the projected
   candidate evidence root, hashes the exact bytes read from the same held
   handle, compares that digest with the pin evidence before JSON parsing, and
   validates those same bytes as canonical before returning them;
4. bind and recheck the exact direct reader outputs without relocating the
   reader-owned digest-mismatch decision;
5. pass those same authenticated bytes to the completed pure membership
   projection;
6. resolve and recheck the actual ProgramData Known Folder locator in-process,
   then reject lexical pin/member overlap before protected-member I/O;
7. call a future protected-member observer with the exact membership snapshot
   and direct pin-chain physical exclusion identities;
8. reject every protected alias or pin-chain physical collision, recheck all
   immutable inputs and race fences, and only then emit the selected path-free
   `ProtectedBoundaryEvidence` set;
9. separately run the completed cleanup-target filesystem observer;
10. run the future fail-closed Qdrant observer; and
11. assemble `ResolvedCleanupScope`, build, and immutably persist the candidate
    plan.

The target filesystem observer is deliberately after authenticated protected
authority in this sequence. A trust-root or manifest failure should prevent
unnecessary target observation, and target evidence must never substitute for
manifest or protected-member evidence.

## Exact Future Bindings

The future authenticated boundary must bind direct outputs only:

- exact `ResolvedPlanConfiguration` canonical bytes and
  `configuration_scope_sha256`;
- exact manifest-reader bytes, SHA-256, fixed child identity, and held physical
  evidence;
- exact `ExternalPinEvidence` canonical bytes and
  `external_pin_evidence_sha256`;
- exact `ProtectedMembershipProjection` canonical bytes and
  `protected_membership_scope_sha256`; and
- exact protected-observer envelopes, each binding the same membership digest.

The external pin's `manifest_sha256` must equal both the direct manifest-reader
digest and the manifest digest embedded in the membership projection. The
membership configuration digest must equal the direct configuration digest.
Every exact type, private canonical byte string, public detached projection,
and detached digest must remain unchanged through final composition.

The external pin evidence digest is an integrity binding over the direct trusted
reader result, source, enrolled identity, security policy, and pin-chain
physical state; it is not proof by itself that the reader ran. The
already-selected protected-boundary identity envelope carries the authenticated
membership digest into candidate planning. Do not reopen candidate-plan v1 or
the completed ten-key pin schema merely to duplicate those bindings.

## ProgramData Locator Gap

The pin reader correctly emits no raw path. Its actual Known Folder locator and
validation helper remain private, while the governing contract requires lexical
pin/member separation before protected observation. Ambient `PROGRAMDATA`,
configuration, CWD, caller input, or a second guessed path is not authority.

A separate later audit must select one composition-owned locator/recheck contract
that:

- calls the actual `FOLDERID_ProgramData` Known Folder API;
- appends only the fixed pin-chain children;
- retains the canonical locator in-process and never serializes or logs it;
- brackets it with direct pin-reader evidence and later physical exclusions;
- rejects lexical member overlap before protected-member I/O; and
- does not import a private reader symbol or weaken the exact four-symbol reader
  export.

Whether that requires a shared extraction-parity checkpoint or a separate
composition-owned resolver must be decided before locator code. The manifest
reader seam must not absorb that decision, and the completed pin-reader
checkpoint must not be reopened by assumption.

## Failure Precedence

Future production orchestration must stop at the first failed stage:

1. invalid configuration fails before any filesystem operation;
2. the completed `ExternalPinReaderError` taxonomy remains authoritative for
   pin acquisition and security failures;
3. the future manifest reader owns one finite path-free physical/read taxonomy,
   including manifest digest mismatch before JSON parsing or return;
4. later composition rechecks the exact direct outputs and treats any
   inconsistency or change as a final-fence failure, without displacing the
   reader-owned digest comparison;
5. membership structural errors are translated at the outward runtime boundary
   rather than leaking arbitrary parser detail;
6. lexical pin/member conflict fails before protected-member I/O;
7. the future protected observer owns one finite path-free physical-state
   taxonomy and returns no partial evidence;
8. a changed direct input or final fence is `observation_raced`; and
9. cleanup-target `FilesystemObservationError` is possible only after
   authenticated protected authority succeeds.

Exact manifest-reader, locator, and protected-observer codes remain closed until
their separate boundary audits. That is a blocker to composition code, not
permission to invent generic fallbacks.

## Import And Test Boundaries

The final runtime edge remains in `cli.clean_memory` and must use lazy imports so
the completed import-pure configuration API stays capability-free. A future
composition helper may receive only exact direct-output types inside that owned
edge; no CLI or public runtime API may accept prebuilt evidence.

The next implementation candidate, after its boundary audit, is exactly:

- `cli/clean_memory_protected_manifest.py`; and
- `tests/unit/test_clean_memory_protected_manifest.py`.

Its RED oracle must cover the fixed child, direct exact `ExternalPinEvidence`,
pin-first order, same-handle bounded read and digest, reader-owned
mismatch-before-parser behavior, canonical validation before return,
redirect/replacement/race refusal, closed path-free errors, exact input fences,
and the absence of caller path/digest/bytes authority. It performs no
ProgramData locator work, protected member observation, target filesystem
observation, Qdrant access, plan work, enrollment, publication, approval, or
cleanup.

Later focused seams remain separate:

1. ProgramData locator/recheck boundary audit and implementation;
2. protected-member observer and pin-chain exclusion;
3. final authenticated composition and its direct-output-only oracle;
4. fail-closed Qdrant observation; and
5. `ResolvedCleanupScope` plus runnable `plan` orchestration.

## Independent Review

Three bounded read-only reviewers independently traced the production call
graph, lifecycle and error precedence, and documentation semantics. All agreed
that the current filesystem observation is the wrong input for membership
authentication, the manifest reader and protected observer are absent, and
composition code must remain closed. They also confirmed that `PROJECT.md` was
still naming the already-completed external-pin reader mission.

## Evidence Boundary

This audit read repository source, tests, active contracts, checkpoints, and the
sole roadmap. It did not read or change live ProgramData, a production pin or
manifest, a token, ACL, configured or protected root, GoodQ data, Qdrant,
service state, evidence stores, jobs, MiniAgent, or cleanup targets.
