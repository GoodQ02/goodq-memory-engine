<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-05-24 -->

# Evidence-First Runtime Repair

Use this workflow when a runtime capability looks absent, stale, or partially
proven, especially around WSL audio, local LLM fallback, Qdrant/FAISS proof,
sentiment, entities, operator-console visibility, or Retro Memory Explorer views.

## Purpose

> [!NOTE]
> **Issue Diagnostics & Reporting Directive (Mandatory Coverage)**
> Report every issue you find, including ones you are uncertain about or consider low-severity. Do not filter for importance or confidence at this stage - a separate verification step will do that. Your goal here is coverage: it is better to surface a finding that later gets filtered out than to silently drop a real bug. For each finding, include your confidence level and an estimated severity so a downstream filter can rank them.

Close one concrete evidence seam without widening the blast radius.

This workflow is for cases where the system probably has the right pieces, but
the operator surface, API route, runtime config, or persistence boundary is not
showing truthful evidence yet.

## Loop

1. **Name one seam**
   - Example: API reports `faster_whisper=not_installed`, but WSL preflight says
     the configured worker can import it.
   - Do not combine unrelated seams in the same pass.

2. **Prove the current contract**
   - Start with `AGENTS.md`, `docs/agent/CURRENT_STATE.md`,
     `docs/agent/current_state.json`, and the subsystem contract.
   - Run read-only status probes first:

```powershell
git status --short --branch
conda run --no-capture-output -n goodq_core python -m cli.print_config
Invoke-RestMethod -Uri 'http://127.0.0.1:30000/api/status' -TimeoutSec 10
```

3. **Compare authoritative surfaces**
   - Config truth: `cli.print_config`
   - Runtime truth: API status, service health, WSL preflight, Qdrant status
   - Persistence truth: scene manifests, temporal index, Qdrant payloads, FAISS
     indexes, SQLite/KG rows
   - UI truth: operator console labels, Retro Memory Explorer views/logs, and evidence panels

4. **Patch the boundary, not the symptom**
   - If an API probe checks the wrong environment, fix the probe.
   - If a read model collapses distinct evidence channels, fix the projection.
   - If a writer claims success without durable proof, fix the writer contract.
   - Keep code changes narrow and covered by a focused regression test.

5. **Validate in two gates**
   - Gate A: targeted unit/contract test for the seam.
   - Gate B: fresh scene-first probe in a fresh epoch with Qdrant empty and
     FAISS absent/new.

6. **Inspect the evidence envelope**
   - Confirm `/api/runs/latest/evidence` reports the intended scope.
   - Confirm Qdrant point counts and current-run payload provenance.
   - Confirm FAISS index type and point counts.
   - Confirm step ledger failures/warnings are zero or explained.
   - Confirm retrieval/UI surfaces show evidence without overclaiming.

7. **Update agent communication**
   - Update `docs/agent/CURRENT_STATE.md`.
   - Mirror material state into `docs/agent/current_state.json`.
   - Update the relevant workflow/contract if the pattern should be reused.
   - Mark superseded observations as historical instead of deleting useful
     provenance.

## Historical Derived-Evidence Backfill Branch

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

## Fresh Probe Rules

- Use a fresh epoch for personal-memory validation.
- Reset or manifest-delete only `goodq_` Qdrant collections when cleanup is
  approved.
- Verify fresh collections have `0` points before ingestion.
- Verify target FAISS files are absent or explicit-ID indexes before broad
  ingestion.
- Run one scene or a tiny clip before a full source.
- Treat generated probe artifacts as local evidence, not source docs.

## Pass Criteria

The pass is ready to commit when:

- the targeted unit/contract tests pass
- the scene-first probe completes
- strict proof surfaces are green for the claimed scope
- optional gaps are labeled as optional or historical, not hidden
- agent-facing docs no longer point a fresh agent toward the stale hypothesis

## Common Traps

- Plain environment checks can be false negatives if the pipeline uses a
  sourced worker runtime.
- Latest-run selectors can mix stale report roots with fresh epoch artifacts if
  scope is not explicit.
- Collection-level proof can look like scene-level proof unless selected-scope
  labels are precise.
- Entity channels must stay separate: scene-present, dialogue-mentioned,
  candidate-visible, and speaker-aligned evidence do not mean the same thing.
- Audio emotion rankings can be useful without promoted labels; do not hide
  ranked scores just because no label cleared the promotion threshold.
