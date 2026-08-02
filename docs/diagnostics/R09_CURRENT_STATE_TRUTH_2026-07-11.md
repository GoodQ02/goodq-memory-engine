<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-09 Current-State Truth Checkpoint

## Invariant

Active human, JSON, and RAG state must be deterministic projections of one
checked, redacted evidence snapshot. A projection must not infer lifecycle
completion, service health, epoch authority, or future work beyond that
evidence.

## Checkpoint Lineage

- Branch: `codex/r09-current-state-truth`
- Base: `d4c5b686`
- Builder checkpoints: `1eba75f9`, `2899ac0e`, `8b549a1e`, `e2b8f23e`
- Final evidence source commit: `e2b8f23e`
- Final evidence source state: clean

## Included Surface

- fail-closed current-state capture from an explicit resolved configuration and
  exact epoch root
- immutable SQLite census with non-empty WAL and rollback-journal refusal
- exact loopback Qdrant inventory, observed vector dimensions, green status,
  and identity-only sampling with payloads and vectors disabled
- loopback-only, no-proxy, no-redirect runtime probes
- canonical evidence hashing and validation before render or verification
- locked three-file projection publication with path-collision rejection and
  rollback after a partial replacement failure
- deterministic human, JSON, and RAG projections from one evidence file
- dynamic Hermes verification prompt with a service-free structural contract
  gate

## Evidence Snapshot

- Private runtime evidence and corpus-specific measurements are retained in
  private development. They are deliberately omitted from the public mirror.

Service observations are deliberately narrow; public releases should use their
own local verification receipts rather than inheriting another operator's
runtime evidence.
The configured non-loopback vLLM endpoint was withheld and not contacted.
GoodQ Ollama was reachable with no model reported loaded. WSL was not queried.

## Projection Truth

The following active surfaces exactly match the evidence snapshot:

- `docs/agent/CURRENT_STATE.md`
- `docs/agent/current_state.json`
- `docs/GOODQ_RAG_CONTEXT_PACK.md`

The projections contain no temporary branch name, repair-task ID, future-work
section, active June epoch, absolute machine path, user name, secret-shaped
value, remote endpoint, raw payload, or vector.

## Hermes Adapter Boundary

The GOOD-CUBE-local bridge under
`%SYSTEMDRIVE%\Tools\goodq-hermes-rag` was updated without changing its MCP
server implementation:

- the minimal prompt discovers epoch and collection authority from live GoodQ
  tools rather than hard-coding a dated collection
- `Test-GoodQHermesRag.ps1 -PromptContractOnly` validates the six-tool contract
  without Python, network, model, or service calls
- the full read-only bridge self-test passed
- `hermes mcp test goodq` connected and discovered all nine bridge tools

The model-level prompt was intentionally not run against a temporary worktree.
Until this checkpoint is integrated into the live private checkout, a dynamic
authority comparison should fail rather than accept the older live context
pack.

## Verification Evidence

- Focused builder suite: **18 passed**.
- Evidence hash was independently recomputed and matched.
- Builder projection verification passed after every final rotation.
- Projection parity for evidence ID, timestamp, epoch, lifecycle inputs,
  Qdrant names, counts, dimensions, and status passed.
- Endpoint/path/credential/secret/task/stale-epoch scans passed.
- PowerShell prompt-contract parsing and service-free validation passed.
- Three independent final reviews returned READY after all blockers were
  corrected.
- `git diff --check` passed apart from normal Windows line-ending notices.

## Safety Boundaries

- No ingestion, promotion, re-ingestion, Qdrant mutation, API start, WSL start,
  model chat, or durable agent-memory write was performed.
- The mixed main checkout remained frozen at **96** expanded entries.
- The public checkout remained clean.
- The evidence contains commit-based provenance only; temporary branch names
  are not active state.

## Resume

Continue with R-13 in a new isolated worktree. Treat this generated evidence
chain as the current-state authority and do not reopen R-09 unless a fresh
capture proves drift.
