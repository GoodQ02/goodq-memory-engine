<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-11-F1 MiniAgent Handler Outcome Truth Checkpoint

## Invariant

When a native MiniAgent handler explicitly reports `status=error`, the outward
envelope, return code, side-effect report, and durable execution audit must all
report the same failure. Caller-facing failure text remains generic. Existing
soft `blocked` semantics are not changed by this follow-up.

## Checkpoint Lineage

- Branch: `codex/r11-f1-handler-truth`
- Implementation: `9661d8db fix: report MiniAgent handler errors truthfully`
- Parent authority: verified R-11 plus the first governed R-05 staging
  checkpoint

## Repair

The generic native execution wrapper now recognizes exact handler
`status=error` while its own wrapper status is still success. It converts that
outcome to outward error and return code one. The controlled handler reason is
used as the error code; a reasonless handler receives
`handler_reported_error`. The caller-facing message is always the fixed generic
text `Tool handler reported an error.`

The original handler output remains available as structured output, the
side-effect report remains nonmutating, and the durable execution audit records
the same status, return code, error code, handler status, and handler reason.
The existing `blocked` return-code-zero behavior remains covered and unchanged.

The mission-authority lint now recognizes registered roadmap sub-items such as
this follow-up as distinct IDs. A bounded mission can therefore point at an
open sub-item without being mistaken for its already-verified parent.

## Verification Evidence

Fresh evidence from the isolated worktree:

- 204 MiniAgent, durable-audit, governed-ingest, isolation, and documentation
  authority tests passed.
- The two new handler-error tests cover controlled-reason and reasonless
  outcomes. Existing blocked-handler coverage stayed green.
- Full MiniAgent client coverage and the complete governed-staging regression
  set remained green.
- Python compilation, mission/documentation authority, documentation drift,
  banned-token, dependency-drift, and staged-diff gates passed.
- Documentation drift scanned 295 active files with zero active violations.
- Independent specification review returned `APPROVED`.
- Independent security review returned `APPROVED`, including an isolated
  mutating-handler probe confirming `mutated=false`.

## Boundary Accounting

This follow-up changed no handler, token, confirmation, route, Control Agent,
governor, runtime service, data store, or network binding. Tests used isolated
state. The frozen mixed checkout and public checkout were not modified.

## Resume

Return to R-05 from this checkpointed descendant. The next bounded seam is the
common route-effect registry and remote-mutation denial. Do not reopen R-11-F1
unless fresh focused evidence contradicts this checkpoint.
