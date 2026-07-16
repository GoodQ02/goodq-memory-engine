<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# R-07 Protected-Membership Projection Checkpoint

## Outcome

The selected non-authoritative protected-membership projection is implemented
and privately checkpointed:

```text
81aafce1 feat: add protected membership projection
```

The new import-pure seam accepts only the exact completed
`ResolvedPlanConfiguration` and already-supplied canonical manifest bytes. It
validates the selected eight-role manifest, converts the ten configured roles
using the fixed positional compatibility table, and produces the canonical
18-role `goodq.clean-memory-protected-membership.v1` envelope and digest.

This checkpoint proves structural and digest consistency only. It does not
locate, read, authenticate, enroll, publish, or rotate a manifest or external
pin, and it grants no candidate-planning or cleanup authority.

## Exact Boundary

The public surface is exactly:

- `PROTECTED_MEMBERSHIP_SCHEMA`;
- `ProtectedMembershipProjection`; and
- `project_protected_membership(configuration, *, manifest_bytes)`.

The implementation:

- requires exact runtime types for configuration and manifest bytes;
- validates the unchanged canonical configuration bytes and SHA-256 while
  checking only membership-consumed v1 fields;
- bounds manifest bytes before JSON parsing;
- rejects duplicate keys, non-finite values, noncanonical UTF-8/JSON, Unicode
  control characters, and recursive parser exhaustion;
- requires the exact eight manifest roles, ordered explicit member IDs,
  1–64 members per role, no more than 512 manifest members, and paths no longer
  than 4,096 UTF-8 bytes;
- applies reject-on-change Windows/POSIX lexical path validation, including
  unresolved parameter syntax and Windows device aliases;
- rejects exact duplicates, Windows comparison aliases, configured/manifest
  aliases, and overlap with cleanup or evidence scope while preserving
  intentional protected containment;
- assigns `configured_00` and `configured_01` only by the immutable configured
  path-list positions selected by the semantics decision;
- returns a frozen path-free-repr object with a detached projection; and
- rechecks the configuration payload and digest before return.

It performs no configuration load, filesystem or environment read, network or
process call, persistence, service/Qdrant access, plan construction, job/token
work, MiniAgent call, or cleanup.

## Mutation-Sensitive Evidence

The focused oracle was developed through witnessed RED failures for:

- the missing module, then the wrong public API and signature;
- the unimplemented valid 18-role projection;
- forged control-root topology and reordered watchdog members;
- oversized input being checked after configuration JSON parsing;
- Windows superscript DOS-device aliases;
- deeply nested JSON leaking `RecursionError`;
- Unicode C1 controls; and
- braced POSIX parameter-expansion variants.

Independent review then found and closed three completion-oracle gaps. The final
tests use semantically valid noncanonical/duplicate-key manifests, a poisoned
and audited isolated import/invocation, and a non-collapsing exact AST import
census with dynamic-import rejection.

Every test used synthetic configuration projections and manifest bytes. No
configured or live root, manifest, pin, ACL, service, data, Qdrant store,
evidence store, job, token, MiniAgent, or cleanup authority was read or changed.

## Fresh Verification

The final staged implementation bytes passed with the explicit `goodq_core`
interpreter:

| Gate | Result |
|---|---:|
| Focused protected-membership authority | 98 passed |
| Configuration/candidate/filesystem/membership authority union | 331 passed |
| Python compilation | passed |
| Staged file census | exactly 2 implementation files |
| Staged diff check | passed |
| Independent configuration review | CLEAN |
| Independent security/contract review | CLEAN |
| Independent test-oracle review | CLEAN |

The first union attempt encountered one inherited temporary Windows filesystem
observer `observation_raced` result. Its exact native-trace witness passed on
immediate isolated retry, and a fresh full 331-test union then passed. No source
change was made for that unrelated transient witness.

The three final reviewers independently read identical bytes:

```text
cli/clean_memory_protected_membership.py
7068E37AEE64AC204DC30F8B6B1931AD6316A11D443966DD195F187F33389B9C

tests/unit/test_clean_memory_protected_membership.py
3D5ADDD1971C0F320A8E7E2B3BCF112E4E51F139A6A44E88D0343FBF3C962CD6
```

Documentation authority, generated-index, semantic-drift, banned-token,
dependency-drift, compile, and final diff gates are rerun in the documentation
checkpoint that records this implementation.

## No-Repeat Boundary

Do not recreate or reopen without contradictory focused evidence:

- the manifest schema, role order, member limits, configured positional table,
  lexical rules, or projection/digest envelope selected by the semantics
  decision;
- the import-pure structural membership projection;
- configuration-v1 or filesystem-observer internals merely to share private
  validation helpers; or
- manifest/pin authentication inside this non-authoritative type.

## Next Bounded Mission

Run one read-only Windows external-pin boundary audit before any reader,
enrollment, publication, or authenticated-selection implementation. Reconcile
the selected semantics against existing held-handle/no-follow Windows
capabilities, identify the smallest public extraction seam if reuse is viable,
and select exact path-free reader evidence and failure codes. Do not inspect or
mutate the live ProgramData trust-root location, create a pin, change an ACL, or
claim authenticated membership during that audit.
