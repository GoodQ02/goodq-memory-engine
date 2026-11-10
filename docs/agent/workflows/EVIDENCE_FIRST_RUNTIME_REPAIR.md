<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# Evidence-First Runtime Repair

Use this for a demonstrated runtime, API, persistence or UI evidence failure.
For ingestion-quality evaluation, also use [pipeline troubleshooting](PIPELINE_TROUBLESHOOTING_FLOW.md).
Applicable `AGENTS.md`, the current authorization/checkpoint and the subsystem
contract define scope. This workflow grants no ingestion, promotion or deployment
authority and is not required for ordinary documentation edits.

## Diagnose and verify the affected boundary

1. Define one observable failure and the result that would close it. Inspect the
   caller, relevant contract and existing evidence before changing anything.
   Resolve conflicting observations instead of repeating an entire old workflow.
2. Compare only relevant surfaces: resolved config, actual runtime owner/status,
   durable output and its consumer. Discover the configured endpoint; do not
   assume a default port or that `/api/runs/latest/evidence` belongs to this run.
   Use bounded read-only checks first and keep secret-bearing config output local.
3. Repair the cause at its owning boundary and retain original-failure evidence.
   Validate the regression and affected production caller, including meaningful
   negative/failure cases. Do not weaken contracts or hide diagnostic failures.
4. Select integration evidence by the claim below. Expand only when the boundary
   under test, current authorization and earlier evidence justify it.

| Claim | Required evidence |
| --- | --- |
| Read model, API or UI consumes existing output correctly | Isolated production-caller check against suitable saved/copy fixtures; verify attributable output and failure behavior |
| Current ingestion produces correct evidence | Fresh isolated source-to-consumer probe through the selected production path; follow [clean memory start](CLEAN_MEMORY_START.md) |
| Ingestion coverage, cross-scene behavior, duration or recovery | Authorized selected full-source witness when the smaller probe cannot establish the claim |
| Runtime deployment or release works | Its existing deployment/release gates in addition to source checks; a unit pass is not deployment evidence |

For ingestion proof, bind revision/configuration, input hash, run and epoch.
Inspect each applicable selected store/step and its consumer: manifests, ledger,
SQLite/KG and configured vector outputs as relevant. Qdrant point provenance and
FAISS type/count checks apply when those stores participate; they are not gates
for unrelated repairs. Explain warnings, fallbacks and supported negatives.
An optional-stage failure can preserve core operation without passing that feature.

## Record and stop

Keep exact commands/results, evidence locations and unverified scope in the task
receipt. Update `PROJECT.md` when its checkpoint changes and the roadmap when a
gate changes; avoid duplicating the narrative. Generated current-state/RAG
projections are never hand-edited. Use `scripts/docs/build_current_state.py` only
for an in-scope capture/render/verify; rendering old evidence does not refresh it.

Report confirmed defects and material unresolved risks with supporting evidence;
label hypotheses and use the smallest useful check before promoting them to
findings. Do not flood the backlog with every speculative issue. Preserve useful
historical receipts without copying their old directions into current instructions.

Reuse passing checks on unchanged source. If independent review is used, the lead
checks the relevant evidence, source/diff and test coverage; rerun a test only for
a changed patch, missing/contradictory evidence or an applicable release gate.
Do not edit code/config while a running witness may import it, overlap mutating
seams, or bypass current review/test holds. A failing broad gate remains failed;
diagnose it before spending on unrelated validation. Stop at the approved outcome
or an actual blocker and report its source, rather than repeating the plan.

## Historical derived-evidence backfill


Use this branch when a completed canonical corpus has a bounded historical
failure in one *derived* evidence surface—such as speaker signatures—while the
source audio, transcript, diarization, and scene identity already exist.

This is a repair workflow, not an ingestion workflow. Do not re-ingest media to
repair a derived field unless the inspect plan proves the underlying evidence is
missing or invalid.

1. **Inspect only.** Build a deterministic ledger from canonical manifests and
   local artifacts. Classify each historical failure as `eligible`, `blocked`,
   or already explained; list the field-path reason for every blocked item.
   For speaker signatures, eligibility must also satisfy the worker's
   deterministic per-speaker diversity thresholds before WSL is invoked.
2. **Prove the narrow computation.** In a fresh proof envelope, consume only
   the existing minimum inputs. For speaker signatures this means audio plus
   persisted diarization; it must not transcribe or diarize again.
3. **Promote one scene.** Require a digest-bound confirmation, before/after
   checksums, backup, rollback, and a receipt. Change only the canonical
   derived field and its matching temporal projection. Preserve transcript,
   diarization, CLAP, visual evidence, and neutral provenance.
4. **Re-inspect independently.** The historical-debt count must decrease by
   exactly one, with no new changes outside the target scene and temporal
   segment.
5. **Scale serially.** Only after the one-scene receipt passes, prepare small
   deterministic batches. Every batch gets a fresh inspected digest, one
   receipt per scene, and stops on the first checksum, artifact, runtime, or
   projection mismatch. Never treat `success` status without its required
   payload as eligible.

Current GoodQ tooling:

- `cli/signature_backfill_plan.py` is inspect-only and emits the eligible-set
  digest; it has no execution path.
- `wsl2_audio/signature_only.py` computes signatures from existing waveform
  and diarization only.
- `cli/signature_backfill_execute.py` performs the token-bound one-scene
  promotion with backup and rollback.
- `cli/signature_backfill_batch_execute.py` builds one fresh deterministic
  batch, requires a batch-bound token, creates one signature-only CUDA proof
  and one atomic promotion receipt per scene, and stops at the first failure.
  It accepts only the immediate next batch (`--batch-index 1`), because the
  eligible ledger rebases after every committed batch; this prevents skipped
  scene ranges.
  It does not automatically roll back earlier committed scene receipts; that
  partial outcome is recorded as a stopped batch receipt for review.
- `cli/signature_backfill_serial_run.py` repeats only that immediate-next
  operation for an explicitly bounded run, independently audits each committed
  batch against its backups and projections, and stops on the first failed
  execution or audit gate.


## Interpretation traps

- A plain environment probe can be a false negative for a sourced worker runtime.
- Collection totals and latest-run selectors do not establish selected-scene proof.
- Scene-present, dialogue-mentioned, candidate-visible and speaker-aligned
  evidence remain distinct; model confidence does not merge these channels.
- Preserve useful audio-emotion rankings even when no label qualifies for promotion.

Use the [agent decision protocol](../../architecture/AGENT_DECISION_PROTOCOL.md)
for scene/contract and external-anchor boundaries. Private delivery, public
sanitization and publication remain separate authorization and evidence gates.
