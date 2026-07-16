<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-10 Architecture Contract Checkpoint

## Invariant

Canonical architecture documentation must distinguish staged artifact/evidence
state from active promoted memory and must name the configured desktop Qdrant
root without changing runtime configuration to match prose.

## Checkpoint Lineage

- Branch: `codex/r10-architecture-contracts`
- Base: `2562daaa`
- Implementation checkpoint: `24edd572 docs: align governed materialization contracts`
- R-10 status: independently reviewed, verified, and privately checkpointed

## Proven Storage Authority

The canonical desktop/config Qdrant root is:

```text
${GOODQ_DATA_ROOT}/qdrant_storage
```

It is a sibling of `${GOODQ_DATA_ROOT}/GoodQ_Data`. The approved config loader,
service environment, launcher/status consumers, and live populated storage all
resolved to that sibling layout. The formerly documented nested alternative
was absent. No data was moved and no service, binding, or configuration was
changed.

The packaged installer's ProgramData layout remains a separate distribution
layout. This checkpoint does not conflate it with canonical desktop/config
authority or claim that installer reconciliation is complete.

## Governed Materialization Contract

The aligned contracts now state one implemented lifecycle:

1. Under `ingestion_isolation: true`, `scene_manifest.json` is per-video
   artifact evidence, while `ucf/ucf_ledger.db` is lifecycle/evidence authority.
2. Isolated ingest stages UCF records and Qdrant points with
   `ucf_promotion_status = staged`; active SQLite memory and graph views are not
   created by staging or validation alone.
3. Explicit validation precedes a separately approved, human-gated
   `promote_ucf_to_memory` operation bound to exact `video_hash` and `epoch_id`.
4. Promotion materializes active `memory.db` and `knowledge_graph.db` views.
5. The UCF status mutation, transition audit, and durable Qdrant outbox enqueue
   share one SQLite transaction. Active-view cleanup is compensating and
   recoverable. Post-commit Qdrant delivery/reconciliation are separate durable,
   recoverable obligations; there is no cross-store ACID claim.
6. `promotion_committed_sync_pending` means active materialization and the UCF
   commit succeeded while durable Qdrant delivery remains pending.
7. Default active retrieval exposes promoted evidence. Explicit raw audit
   queries may inspect other lifecycle states without activating them.

Governed UCF promotion materializes video, scene, segment, and evidence graph
projections. Speaker-pattern and identity edges remain outputs of separate
governed identity workflows and are not implied by promotion alone. Qdrant is
the canonical vector authority; FAISS remains an optional configured
cache/projection/fallback.

## Verification Evidence

Fresh evidence from the isolated worktree:

- 37 focused documentation, portable-config, and materialization tests passed.
- 42 ingestion-isolation, transition, exact-scope promotion, materialization,
  durable Qdrant delivery, reconciliation, and promoted-visibility tests passed.
- `doc_authority_lint.py verify` passed, including structured lifecycle
  semantics and Qdrant tree-topology checks.
- `doc_drift_lint.py` scanned 292 active files with zero active path,
  drive-root, ghost-path, CUDA, archive-banner, corruption, or snapshot-authority
  violations.
- Current-state projections still match evidence `2923b9a7ca972db2`.
- Python compile, banned-token, dependency-drift, and staged-diff checks passed.
- Regression tests proved the semantic checker rejects missing sections,
  removed or inverted qualifiers, nested Qdrant trees with or without a
  trailing slash, and context-free token bags.
- An independent multi-round review finished with spec PASS and quality
  APPROVED after every Important finding was repaired and re-reviewed.

## Safety Boundaries

- No ingestion, validation, promotion, reconciliation, database mutation,
  service restart, network change, storage move, or installer change occurred.
- The mixed main checkout remained frozen at 96 expanded status entries.
- The public checkout working tree remained untouched.
- The historical ledger and completed July memory were not reopened.

## R-13 Closure

R-13's last semantic blocker was this Qdrant root contradiction. With this
checkpoint, the full documentation authority, link, metadata, mission, index,
current-state, epoch, storage, and governed-materialization checks pass.

## Resume

Continue from the single bounded mission in `PROJECT.md` and the ordered master
register in `docs/releases/ROADMAP.md`. Do not reopen this checkpoint unless
fresh code, configuration, or runtime evidence contradicts it.
