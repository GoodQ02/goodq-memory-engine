<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# R-07 Protected-Manifest Reader Checkpoint

## Outcome

The selected authenticated Windows protected-manifest reader is implemented and
privately checkpointed:

```text
66ee4f47 Implement authenticated protected manifest reader
```

`read_protected_manifest()` accepts only exact authenticated configuration and
direct external-pin evidence. It traverses the complete fixed route through
owned no-follow handles, enforces the selected reader and descriptor policy,
reads one bounded fixed-child manifest, compares its digest with the direct pin
before parsing, validates those identical bytes once through the shared
canonical validator, performs final race fences, completes cleanup, and returns
immutable path-free evidence.

This checkpoint implements only that physical reader. It does not locate or
recheck ProgramData for later composition, observe protected members, compose
authenticated membership, contact Qdrant, create a cleanup plan, issue
approval, or execute cleanup.

## Closed Contract

- The module has the exact four-export public surface and keyword-only direct
  external-evidence input selected by the decision checkpoint.
- Import remains capability-pure. Native security binding and backend creation
  occur only after exact input authentication and the Windows platform gate.
- The anchor, complete variable route, candidate directory, and fixed manifest
  child are selected and retained by physical identity through the shared
  held-handle backend. No descendant is reopened by pathname.
- One mandatory-policy token snapshot is retained and validated through the
  shared reader-identity authority. Candidate and manifest security descriptors,
  label policy, positive access, and ordered mutation denials are checked on the
  held objects.
- The exact complete manifest bytes are read once with the shared size-plus-one
  primitive. Pin mismatch precedes parser invocation; the shared canonical
  validator receives the identical bytes object exactly once.
- Returned evidence binds the direct configuration and pin-evidence digests,
  complete physical route, manifest identity and digest, selected security
  policy digest, and repr-hidden retained bytes.
- The public failure surface is the selected sixteen path-free errors. Raw
  paths, SIDs, descriptors, Win32 details, handles, and manifest content cannot
  escape through values, representations, or linked exception graphs.
- Named process-control exceptions preserve exact identity and traceback after
  complete cleanup, while every linked node is sanitized. Unknown
  `BaseException` subclasses fail closed as reader errors.

## TDD And Oracle Hardening

Focused RED first proved the module and contract were absent. GREEN remained
inside the exact two-file seam while independent review found and closed these
additional lifecycle and oracle gaps:

- held-handle errors during final acceptance now map to `observation_raced`;
- zero physical volume or file identities are rejected in direct and live
  evidence;
- operation control flow remains primary over later cleanup or sanitizer
  control flow;
- an unopposed named control raised during sanitization is preserved rather than
  swallowed;
- control-flow cause/context links are sanitized at configuration, pin, startup,
  operation, and cleanup boundaries;
- unknown non-`Exception` failures cannot escape the closed public taxonomy;
- cleanup sanitization failure cannot replace an already selected control;
- saturated cleanup graphs retain the final observed failure; and
- preflight/startup public failures contain only closed reader-error graphs.

Three independent reviewers inspected the same final source and test hashes for
contract parity, lifecycle/control precedence, and privacy/closed-error
behavior. All returned no critical, major, or minor finding.

## Fresh Verification

All commands used the explicit `goodq_core` interpreter and fake or synthetic
native surfaces only. The reader suite ran first as required by the decision
contract.

| Gate | Result |
| --- | ---: |
| Focused protected-manifest reader suite | 148 passed |
| Frozen pre-reader authority union | 1,422 passed |
| Reader-first combined authority gate | 1,570 passed |
| Exact two-file Python compilation | passed |
| Documentation authority and semantic drift | passed |
| Banned-token and dependency drift | passed |
| Staged source census | exactly 2 files |
| Staged diff and whitespace checks | passed |
| Contract/specification review | CLEAN |
| Lifecycle/control-precedence review | CLEAN |
| Privacy/closed-error review | CLEAN |

The reviewed committed SHA-256 hashes are:

```text
cli/clean_memory_protected_manifest.py
4662CC5E49E987B8FE46282AF36057A6E0A83AC7B6E944D9CF60A6F08D5BB7FC

tests/unit/test_clean_memory_protected_manifest.py
31C368D0BBBE3BF36C2A2983E78BCC758AA793B26E7294312E0B0B807915CCC1
```

## Evidence Boundary

No live token, ACL, descriptor, configured or protected root, manifest, pin,
service, GoodQ data, Qdrant store, evidence store, job, MiniAgent, approval, or
cleanup target was read or changed.

## No-Repeat Boundary

Do not add a second protected-manifest reader, duplicate canonical parsing or
reader-identity policy, reopen descendants by path, move GoodQ policy into the
projection-neutral backend, expose retained bytes through a display surface, or
reopen this two-file seam without contradictory focused evidence.

The synthetic checkpoint is not the separate native `0xb014` enrollment or
candidate-store compatibility witness. It authorizes no live authority read.

## Next Bounded Mission

R-07 remains `IN_PROGRESS`. Perform one read-only no-repeat boundary audit of
the composition-owned ProgramData locator and final recheck contract. Decide
whether the fixed Known Folder locator belongs in a shared extraction-parity
surface or a composition-owned resolver before any locator code is authorized.

Protected-member observation, authenticated composition, Qdrant observation,
runnable planning, approval, and cleanup execution remain closed.
