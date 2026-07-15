<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Windows ProgramData Locator Checkpoint

## Outcome

The selected shared Windows ProgramData locator authority is implemented and
privately checkpointed:

```text
f93ae143 Extract shared Windows ProgramData locator
```

The import-pure shared module now owns the actual `FOLDERID_ProgramData`
acquisition, fixed clean-memory child spelling, lexical result grammar, native
buffer lifetime, and path-free locator failures. The existing external-pin
reader delegates to that public capability and no longer contains a second
private GUID, Known Folder resolver, fixed-child tuple, or pin-name authority.

This checkpoint does not observe protected members, compose authenticated
membership, contact Qdrant, build or persist a cleanup plan, issue approval, or
execute cleanup.

## Closed Contract

- The shared module exposes exactly the five public symbols selected by the
  decision checkpoint; the external reader retains exactly its prior four
  exports and thirteen errors.
- Binding is operation-free. It validates the Windows ABI, captures the exact
  callable native exports, applies their ABI signatures, and rejects missing,
  non-callable, or unsupported capability before returning a locator.
- A bound locator retains those exact callables even if the source library
  objects are later changed or their attributes are deleted.
- Resolution invokes `SHGetKnownFolderPath` with the canonical ProgramData GUID
  and flags `0`, validates one absolute drive-rooted normalized result, retains
  only detached components, and releases every returned native buffer exactly
  once with the bound `CoTaskMemFree` capability.
- Errors, locations, and locators are immutable, including ordinary assignment
  and deletion. Their representations are redacted and they cannot be copied,
  pickled, or used to recover a full path.
- Ordinary, malformed, cleanup, and control-flow failures remain inside the
  selected three-code, path-free locator taxonomy with bounded closed exception
  graphs and preserved control identity where required.
- The external reader preserves DLL load order, token brackets, held-handle
  traversal, fixed-child and pin semantics, evidence bytes, cleanup precedence,
  and outward phase-specific error mapping.
- Semantic negative-mutant tests reject renamed copies of the GUID structure,
  ProgramData GUID, native calls, fixed directory tuple, and pin name in the
  external reader.

## TDD And Review Hardening

The direct RED first failed because the shared module did not exist. Subsequent
focused RED cases exposed and closed these additional contract gaps before the
checkpoint:

- the original locator retained DLL containers rather than the exact validated
  callables;
- malformed or unknown errors could expose mutable or raw linked state;
- malformed decoded native output had the wrong outward classification;
- the external consumer did not prove complete shared resolve-graph
  translation or defend against renamed duplicate-authority mutants;
- public location and locator slots could be deleted; and
- non-callable fake exports could pass binding and fail only during resolution.

Independent contract and extraction-parity reviewers inspected the final bytes
after every correction. Both returned `PASS` with no remaining finding.

## Fresh Verification

All commands used the explicit `goodq_core` interpreter and fake or synthetic
native surfaces only.

| Gate | Result |
| --- | ---: |
| Direct shared-locator suite | 53 passed |
| Frozen external-reader parity suite | 499 passed |
| Protected-manifest reader suite | 148 passed |
| Adjacent authority gate | 737 passed |
| Exact frozen pre-manifest authority union | 1,422 passed |
| Locator-first expanded authority gate | 1,623 passed |
| Exact four-file Python compilation | passed |
| Documentation authority and semantic drift | passed |
| Banned-token and dependency drift | passed |
| Staged source census | exactly 4 files |
| Staged diff and whitespace checks | passed |
| Contract review | PASS |
| Extraction-parity review | PASS |

One earlier pre-final union run observed the existing synthetic temporary-
filesystem `observation_raced` condition. The unchanged retry passed, and both
later final-byte union witnesses passed. The event was retained as evidence and
was not treated as a product failure or suppressed.

The reviewed committed SHA-256 hashes are:

```text
steps/common/clean_memory_windows_program_data_locator.py
09B9040C0B3BFD4F0FFB70357336E21C4AC8390B843FDACE5A605C31032724C4

tests/unit/test_clean_memory_windows_program_data_locator.py
A2D0F25EE4A22514B5CCD7D4D7A3D6EF6B35BBC1D36064593B6A12443E0BA390

cli/clean_memory_external_pin.py
B0D8695131CFE4B4421717F4D61ECA83E71C4EF6393246D012BA01D496880B03

tests/unit/test_clean_memory_external_pin.py
43013882CA118D9E6B358529899BF43698B403A6710F254F3B7F41500EAF3124
```

## Evidence Boundary

No live ProgramData, production pin, manifest, token, ACL, descriptor,
configured or protected root, service, GoodQ data, Qdrant store, evidence store,
job, MiniAgent, approval, or cleanup target was read or changed.

## No-Repeat Boundary

Do not add a second ProgramData resolver, restore the private external-reader
GUID/native/fixed-child/pin authority, accept a caller path or environment
location, reopen descendants by pathname, serialize a resolved location, or
reopen this four-file seam without contradictory focused evidence.

This checkpoint proves only the shared locator and exact extraction parity. It
does not prove protected-member physical state, pin-chain exclusion,
authenticated composition, or runnable cleanup planning.

## Next Bounded Mission

Run one read-only no-repeat ownership and contract audit of the protected-member
observer and direct pin-chain physical-exclusion boundary. Select the exact
inputs, held-handle lifecycle, alias/collision rules, error taxonomy, and RED
oracles before any observer code is authorized.

Final authenticated composition, Qdrant observation, runnable planning,
approval, and cleanup remain closed.
