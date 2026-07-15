<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — audit the composition-owned ProgramData locator and final
recheck boundary.

## Outcome

Perform one read-only no-repeat audit before any locator or composition source
is authorized. Select one exact contract that obtains the fixed pin-chain
location from the real Windows Known Folder authority, retains it only
in-process, brackets it with direct reader evidence, and enables later lexical
and physical exclusion without widening either completed reader.

The audit must decide whether ownership belongs in a shared extraction-parity
surface or a composition-owned resolver. It must not implement either option.

## Completed work — do not repeat

- Configuration projection, external-pin reading, canonical manifest
  validation, protected-membership projection, held-handle traversal and reads,
  label-aware descriptor transport, Windows security mechanics, shared reader
  identity, and the protected-manifest security policy are checkpointed.
- `66ee4f47` checkpoints the authenticated protected-manifest reader and its
  exhaustive two-file regression suite.
- Fresh verification passed 148 focused reader tests, the zero-drop 1,422-test
  pre-reader authority union, and the 1,570-test combined authority gate.
- Three independent current-byte reviews found no unresolved critical, major,
  or minor issue.
- Checkpoint evidence is recorded in
  `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`.
- The earlier composition audit already proved that target filesystem evidence
  is cleanup-plan pre-state, not membership-authentication input.

## Governing invariant

Ambient environment, configuration, current directory, caller input, or a
second guessed path cannot locate the ProgramData pin chain. The later
production edge must invoke the actual fixed Known Folder authority, preserve
the canonical result only in-process, and compare it with direct reader outputs
without logging or serializing it.

The pin reader and protected-manifest reader remain closed four-export
authorities. The audit may select no private-symbol import, caller-supplied path,
or duplicate physical reader.

## Audit questions

Select and document exactly:

1. whether ownership is shared extraction parity or a composition-owned
   resolver;
2. the minimal import-pure public or private surface, if any;
3. the exact `FOLDERID_ProgramData` acquisition and fixed-child append sequence;
4. path normalization, lexical separation, retention, and final recheck rules;
5. how direct pin and manifest evidence bracket locator use;
6. finite path-free failure precedence and race behavior;
7. the smallest later source/test file census; and
8. the focused RED and non-regression gates required before implementation.

## Governing evidence

- `docs/diagnostics/R07_AUTHENTICATED_PROTECTED_MEMBERSHIP_COMPOSITION_AUDIT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_MANIFEST_READER_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `cli/clean_memory_external_pin.py`;
- `cli/clean_memory_protected_manifest.py`;
- their focused tests; and
- `docs/releases/ROADMAP.md`.

## Boundaries

- Work only in `.worktrees/r05-api-authority` on
  `codex/r05-api-authority`.
- Read repository source, tests, contracts, and checkpoint evidence only.
- Do not create locator, protected-observer, composition, Qdrant, planning,
  approval, or cleanup code during this audit.
- Do not reopen or modify either completed physical reader or its tests.
- Do not inspect or mutate live ProgramData, a token, ACL, descriptor,
  configured or protected root, manifest, pin, service, GoodQ data, Qdrant
  store, evidence store, job, MiniAgent, approval, or cleanup target.
- Do not change environment, service, firewall, dependency, enrollment,
  publication, rotation, recovery, or runtime state.

## Decision gate

Before any locator implementation is authorized:

1. bounded independent read-only traces reconcile ownership, lifecycle/error
   precedence, and parity with the actual external-pin Known Folder path;
2. one decision document fixes the exact contract, dependency boundary, file
   census, RED matrix, and verification gate;
3. no private reader helper, duplicate locator, or caller path becomes
   authority;
4. every unresolved field or failure remains explicitly closed; and
5. documentation authority, semantic-drift, banned-token, dependency, index,
   and committed-diff gates pass in a separate checkpoint.
