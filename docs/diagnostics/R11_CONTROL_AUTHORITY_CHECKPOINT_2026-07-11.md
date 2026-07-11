<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-11 Control Authority Checkpoint

## Invariant

Native MiniAgent execution must use one exact-scope confirmation authority,
must preserve durable generic decision and execution evidence, and must not let
the preflight-only governor or dormant Control Agent capability become an
unapproved execution authority.

## Checkpoint Lineage

- Branch: `codex/r11-control-authority`
- Confirmation checkpoint: `d2e8f72a fix: enforce exact native confirmations`
- Audit checkpoint: `8f0b424d feat: persist MiniAgent tool audit evidence`
- Control-default checkpoint: `2afa9d69 fix: align Control Agent activation authority`
- R-11 status: independently reviewed, verified, and privately checkpointed

## Confirmation Authority

The native path now has one explicit confirmation-required set for the seven
approved mutating operations. Both safe and unrestricted execution require a
locally issued, single-use token bound to the exact operation and complete
argument scope. File deletion additionally retains its break-glass requirement.
Token issuance failures deny execution, invalid or mismatched tokens are
rejected, and confirmation material cannot be reused for another operation or
scope.

The atomic token-store persistence established by the completed R-02 checkpoint
was re-audited and preserved. R-11 did not replace or duplicate that authority.
The exact-scope UCF promotion and lifecycle transaction paths from R-02/R-03
were also left intact.

## Durable Generic Audit Evidence

MiniAgent now appends locked JSONL records for every nonempty public validation
decision and every native handler outcome. The default is the ignored local
`.goodq/logs/tool-audit.jsonl` path, with a dedicated environment override for
isolated tests and operators.

Audit records recursively redact secret-bearing fields and sanitize paths; raw
prompts and confirmation tokens are not persisted. A decision-audit failure is
fail-closed and revokes any token issued by that decision. A post-execution
audit failure remains visible without falsifying the already-observed handler
result or side effect. Blocked and error outcomes remain truthful nonmutating
records rather than being relabeled as successful execution.

## Control Agent and Governor Authority

The Control Agent is dormant by default. Activation requires an exact explicit
CLI/config boolean or environment value, and configuration mutation requires
activation, auto-healing, and non-dry-run operation together. Cached client
state and command-framework option wrappers cannot bypass those gates. Watchdog
use remains injection-only.

The machine-local `goodq_governor` MCP was probed live and remains
preflight-only. It exposes exactly `validate_safe_profile` and `preflight_task`;
it has no execution tool. No governor runtime code was changed in this seam.

## Verification Evidence

Fresh committed-HEAD evidence from the isolated worktree:

- 229 focused MiniAgent confirmation/audit, staged-ingestion mock,
  governance-validator, UCF transition/promotion, Control Agent activation,
  disabled-default, self-healing-truth, and retry-ceiling tests passed.
- The staged-ingestion suite ran with its explicit mock harness; no live ingest,
  promotion, reconciliation, or deletion was performed.
- Python compilation, documentation authority, documentation drift,
  banned-token, dependency-drift, and staged-diff checks passed.
- Documentation drift scanned 293 active files with zero active violations.
- Multiple independent reviews found and then verified repairs for a mock-only
  assertion, orphan confirmation material, blocked-result truth, cached-client
  activation bypass, missing dry-run mutation gating, and generated-index drift.
- Final independent review returned APPROVED for all three implementation seams.

## Boundary Accounting

One mock-harness omission during verification created a zero-byte E2E fixture in
the frozen mixed checkout. The artifact was proven current-run, empty, and
test-owned, then removed alone. The mixed checkout returned to its original 96
expanded status entries. The public checkout remained at zero working entries.

No live memory, Qdrant data, service binding, network rule, ingestion state,
identity state, or public checkout was mutated by R-11.

## Resume

Continue from the single bounded mission in `PROJECT.md` and the ordered master
register in `docs/releases/ROADMAP.md`. R-05 owns API and Command Center route
authority convergence. Do not reopen R-11 unless fresh focused evidence
contradicts this checkpoint.
