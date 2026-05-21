<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

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
- `docs/diagnostics/POWER_LOSS_INGESTION_AUDIT_2026-05-20.md`

Pre-clean audit found and cleared:

- Qdrant collections: `68`
- Qdrant epochs represented: `17`
- Qdrant points: `17,767`
- Collection names classify as witness, smoke, semantic-cleanup, Season, or
  legacy epoch test memory.
- Cleanup result: all `68` old `goodq_` collections deleted successfully; `0`
  delete errors.
- Initial post-clean state: `4` fresh home-memory collections existed, all
  green, all with `0` points.
- A power loss interrupted the first full home-memory run in
  `epoch_2026_05_20_home_memory_clean`. That epoch is preserved as forensic
  evidence and must not seed the next clean run.
- Generated runtime reports now expose the preserved interrupted run as
  `interrupted_ingestion` through `/api/runs/latest/evidence`.
- Prior filesystem epochs were removed except for a small
  `epoch_2025_12_22` log stub held open by the Qdrant Windows service.
- Active API status on port `30000` reports `database.exists=true` and
  `database.scenes=2` after the second small-scene probe below.

Fresh local test epoch:

- `epoch_2026_05_20_home_memory_clean_02`

The fresh epoch should use empty Qdrant collections:

- `goodq_clip_epoch_2026_05_20_home_memory_clean_02`
- `goodq_dino_epoch_2026_05_20_home_memory_clean_02`
- `goodq_text_epoch_2026_05_20_home_memory_clean_02`
- `goodq_audio_epoch_2026_05_20_home_memory_clean_02`

Preserved interrupted-run collections may also exist:

- `goodq_clip_epoch_2026_05_20_home_memory_clean`
- `goodq_dino_epoch_2026_05_20_home_memory_clean`
- `goodq_text_epoch_2026_05_20_home_memory_clean`
- `goodq_audio_epoch_2026_05_20_home_memory_clean`

These are evidence for the power-loss audit, not the target memory surface for
the next run.

## Latest Small-Scene Probes

The first post-power-loss scene probe completed successfully in the fresh
`epoch_2026_05_20_home_memory_clean_02` epoch.

Scope:

- Source scope: first redacted FAMILY media file.
- Probe scope: `1` video, `1` scene.
- Scene duration: `53.787` seconds.
- Runtime run id resolved from `scene_results.scenes.audio.clap_meta.run_id`.
- Pipeline status after probe: idle.

Observed fresh collection counts after the probe:

- `goodq_clip_epoch_2026_05_20_home_memory_clean_02`: `1`
- `goodq_dino_epoch_2026_05_20_home_memory_clean_02`: `1`
- `goodq_text_epoch_2026_05_20_home_memory_clean_02`: `2`
- `goodq_audio_epoch_2026_05_20_home_memory_clean_02`: `1`

High-value scene evidence surfaced:

- Visual vectors: present.
- Text vectors: present.
- Audio vector: present.
- Transcript: present.
- OCR: present.
- Caption: present.
- Sentiment: present.
- CLAP status: `ok`.
- `/api/runs/latest/evidence` audio vector proof:
  `current_run_audio_vector_proven`.
- `/api/runs/latest/evidence` temporal index projection: `ok`, `1` scene.
- `/api/runs/latest/evidence` projection gaps: `ok`.

Known follow-up from the probe:

- Entity extraction produced no scene-present KG entities for the first scene.
  Treat this as a content/sequence follow-up, not a failed run.

The second small-scene probe then completed successfully against the same
fresh epoch.

Scope:

- Source scope: same first redacted FAMILY media file.
- Probe scope: `1` video, `2` scenes.
- Runtime run id: `80160289-208d-4303-bd42-5cc0d36976ab`.
- Pipeline status after probe: idle.

Observed fresh collection counts after the second probe:

- `goodq_clip_epoch_2026_05_20_home_memory_clean_02`: `2`
- `goodq_dino_epoch_2026_05_20_home_memory_clean_02`: `2`
- `goodq_text_epoch_2026_05_20_home_memory_clean_02`: `4`
- `goodq_audio_epoch_2026_05_20_home_memory_clean_02`: `2`

High-value second-probe evidence surfaced:

- `/api/runs/latest/evidence` temporal index projection: `ok`, `2` scenes.
- Current-run audio proof: `2 / 2` CLAP-ok scenes proven against run-matched
  Qdrant payloads.
- Text sentiment labels: present for both scenes.
- Dialogue-mentioned entities, mentioned people, visible-person candidates,
  and speaker-aligned mentions are now projected through timeline, scene, and
  search read models.
- Operator console scene evidence now distinguishes scene-present entities
  from dialogue/candidate identity evidence instead of reporting all entity
  evidence as not exposed.
- Search read models redact local CLAP/FAISS paths at the top-level
  `clap_meta` surface.

Superseded follow-ups from the second probe:

- Optional `scene_context_llm` and realtime KG entity resolution were retested
  in the validation rerun below.
- Scene-present entities remain stricter than dialogue/candidate evidence; do
  not collapse those labels in the UI or API.

## LLM and Realtime KG Validation Rerun

A follow-up two-scene rerun completed on the fresh epoch after starting the
existing local vLLM backend.

Scope:

- Source scope: same first redacted FAMILY media file.
- Probe scope: `1` video, `2` scenes.
- Runtime run id: `69b204f3-afb7-4812-9a43-0a1251107731`.
- Pipeline status after probe: idle.
- Local vLLM primary: healthy on `127.0.0.1:38005`.
- Ollama fallback: offline; fallback chain is limited but primary LLM calls
  work.
- Control Agent: still disabled because it requires an injected `llm_client`;
  this is separate from vLLM API health.

Validated improvements:

- `scene_context_llm`: present for `2 / 2` temporal segments.
- Realtime KG update: no longer reports the old missing-key zero; the rerun
  logged resolved entities for scene processing.
- KG DB after the rerun contains person, location, and generic entity nodes
  for the two-scene scope.
- Separate Qdrant audio inventory shows the new runtime run id has `2`
  run-tagged, provenance-capable audio points in the fresh audio collection.
- `scripts/test_llm_client.py` now initializes from the validated config
  surface and successfully talks to the vLLM primary.

Known follow-up from the rerun:

- Superseded by the direct-output selector validation below. The old symptom
  was that `/api/runs/latest/evidence` could mix the latest refreshed temporal
  artifacts with an older standalone report-root run id after ad hoc direct CLI
  reruns.

## Latest Direct-Output Selector Validation

A one-scene direct/default CLI probe completed after the LLM/KG validation
rerun. This intentionally used the configured runtime output path instead of a
new `reports/fresh_ingest_runs` report root.

Scope:

- Source scope: same first redacted FAMILY media file.
- Probe scope: `1` video, `1` scene.
- Runtime run id: `c6fe8dc1-d3d1-4685-b784-bdc0c84fba22`.
- Pipeline status after probe: idle.

Validated selector fix:

- `/api/runs/latest/preview` and `/api/runs/latest/evidence` now prefer the
  newer configured CLI output when it is fresher than repo-local report roots.
- Latest evidence run scope: `configured_output_scene_results`.
- Current-run audio proof: `1 / 1` CLAP-ok scene proven against run-matched
  Qdrant payloads.
- Projection gaps: `ok`.
- Qdrant audio inventory still remains separate and read-only; it does not
  override latest structured-run proof.

Root cause confirmed:

- Explicit report-root probes wrote immutable-looking copies under
  `reports/fresh_ingest_runs`.
- Direct/default CLI probes wrote to the configured epoch output and mutable
  processing artifacts, but did not create a newer report-root entry.
- The old selector only considered report roots, so it could pair stale
  report-root scene results with refreshed temporal artifacts from the active
  epoch. The selector now considers both surfaces and chooses the freshest
  read-only scope.

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
3. Inspect the operator console against the latest direct-output selector
   validation run.
4. If the scene evidence is acceptable, decide whether to run the first full
   source video or do one more UI pass for the latest-run proof scope banner.
