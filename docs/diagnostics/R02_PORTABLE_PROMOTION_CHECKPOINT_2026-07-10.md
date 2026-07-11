<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-02 Portable Promotion Checkpoint Evidence

## Invariant

A promotion transaction must durably queue its exact-scope Qdrant projection.
The obligation may clear only after the projected payload is read back and
verified. Post-commit delivery failure must be nonzero, durable, and recoverable
through a fresh human-gated token without repeating materialization.

## Checkpoint Lineage

- Branch: `codex/r01-r02-checkpoints`
- Base: `19274ca7`
- R-01 prerequisite: `c0e9099f fix: align scoped UCF promotion contract`
- R-02 status: independently verified and ready for a seam-only checkpoint

## Included R-02 Surface

- `cli/ucf_promotion.py` and focused CLI tests
- MiniAgent promotion outbox and exact-scope reconciliation
- contract registration for pending delivery and reconciliation
- fresh-agent-home script packaging
- pre-mutation exact-video and exact-epoch Qdrant verification
- lifecycle-source allowlisting and terminal-state preservation
- backward-compatible epoch proof for canonical audio collections
- four retired promotion/lifecycle runner deletions
- clean-slate guard and CLI reference updates
- retrieval bridge and stress coverage

## Explicit Exclusions

- no R-03 transition insertion implementation
- no R-03 promotion transition frame evidence
- no R-03 promotion transition rollback tests
- no unrelated identity, UI, documentation reorganization, or runtime work

## Checkpoint Evidence

Fresh isolated verification completed on 2026-07-11 from a brand-new temporary
`GOODQ_MINI_AGENT_HOME`. The temporary home was removed in the command's
`finally` block.

- 15 promotion CLI tests passed
- 81 MiniAgent tests passed
- 7 governance-validator tests passed
- 19 retrieval-bridge tests passed
- 7 retrieval stress tests passed
- total: 129 passed in 52.78 seconds
- Python compile passed for the seven changed Python files
- the MiniAgent contract and current-state JSON parsed successfully
- the seam-only added-line scan found zero fixed drive roots and zero secret
  prefixes outside test fixtures
- all four retired runners are absent
- no R-03 transition implementation, frame-evidence tests, or rollback tests
  are present
- the banned-token lint passed
- `git diff --check` passed

The first isolated collection contained 114 tests because the two R-03-only
transition tests were correctly excluded. Three bounded read-only checkpoint
reviews then found R-02 defects before checkpointing. Focused regression tests
failed for each defect before the minimal correction was applied:

- materialization selected promoted frames by video but not epoch
- numeric Qdrant IDs were normalized as strings rather than integers
- an unverified or empty scope readback could clear the delivery obligation
- a pending promotion obligation could survive supersession and resurrect
  superseded evidence
- suffix-based collection discovery and video-only filters could cross epoch
  boundaries
- terminal, lifecycle-anonymous, conflicting-epoch, or wrong-scope points
  could be mutated before their payload scope was validated
- reject and supersede exact-ID paths did not pass their required video/epoch
  scope into the pre-mutation proof helper
- a stale local delivery result could report success after the durable outbox
  had been cancelled concurrently
- canonical audio epoch collections were incorrectly required to carry an
  `epoch_id` payload even though current and historical CLAP points encode the
  epoch in the exact collection name

The final suite contains 129 R-02 tests without importing any R-03 transition
insertion or rollback implementation. Exact-ID and scope sweeps now pre-read
the requested payloads, reject invalid lifecycle or scope metadata before
mutation, preserve terminal states through a source-state allowlist, require
post-write proof, and derive success from durable outbox state. Canonical
`goodq_{modality}_{epoch_id}` collection membership may supply epoch proof for
legacy audio payloads; noncanonical/global collections still require an exact
payload `epoch_id`. Configured epoch collections belonging to another epoch are
not swept.

Atomic lifecycle transition insertion and the remaining delivery-versus-
supersession concurrency transaction belong to R-03 and remain explicitly
excluded from this checkpoint. R-02 covers sequential supersession
cancellation and refuses to report a cancelled durable obligation as complete.

The ignored validator reports were snapshotted before the final suite and
restored afterward so checkpoint verification did not further alter that known
adjacent report-isolation surface.

Repository-wide drive-root and documentation-drift scanners still report
unchanged baseline findings in files outside the R-02 diff. They are not
silently waived: they remain owned by the configuration and documentation
authority repair seams and were not imported into this checkpoint.

## Resume

Inspect the seam-only staged diff, create the private R-02 checkpoint, then add
the resulting commit hash to the current-state handoff surfaces before starting
R-03 isolation.
