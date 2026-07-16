<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-15 -->

# R-07 Authenticated Protected-Membership Composition Recheck Decision

## Outcome

Implement authenticated protected-membership composition only after this
decision is checkpointed. The exact implementation seam is the existing pair:

- `cli/clean_memory.py`; and
- `tests/unit/test_clean_memory_cli.py`.

Do not create a composition module, second test authority, public evidence
wrapper, schema, digest, parser, locator, reader, observer, or caller-injected
evidence API. Composition belongs inside the sole future
`python -m cli.clean_memory plan` owner and remains private until that command
surface is separately authorized.

The implementation adds one private helper to the existing module:

```python
def _compose_authenticated_protected_membership(
    configuration: ResolvedPlanConfiguration,
) -> tuple[ProtectedBoundaryEvidence, ...]:
    ...
```

`cli.clean_memory.__all__` remains exactly its current three configuration
symbols. The helper accepts only an exact direct configuration projection and
returns the observer's exact tuple. It accepts no pin, manifest, membership,
location, path, digest, backend, dependency, override, filesystem observation,
or planning object.

## No-Repeat Ownership Result

Current production ownership is singular and acyclic:

| Authority | Sole owner | Exact direct output |
| --- | --- | --- |
| Configuration | `cli.clean_memory` | `ResolvedPlanConfiguration` with canonical private JSON and `configuration_scope_sha256` |
| ProgramData location | `steps.common.clean_memory_windows_program_data_locator` | immutable `CleanMemoryWindowsProgramDataLocation` |
| External pin | `cli.clean_memory_external_pin` | `ExternalPinEvidence` with canonical private bytes and `external_pin_evidence_sha256` |
| Protected manifest | `cli.clean_memory_protected_manifest` | `ProtectedManifestEvidence` with exact manifest bytes, canonical evidence bytes, and detached digest |
| Structural membership | `cli.clean_memory_protected_membership` | `ProtectedMembershipProjection` with canonical private JSON and detached digest |
| Physical protected boundaries | `cli.clean_memory_protected_boundary` | exact 18-role `ProtectedBoundaryEvidence` tuple |
| Candidate-plan validation | `steps.common.clean_memory` | existing `ResolvedCleanupScope` and `CandidatePlan` authority |

Repository search finds no production composition caller. The external-pin
reader is the only current consumer of the shared ProgramData locator. There is
no duplicate production definition and no circular import today.

The new helper uses function-local lazy imports. The manifest and membership
modules depend directly on `cli.clean_memory`, and the observer depends on it
indirectly, so eager imports of those modules would create or widen a cycle.
The pin and locator modules do not depend on `cli.clean_memory`, but they remain
lazy so module import and configuration resolution stay capability-free and the
configuration preflight remains ahead of every native capability.

Keep every completed source and focused test unchanged except the selected
`cli.clean_memory` source/test pair. In particular, do not reopen the locator,
pin reader, manifest reader, membership projector, protected observer,
filesystem observer, candidate-plan core, MiniAgent, or action-job authority.

## Governing Invariant

Composition authenticates relationships among exact direct outputs. It does
not rediscover, reinterpret, or replace their authority.

The exact chain is:

```text
configuration digest
    -> manifest evidence configuration digest
    -> membership configuration digest

external-pin evidence digest
    -> manifest evidence external-pin digest

external-pin manifest digest
    -> exact manifest bytes SHA-256
    -> manifest evidence manifest digest
    -> membership manifest digest

membership digest
    -> every protected-boundary identity envelope
```

All accepted exact types, private canonical bytes, detached projections, and
detached digests remain unchanged through the final fence. The helper returns
no partial result.

The candidate-plan v1 schema remains unchanged. The existing boundary envelopes
already bind the membership digest, while the candidate plan separately binds
the configuration digest. A second composition wrapper or digest would
duplicate authority without proving that any reader ran.

## Exact Private Error Contract

The helper uses one immutable, deletion-protected private error type with only
these codes and exact path-free messages:

| Code | Exact message |
| --- | --- |
| `invalid_configuration` | `Clean-memory authenticated composition configuration is invalid` |
| `invalid_protected_membership` | `Clean-memory authenticated protected membership is invalid` |
| `pin_member_overlap` | `Clean-memory protected membership overlaps the external pin chain` |
| `observation_raced` | `Clean-memory authenticated protected authority changed during composition` |
| `composition_failed` | `Clean-memory authenticated protected-membership composition failed` |

The type and helper are private and do not enter `__all__`. Unknown codes,
assignment, deletion, notes, copying, serialization, or raw linked state are
rejected.

Dependency-owned exact public errors remain authoritative when their owned
stage fails before acceptance:

- `CleanMemoryWindowsProgramDataLocatorError` for initial locator ABI, binding,
  and baseline resolution;
- `ExternalPinReaderError` for the one direct pin read;
- `ProtectedManifestReaderError` for the one direct manifest read; and
- `ProtectedBoundaryObservationError` for the one direct physical observation.

An ordinary native-library loading failure before locator binding maps to
`composition_failed`. A locator error or unequal exact location after the
baseline location is accepted maps to `observation_raced`. Membership
projection or first-acceptance structural failure maps to
`invalid_protected_membership` only after every previously accepted upstream
snapshot and the latest required location fence remain exact. A wrong, forged,
malformed, or noncanonical dependency return not already represented by its
owner's exact public error maps to `composition_failed` only after the same
upstream-stability check. Any changed accepted direct input or post-baseline
location wins precedence and maps to `observation_raced`.

Unknown ordinary failures fail closed as `composition_failed`. Operation
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` preserve exact identity
and traceback after their cause/context graphs are replaced with bounded closed
composition errors. Unknown non-`Exception` values fail closed. No raw path,
location component, comparison key, native message, manifest content, identity,
or dependency detail enters public links or output.

## Native Locator Binding

The helper authenticates the configuration before importing or constructing a
capability. This preflight requires the exact Windows projection flavor and its
canonical Windows path topology; a valid POSIX configuration projection is not
eligible for this Windows-only composition and fails `invalid_configuration`
before ABI verification or DLL loading. It then uses only the public shared
locator surface:

1. call `verify_clean_memory_windows_program_data_locator_abi()`;
2. load exact `shell32` and then exact `ole32` with function-local
   `ctypes.WinDLL(..., use_last_error=True)`;
3. pass those exact libraries once to
   `bind_clean_memory_windows_program_data_locator()`; and
4. retain that exact bound locator for all four location acquisitions.

No alternate loader, environment value, caller library, fallback, search,
repository discovery, CWD, configuration path, cached global, or second
locator is permitted. The composition helper never passes its locator or
location into either physical reader; both readers retain their completed
independent observation boundaries.

## Exact Lifecycle

The future helper performs this order and stops on the first failure:

1. require and snapshot the exact `ResolvedPlanConfiguration` private canonical
   JSON and detached digest, including exact Windows flavor/topology, before any
   capability;
2. bind the shared locator and acquire one exact baseline location;
3. invoke `read_external_pin()` exactly once;
4. exact-type gate the pin return before property access and fully authenticate
   and snapshot it before forwarding; on failed acceptance, recheck the already-
   accepted configuration so drift wins, otherwise classify the stable failure
   as `composition_failed`; then reacquire the location, require exact equality
   with the baseline, and recheck the accepted configuration and pin snapshots;
5. invoke `read_protected_manifest(configuration,
   external_pin_evidence=pin)` exactly once with the same direct objects;
6. exact-type gate the manifest return before property access and fully
   authenticate and snapshot it before any property is forwarded; on failed
   acceptance, recheck configuration and pin snapshots so drift wins, otherwise
   classify the stable failure as `composition_failed`; then invoke
   `project_protected_membership(configuration,
   manifest_bytes=manifest.manifest_bytes)` exactly once, passing the exact
   retained bytes object returned by the manifest reader;
7. exact-type gate the membership return before property access and fully
   authenticate and snapshot it immediately; before classifying a malformed or
   structural return, recheck every accepted upstream snapshot so upstream drift
   wins `observation_raced` precedence;
8. authenticate every direct canonical byte string, detached projection,
   detached digest, and cross-digest binding;
9. reacquire the location, require exact equality, recheck every accepted
   snapshot, and perform lexical
   pin-chain/member exclusion before any protected-member I/O;
10. invoke `observe_protected_boundaries(membership,
   external_pin_evidence=pin)` exactly once with the same direct objects;
11. exact-type gate the returned tuple and each element before property access,
    then fully authenticate and snapshot the role order, canonical envelopes,
    and membership-digest bindings; before classifying a malformed return,
    recheck every accepted upstream snapshot so upstream drift wins
    `observation_raced` precedence; and
12. reacquire the location once more, require exact baseline equality, then
    recheck every accepted configuration, pin, manifest, membership, and
    boundary snapshot before returning that same tuple object.

The composition-owned retained locator is therefore resolved exactly four
times: baseline, after pin, before lexical exclusion/observer, and at the final
fence. The external-pin reader retains its own completed locator boundary. The
pin reader, manifest reader, membership projector, and protected observer each
run exactly once. No physical reader is repeated as a recheck.

Every dependency owns and completes its own per-operation resources before
returning. Composition retains the two process-loaded DLL objects required by
the bound locator, but owns no per-operation caller-cleanable token, descriptor,
session, file, or buffer. It therefore adds no explicit cleanup graph. It may
return only after every dependency cleanup and its own final fence succeed.

## Direct-Output Authentication

Composition validates exact types, not subclasses, before trusting a direct
output. It snapshots private canonical bytes and detached digests rather than
trusting mutable detached projections alone.

The cross-bindings are exact:

- manifest evidence `configuration_scope_sha256` and membership
  `configuration_scope_sha256` equal the direct configuration digest;
- manifest evidence `external_pin_evidence_sha256` equals the direct pin
  evidence digest;
- direct pin `manifest_sha256`, SHA-256 of the exact direct manifest bytes,
  manifest evidence `manifest_sha256`, and membership manifest SHA-256 are all
  equal;
- manifest evidence bytes, projection bytes, and detached digest remain exact;
- membership canonical JSON and detached digest remain exact; and
- every one of the 18 exact boundary envelopes carries the direct membership
  digest and the canonical role/logical-ID pair.

Composition does not parse the manifest bytes again, invoke the canonical
manifest validator again, validate reader security policy again, derive pin
physical identities, traverse protected members, render a new identity, or
call candidate-plan construction as an oracle. Those responsibilities remain
with their completed owners.

## Lexical Pin-Chain Exclusion

The retained location supplies one canonical drive root, the complete
ProgramData component tuple, the three fixed directory components, and the pin
name. Composition forms exactly five transient pin-chain component prefixes:

1. ProgramData anchor;
2. fixed `GoodQ` directory;
3. fixed `authority` directory;
4. fixed `clean-memory` directory; and
5. fixed pin file.

For every protected member, composition converts the already-canonical Windows
path to a drive plus complete component tuple. It creates comparison keys only
by case-folding the canonical drive/components. Equality, ancestor, or
descendant intersection with any of the five complete pin-chain prefixes fails
`pin_member_overlap` before the observer is called.

String prefix tests, `Path.resolve`, `commonpath`, normalization, filesystem
search, existence probes, alternate spelling, and partial-component matching
are forbidden. A shared textual prefix without a complete component boundary
is not overlap. The transient location, member path, and comparison keys never
enter evidence, representation, error text, logs, API output, or durable state.

The protected observer remains the sole owner of physical comparison against
all five pin identities. Lexical exclusion does not replace physical alias
proof, and composition does not reproduce physical identity logic.

## Exact RED Matrix

Before production changes, the existing focused test file must fail for:

1. absent private helper and private closed error while the exact three-symbol
   public API remains unchanged;
2. exact helper signature, exact configuration type only, and rejection of
   every caller pin, manifest, membership, location, path, digest, backend,
   dependency, or override argument;
3. module import and configuration resolver purity, function-local public
   imports, and absence of circular/private/dynamic imports;
4. complete exact Windows-flavor/topology configuration authentication before
   ABI verification, DLL load, locator binding, or any reader call, including
   rejection of a valid POSIX projection as `invalid_configuration`;
5. exact ABI-before-load order, exact Shell32/Ole32 load order/options, one
   public bind, one retained locator, and no alternate loader;
6. exactly four location resolutions and exact equality, with every later
   error or inequality classified as `observation_raced`;
7. one exact pin read, one exact manifest read, one exact membership projection,
   and one exact observer call in the selected order using the identical direct
   objects and manifest bytes, with every direct return exact-type gated before
   property access and fully authenticated before forwarding;
8. exact direct types, canonical private bytes, detached projections/digests,
   all cross-bindings, self-consistent forged instances, and mutation at every
   pre-observer and final fence;
9. component-boundary equality, ancestor, descendant, different-drive,
   case-folded, Unicode, and textual-prefix lexical cases against all five
   pin-chain prefixes;
10. refusal to call the observer until lexical overlap checks pass and proof
    that physical comparison remains observer-owned;
11. exact same-object return of 18 ordered `ProtectedBoundaryEvidence` values,
    exact canonical role envelopes and membership-digest bindings, with no
    wrapper, digest, copy, reconstruction, reorder, or partial tuple;
12. dependency-owned error propagation, the five exact private code/message
    pairs, unknown-code rejection, immutability, path-free bounded graphs, and
    phase-correct `observation_raced` translation;
13. first/middle/final failure stop order, upstream-drift precedence over stable
    malformed/structural classification, unknown ordinary and non-`Exception`
    closure, and exact named-control identity/traceback preservation;
14. fourth-location equality followed by final rechecks of configuration, pin,
    manifest, membership, and boundary tuple immediately before return; and
15. absence of cleanup-target filesystem observation, Qdrant, candidate-plan
    construction/persistence, configuration loading, MiniAgent, approval,
    jobs/tokens, process control, cleanup, logging, network, or output.

Negative-mutant tests must reject a public composition export, new composition
module, second test authority, eager import, private import, dependency
injection, skipped/reordered/duplicated call, copied direct object, omitted
digest binding, omitted locator fence, string-prefix overlap, missing equality/
ancestor/descendant/casefold collision, physical comparison in composition,
reader/observer duplication, new wrapper/digest/schema, partial return, raw
detail leakage, swallowed control flow, or any later-phase capability.

## Verification Gate

Run sequentially with the explicit `goodq_core` interpreter:

- the expanded `tests/unit/test_clean_memory_cli.py` composition/configuration
  suite first;
- unchanged locator, pin, manifest, membership, observer, held-handle,
  filesystem, candidate-plan, manifest-validator, reader-identity, security-
  mechanics, approval-authority, and action-job suites;
- one dependency-safe zero-drop authority union whose exact expected total is
  recorded before implementation;
- exact two-file compilation, unchanged three-symbol public API, import purity,
  dependency containment, source census, diff, and whitespace gates;
- documentation authority, semantic drift, banned-token, dependency-drift, and
  generated-index gates; and
- at least two independent current-byte ownership, lifecycle, privacy, and
  negative-oracle reviews after all corrections.

Implementation and documentation are checkpointed separately. The mixed main
checkout remains frozen.

## Evidence Boundary

This decision read only repository instructions, source, tests, contracts,
checkpoint evidence, Git/worktree state, and the sole roadmap. It did not read
or change live ProgramData, a production pin or manifest, token, ACL,
descriptor, configured or protected root, service, GoodQ data, Qdrant,
evidence store, job, MiniAgent, approval, or cleanup target.

## Next Bounded Mission

After this decision commits, implement only the exact private helper and tests
inside `cli/clean_memory.py` and `tests/unit/test_clean_memory_cli.py` through
RED/GREEN/refactor and independent current-byte review.

Cleanup-target filesystem observation, Qdrant observation, `ResolvedCleanupScope`
assembly, candidate-plan construction or persistence, command parsing,
configuration loading, approval, jobs/tokens, process control, and cleanup
execution remain closed.
