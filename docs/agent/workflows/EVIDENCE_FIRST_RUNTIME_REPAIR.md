<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_WORKFLOW -->
<!-- DOC_LAST_VERIFIED: 2026-05-22 -->

# Evidence-First Runtime Repair

Use this workflow when a runtime capability looks absent, stale, or partially
proven, especially around WSL audio, local LLM fallback, Qdrant/FAISS proof,
sentiment, entities, or operator-console visibility.

## Purpose

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
   - UI truth: operator console labels and evidence panels

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
