<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-14 -->

# Active bounded mission

Roadmap item: R-07 — audit projection-neutral Windows security mechanics.

## Outcome

Run only a decision-only, read-only no-repeat audit of the Windows token and
security mechanics required by the selected protected-manifest policy. Trace
the completed private implementation in `cli/clean_memory_external_pin.py`, its
tests, the shared held-handle backend, and official platform contracts. Decide
which mechanics are genuinely projection-neutral, which remain pin-specific,
and the smallest isolated extraction/adaptation seam that preserves the
completed external-pin reader exactly.

Do not implement mechanics or the protected-manifest reader during this
mission.

## Completed work — do not repeat

- Configuration, filesystem observation, structural membership, held-handle
  traversal, bounded reads, and external-pin reader authority are checkpointed.
- `41e56c74` checkpoints the pure canonical protected-manifest validator and
  membership delegation.
- `25ae5b64` selects the exact manifest security policy: filtered descriptor,
  bounded mutation-denial checking, actual-kernel positive access, frozen v1
  pin identity digest, and explicit publication-provenance limits.
- `6b40d8e8` checkpoints exact opt-in `security_read_label` transport with
  request mask `0x17`, native Windows evidence, 644 focused regressions, and two
  independent `READY` reviews.
- Existing `security_read` remains exact owner/group/DACL transport (`0x7`).
- Candidate-plan authority and storage are completed injected cores and are not
  part of this mechanics audit.

## Governing evidence

- `docs/diagnostics/R07_PROTECTED_MANIFEST_SECURITY_POLICY_DECISION_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_LABEL_SECURITY_TRANSPORT_CHECKPOINT_2026-07-14.md`;
- `docs/diagnostics/R07_WINDOWS_EXTERNAL_PIN_READER_CHECKPOINT_2026-07-14.md`;
- `cli/clean_memory_external_pin.py`;
- `tests/unit/test_clean_memory_external_pin.py`;
- `steps/common/windows_held_handle.py`;
- `tests/unit/test_windows_held_handle.py`; and
- `docs/releases/ROADMAP.md`.

## Governing invariant

The audit may share mechanics, never authority. The external-pin reader's
private policy, five-object grammar, v1 identity projection/digest, evidence,
errors, failure order, and no-argument API remain exact. Manifest policy belongs
only to the future manifest reader. A shared layer may expose bounded native
mechanics but may not know candidate roles, fixed names, trusted SIDs, accepted
token policy, DACL sequences, access outcomes, or consumer error schemas.

## Exact audit seam

The audit must decide, with code traces and parity oracles:

- exact ownership and ABI for token opening, duplication, information queries,
  snapshots, and equality;
- how the frozen external-pin v1 reader-identity projection remains unchanged
  while `TokenMandatoryPolicy` is separately observed and rechecked for the
  manifest reader;
- which self-relative descriptor, ACL, ACE, SID, and mandatory-label parsing is
  projection-neutral and bounded;
- how one immutable filtered descriptor buffer is shared by parsing and bounded
  denial checking;
- exact file `GENERIC_MAPPING`, raw-mask preservation, `MapGenericMask`, and
  zero-privilege `AccessCheck` mechanics;
- malformed-versus-unsupported internal error ownership and consumer-specific
  translation;
- whether extraction or a narrow private adaptation produces the smaller proof
  obligation; and
- exact files, public/private API, RED parity matrix, compilation gates, and
  independent review required for the next implementation checkpoint.

The decision must preserve the rule that `AccessCheck` is only a filtered,
bounded mutation-denial oracle. Actual kernel opens and same-handle reads remain
the positive-access proof.

## Boundaries

- Do not inspect or mutate a live token, ACL, configured/protected root,
  manifest, pin, service, GoodQ data, Qdrant, evidence store, job, MiniAgent, or
  cleanup target.
- Do not query a full SACL or request `ACCESS_SYSTEM_SECURITY`.
- Do not copy private external-pin policy into a shared module or manifest
  reader.
- Do not modify the external-pin reader, held-handle backend, validator,
  membership, configuration, candidate plan, or any runtime code/test.
- Do not add enrollment, publication, rotation, recovery, planning, approval,
  cleanup, dependency, service, firewall, environment, or runtime changes.

## Completion gate

Produce one evidence-backed mechanics ownership/parity decision with an exact
smallest next seam. It must freeze import/public boundaries, native ABI,
consumer ownership, failure translation, RED parity oracles, and no-repeat
constraints; preserve every completed external-pin and held-handle behavior;
and receive independent current-byte review. Checkpoint that decision before
any mechanics extraction. The protected-manifest reader remains closed.
