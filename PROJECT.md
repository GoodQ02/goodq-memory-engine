<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-13 -->

# Active bounded mission

Roadmap item: R-07 — audit the Windows external-pin reader boundary.

## Outcome

Perform one read-only no-repeat audit that reconciles the selected external-pin
semantics with existing Windows held-handle/no-follow capabilities. Determine
the smallest public extraction seam, exact path-free reader evidence, and exact
failure taxonomy needed before any reader, enrollment, publication, or
authenticated-selection implementation is proposed.

This mission selects evidence and implementation boundaries only. It does not
read or create a live pin, mutate ProgramData, change an ACL, or authenticate
protected membership.

## Governing evidence

- candidate-plan checkpoint `c870a1cb`
- configuration projection checkpoint `a12ceb18`
- filesystem observer checkpoint `e8961889`
- protected-boundary authority audit checkpoint `f01e03a7`
- duplicate canonical-envelope guard checkpoint `4230a910`
- source/trust decision checkpoints `8bfa5d27` and `69f4a91e`
- semantics checkpoint `9328e89e`
- membership-projection checkpoint `81aafce1`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SOURCE_DECISION_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_AUTHORITY_SEMANTICS_DECISION_2026-07-13.md`
- `docs/diagnostics/R07_PROTECTED_MEMBERSHIP_PROJECTION_CHECKPOINT_2026-07-13.md`
- `docs/releases/ROADMAP.md`

## Governing invariant

The external pin is the independent authorization source for exact manifest
bytes. Configuration and the completed membership projection remain routing and
structural evidence only. A future production edge may claim authenticated
membership only after it directly owns approved pin and manifest readers and
completes every selected physical/security recheck.

## Exact audit scope

- Reconcile the Windows pin locator, token, volume/filesystem, DACL/owner,
  held-handle, open-by-ID, stable-parent, no-replace, and 65-byte payload
  requirements already selected by the semantics decision.
- Trace existing Windows filesystem-observer capability as a behavioral oracle;
  do not import, copy, or modify its private helpers.
- Identify whether a small public shared backend extraction is coherent, which
  completed tests prove parity, and which reader-specific checks remain new.
- Select one path-free pin-reader evidence envelope and a closed failure-code
  set sufficient for later authenticated composition.
- Preserve POSIX as unsupported in v1 unless a separate capability audit is
  explicitly approved.

## Boundaries

- Read-only audit only. No source implementation, dependency change, service
  action, configuration load, runtime command, or host mutation.
- Do not inspect, create, enroll, publish, rotate, recover, or delete the live
  trust-root location or pin.
- Do not change ProgramData, filesystem permissions, ownership, ACLs, user or
  process tokens, services, manifests, configured roots, Qdrant, or GoodQ data.
- Do not reopen the completed configuration, membership projection, candidate
  plan, filesystem observer, action-job, MiniAgent, or approval contracts.
- Do not design manifest authoring, protected-member observation, Qdrant
  observation, runnable planning, or execution inside this audit.

## Completion gate

Three bounded read-only traces agree on existing capability, missing capability,
public/private ownership, exact reader evidence, exact failure taxonomy, and the
smallest coherent next implementation seam. A dated diagnostic checkpoint,
roadmap entry, regenerated indexes, documentation authority/drift, banned-token,
dependency, diff, and independent current-byte review gates pass. No live trust
root, member, service, or data surface is touched.
