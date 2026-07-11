<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-06 Progressive Ingestion Checkpoint Evidence

## Invariant

Progressive recovery state must describe actual persistence, not loop progress.
Each current window records exactly five targets as `committed`,
`not_applicable`, or `failed`; resume and final cleanup must re-probe that
evidence before skipping work or deleting the checkpoint.

## Checkpoint Lineage

- Branch: `codex/r06-progressive-checkpoint`
- R-04 evidence base: `c6c2e475`
- Reopening record: `e728972b docs: reopen R-06 cleanup gate`
- R-06 code checkpoint: `ffc2b841 fix: make progressive checkpoints evidence-bound`
- R-06 status: independently reviewed, repaired, verified, and privately
  checkpointed

## Included R-06 Surface

- schema-v2 per-window recovery records
- exact memory DB, knowledge graph, vectors, scene manifest, and temporal-index
  target states
- read-only SQLite and artifact evidence probes
- canonical Phase 6/Qdrant vector-commit evidence from the scene manifest
- stale, legacy, failed, and non-contiguous resume handling
- manifest-only isolated resume without creating `memory.db`
- timeline restoration before rewritten manifests
- final cleanup gated by a fresh exact-window persistence re-probe
- canonical architecture and CLI contract updates

## Review-Driven Repair

The first isolated extraction matched the prior R-06 implementation and passed
its focused tests, but independent review found that final cleanup still used
Qdrant-derived `phase6_complete` as its only delete gate. A window could record
a failed memory, graph, manifest, or temporal target and still lose its recovery
checkpoint.

The repair adds `_progressive_checkpoint_cleanup_ready()`. Cleanup now requires
Phase 6 completion and equality between all current window indices and the
freshly re-probed schema-v2 committed-window set. Qdrant completion alone cannot
delete recovery evidence. Positive and failed-target regressions cover the
gate, and both canonical contracts name the rule.

## Explicit Boundaries

- The frozen mixed main checkout was not staged, reset, restored, cleaned, or
  rewritten; its inventory remained 85 entries.
- No ingestion, promotion, service mutation, or live-dataset write was run.
- The old UCF ingestion integration test remains machine- and live-epoch-bound.
  It was not manufactured into a hermetic pass; that harness drift remains
  assigned to R-18/R-09.
- This checkpoint does not claim the V-02 interruption witness. That live
  bounded witness remains a later explicit verification lane.

## Verification Evidence

Fresh verification completed on 2026-07-11 in the isolated R-06 worktree.

- 42 hermetic progressive, isolation, runtime-preview, and governance tests
  passed in 9.41 seconds. This is the historical 41-test hermetic pack plus the
  new cleanup regression.
- 29 expanded progressive, isolation, Phase 6 truth/integrity, temporal repair,
  and progress-tracking tests passed in 5.93 seconds.
- The targeted cleanup positive/negative pair passed.
- Both test runs left the worktree status unchanged.
- Python compile passed for runtime and test files.
- `git diff --cached --check` passed.
- Banned-token, literal-root, and legacy-checkpoint-flag scans passed.
- Runtime, tests, and the architecture contract were transplanted exactly from
  the frozen implementation before the cleanup correction; the CLI reference
  imported only its R-06 block and retained the checkpointed R-02 wording.
- Two independent read-only reviews confirmed the final staged seam and found
  no remaining semantic or checkpoint-mechanics blocker.

## Resume

Continue R-17 classification and extraction of the remaining frozen main-tree
families. Keep foundational documentation separate, and do not fold identity,
Command Center, generated-report, or current-state work into this checkpoint.
