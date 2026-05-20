<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-05-20 -->

# GoodQ4All Current Agent State

This is the first-read handoff for fresh GoodQ4All agents. It is a routing
surface, not a replacement for the canonical runtime contracts.

## Current Mission

Prepare the local-first GoodQ4All runtime for a clean home-movie memory test.
Prior proving-ground memory, including Seinfeld/sample/test and prior home-movie
test runs, is disposable and should not seed the next run.

## Verified Runtime Posture

- Local API target: `http://127.0.0.1:30000`
- Qdrant target: `http://127.0.0.1:6333`
- Primary host: Windows 11 desktop
- Conda environment: `goodq_core`
- Current profile from runtime config: `BASELINE`
- WSL distro from runtime config: `Ubuntu-22.04`
- Operator console: read-only UI, no ingestion/control authority

## Clean-Start Checkpoint

Read `docs/agent/workflows/CLEAN_MEMORY_START.md` before deleting or rerunning
memory surfaces.

Tracked cleanup audit summary:

- `docs/diagnostics/MEMORY_CLEAN_START_AUDIT_2026-05-20.md`

Pre-clean audit found and cleared:

- Qdrant collections: `68`
- Qdrant epochs represented: `17`
- Qdrant points: `17,767`
- Collection names classify as witness, smoke, semantic-cleanup, Season, or
  legacy epoch test memory.
- Cleanup result: all `68` old `goodq_` collections deleted successfully; `0`
  delete errors.
- Post-clean state: `4` fresh home-memory collections exist, all green, all
  with `0` points.
- Generated runtime reports were cleaned so `/api/runs/latest/evidence` now
  returns `no_indexed_runs` instead of old probe data.
- Prior filesystem epochs were removed except for a small
  `epoch_2025_12_22` log stub held open by the Qdrant Windows service.
- Active API status on port `30000` reports `database.exists=false` and
  `database.scenes=0` for the fresh epoch.

Fresh local test epoch:

- `epoch_2026_05_20_home_memory_clean`

The fresh epoch should use empty Qdrant collections:

- `goodq_clip_epoch_2026_05_20_home_memory_clean`
- `goodq_dino_epoch_2026_05_20_home_memory_clean`
- `goodq_text_epoch_2026_05_20_home_memory_clean`
- `goodq_audio_epoch_2026_05_20_home_memory_clean`

## Do Not Investigate First

These are known historical/proving-ground echoes unless a current audit proves
they are active again:

- Seinfeld/Season witness results appearing in Qdrant or old epoch directories.
- `epoch_2025_12_22` or `epoch_2025_12_23` being called "clean" by older docs.
- Basement-era status pages claiming to be the active scratchpad.
- Legacy scene-id-only audio vectors as current-run audio proof.

## Current Source Of Truth

- Durable agent protocol: `AGENTS.md`
- Machine-readable state mirror: `docs/agent/current_state.json`
- Clean-start workflow: `docs/agent/workflows/CLEAN_MEMORY_START.md`
- Config loading contract: `docs/architecture/CONFIG_LOADING_CONTRACT.md`
- Memory storage contract: `docs/architecture/MEMORY_STORAGE.md`
- Audio vector provenance: `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
- API surface: `docs/reference/API.md`

## Safe Next Actions

1. Capture or inspect the cleanup manifest in
   `reports/local_housekeeping/2026-05-20-memory-clean-start/` if working on
   this local machine.
2. Confirm local config points to the fresh home-memory epoch.
3. Run one small home-movie scene through the pipeline and inspect the operator
   console before broad ingestion.
