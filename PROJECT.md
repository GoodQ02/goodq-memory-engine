<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — implement the audited read-only Windows external-pin
reader without enrollment or execution authority.

## Outcome

Add the one no-argument Windows reader selected by the completed boundary audit.
It must resolve the actual ProgramData Known Folder, prove the effective reader
identity and protected owner/DACL policy, walk the fixed source by the shared
held-handle backend, read the exact 65-byte pin payload, perform every final
recheck, and return only the canonical path-free evidence contract.

The implementation is hermetic-first. No test or development step may inspect,
create, enroll, publish, rotate, recover, or delete a live pin or trust root.

## Governing evidence

- held-handle extraction checkpoint `0f567557`;
- `docs/diagnostics/R07_WINDOWS_HELD_HANDLE_EXTRACTION_CHECKPOINT_2026-07-13.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_BOUNDARY_AUDIT_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`;
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`;
- `docs/releases/ROADMAP.md`.

## Governing invariant

The external pin is the independent authorization source for exact manifest
bytes. A reader result exists only when one production-owned operation proves
the fixed source, effective reader, physical chain, security policy, exact
payload, and all final rechecks without pathname fallback. Configuration and
protected-membership projection remain routing and structure only.

## Exact implementation scope

- Add `cli/clean_memory_external_pin.py` with exactly the audited public API:
  `EXTERNAL_PIN_EVIDENCE_SCHEMA`, `ExternalPinReaderError`,
  `ExternalPinEvidence`, and `read_external_pin`.
- Add focused hermetic RED/GREEN coverage in
  `tests/unit/test_clean_memory_external_pin.py`.
- Reuse only the public `steps.common.windows_held_handle` boundary for held
  traversal and physical snapshots; do not copy or import its private ABI.
- Add only the reader-specific Known Folder, token, security-descriptor,
  authorization, bounded-read, canonical evidence, and recheck capabilities
  fixed by the audit.
- Preserve exact path-free errors and detached canonical evidence. Raw paths,
  SIDs beyond approved evidence, OS text, and native details remain outside
  serialized output.

## Boundaries

- Touch only the reader source/test pair plus checkpoint documentation and
  generated indexes.
- Do not modify the held-handle backend, filesystem observer, configuration,
  protected membership, candidate plan, job, approval, MiniAgent, or cleanup
  contracts without contradictory focused evidence.
- Do not add enrollment, publication, rotation, recovery, authenticated
  membership composition, protected-member observation, Qdrant observation,
  runnable planning, or execution behavior.
- Do not read or alter live ProgramData, a live pin, tokens, ACLs, configured
  roots, services, GoodQ data, Qdrant, evidence stores, or cleanup targets.
- POSIX remains `unsupported_platform` for this reader version.

## Completion gate

The exact public API, import purity, Known Folder flags and normalization,
effective-token precedence and acceptance matrix, owner/DACL/anchor policy,
AccessCheck authorization, fixed chain traversal, exact 65-byte payload,
canonical evidence/digest, full recheck order, finite errors, malformed native
buffer handling, and no-live-surface test boundary pass. Then run the approved
adjacent authority union, compilation, documentation/index/drift, banned-token,
dependency, staged-diff, and three independent current-byte reviews before a
private checkpoint.
