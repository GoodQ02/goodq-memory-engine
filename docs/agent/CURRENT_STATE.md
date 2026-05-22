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
- Local vLLM primary: `http://127.0.0.1:38005/v1`, systemd unit
  `vllm-llama1b.service`, model
  `/home/jdben/models/Qwen2.5-0.5B-Instruct`
- WSL vLLM lifetime: Windows operator sessions should start through
  `scripts/start_vllm_servers.bat`, which starts one named
  `goodq-vllm-keepalive` anchor so WSL remains alive while vLLM serves.
- Windows logon fixture: Task Scheduler task `GoodQ4All vLLM WSL Startup`
  invokes the same wrapper with pauses disabled.
- Ollama fallback: optional/offline unless started separately.

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
- Active API status on port `30000` is bound to the `_04` clean clip probe
  epoch. It currently reports the latest `1`-scene FAMILY clip probe, not an
  empty broad-run seed. Reset Qdrant and use a fresh epoch before the next probe
  or broad home-memory run.

Fresh local validation epoch:

- `epoch_2026_05_21_family_full_clean_04`

The active validation epoch uses these Qdrant collections:

- `goodq_clip_epoch_2026_05_21_family_full_clean_04`
- `goodq_dino_epoch_2026_05_21_family_full_clean_04`
- `goodq_text_epoch_2026_05_21_family_full_clean_04`
- `goodq_audio_epoch_2026_05_21_family_full_clean_04`

This epoch now contains validation/probe evidence. It is useful for audit and UI
verification, but it must not seed the next probe or broad home-movie pass
unless the operator deliberately resets Qdrant and verifies fresh/explicit-ID
FAISS targets first. The previous `_01`, `_02`, and aborted `_03` attempts also
contain validation or partial probe residue and must not seed the broad run.

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
- Operator Console v1 now includes a Current Scope strip above Flight Deck.
  Live validation against port `30000` showed the selected API, latest run,
  run source `Direct CLI Output`, temporal scope `1` scene, strict audio proof
  `Proven`, selected browsing target, selected scene, and read-only mode.

Root cause confirmed:

- Explicit report-root probes wrote immutable-looking copies under
  `reports/fresh_ingest_runs`.
- Direct/default CLI probes wrote to the configured epoch output and mutable
  processing artifacts, but did not create a newer report-root entry.
- The old selector only considered report roots, so it could pair stale
  report-root scene results with refreshed temporal artifacts from the active
  epoch. The selector now considers both surfaces and chooses the freshest
  read-only scope.

## FAISS Memory Path Audit And Repair

A one-scene FAISS validation run completed against the active validation epoch
after the memory-path repair.

Scope:

- Source scope: first redacted FAMILY media file.
- Probe scope: `1` video, `1` scene.
- Runtime run id: `e85a53c7-97b7-48bb-a6f5-56b78f066fa9`.
- Configured-output backup:
  `reports/local_housekeeping/2026-05-21-home-movie-preflight/one_scene_faiss_validation_run/configured_output_backup/scene_ingest_results.before_one_scene_faiss_validation.json`

Validated:

- Text FAISS path is configured under the active epoch and reads as an
  explicit-ID `IndexIDMap2` from the text embedding environment.
- CLIP FAISS path is configured under the active epoch and reads as an
  explicit-ID `IndexIDMap2` from the visual embedding environment.
- DINO FAISS path is configured under the active epoch and reads as an
  explicit-ID `IndexIDMap2` from the visual embedding environment.
- Phase 6a runs in `goodq_image_caption`, writes Qdrant as canonical vector
  truth, and writes configured CLIP/DINO FAISS parity when explicit-ID support
  is available.
- `/api/runs/latest/evidence` reports projection gaps `ok`, Phase 6 Qdrant
  `ok`, Phase 6 FAISS `ok`, and current-run audio proof `Proven` for the
  validation run.
- Realtime KG scene update resolved entities during the validation run.

Repair applied:

- FAISS writers now require explicit stable IDs for claimed FAISS commits.
- New HNSW FAISS indexes are wrapped in `IndexIDMap2`.
- Direct audio, CLIP, DINO, text-router, and Phase 6 FAISS writes no longer
  silently downgrade from `add_with_ids` to position-based `add`.
- CLIP/DINO direct writers keep separate modalities, Qdrant collections, FAISS
  indexes, ID maps, and SQLite embedding rows.

Known previous-epoch residue:

- The previous `_01` audio FAISS file read as a legacy non-IDMap HNSW index from
  earlier validation probes.
- The current target is the fresh `_02` epoch. Before a broad home-movie run,
  confirm all `_02` FAISS targets are absent or explicit-ID indexes.

Follow-up preflight refresh on 2026-05-21:

Pre-probe `_02` launch checkpoint:

- Port `30000` API was restarted after `config.local.yaml` moved to `_02`.
- At that checkpoint, `/api/status` reported `database.exists=false`,
  `database.scenes=0`, and pipeline `idle`; this was the expected clean-run
  launch state before the validation probes below.
- At that checkpoint, `/api/runs/latest/evidence` reported `available=false`
  with reason `no_indexed_runs`; this prevented stale `_01` evidence from
  appearing as the current scope before ingestion.
- The four `_02` Qdrant collections were green with `0` points.
- The `_02` FAISS directory did not exist yet. This was acceptable because the
  writers needed to create fresh explicit-ID indexes.
- The old `_01` text, CLIP, and DINO FAISS indexes read as `IndexIDMap2`.
- The old `_01` audio FAISS index reads as legacy `IndexHNSWFlat` and must not
  be reused.
- Shared FAISS memory writes now reject vectors without explicit IDs instead
  of silently using position-based `add`.
- Direct CLIP and DINO writers now return provenance-style commit fields for
  FAISS, Qdrant, SQLite id-map, and SQLite embedding writes.

Follow-up clean `_02` ingestion probe on 2026-05-21:

- Probe scope: first redacted FAMILY media file, `1` video, `1` scene.
- Runtime run id: `724376e0-d265-48e9-8891-1cf402ee7b6c`.
- Pipeline status after probe: idle.
- `/api/status` reports `database.exists=true` and `database.scenes=1`.
- `_02` Qdrant counts: CLIP `2`, DINO `2`, text `2`, audio `1`.
- `_02` FAISS indexes all read as explicit-ID `IndexIDMap2`:
  text `2`, CLIP `2`, DINO `2`, audio `1`.
- FAISS id-map tables exist and are populated: CLAP `1`, CLIP `2`, DINO `2`.
- SQLite memory has `1` scene, `24` segments, `7` embeddings, `7` memory commit
  events, and `53` links.
- Knowledge graph has `13` nodes, `24` edges, `1` event, `1` media node, and
  `37` node-media links.
- `/api/runs/latest/evidence` selects the configured output run, reports
  projection gaps `ok`, temporal scope `1` scene, scene-context LLM `1 / 1`,
  and current-run audio proof `Proven` for `1 / 1` CLAP-ok scenes.
- `/api/memory/stats` reports count-only FAISS storage visibility for the same
  scope: text `2`, CLIP `2`, DINO `2`, audio `1`.
- API sentiment summary now counts temporal `full_transcript` as transcript
  evidence. The same route now reports `segments_with_transcript=1` for this
  run after the read-model fix.
- API memory stats now fall back to persisted SQLite embedding/id-map counts
  when the API environment cannot import FAISS, but only when the corresponding
  FAISS index file exists.
- Operator Console proof-panel refresh against port `30000` showed evidence
  coverage `100%`, observed signals `15 / 15`, current-run audio proof
  `Proven`, and FAISS audio count `Count present`.
- Audio emotion is intentionally not promoted for this scene: raw neutral score
  is about `0.132`, below the `0.5` promotion threshold, so the UI should show
  raw/not-promoted evidence rather than a hard emotion label.

Follow-up `10`-scene validation probe on 2026-05-21:

- Probe scope: first redacted FAMILY media file, `1` video, `10` scenes.
- Runtime run id: `52ccf932-7a63-4243-801b-c108bf79157a`.
- Pipeline status after probe: idle.
- `/api/status` reports `database.exists=true` and `database.scenes=10`.
- `_02` Qdrant counts after the run: text `20`, CLIP `20`, DINO `20`, audio
  `10`.
- `/api/runs/latest/evidence` selects the configured output run, reports
  projection gaps `ok`, temporal scope `10` scenes, sentiment labels for
  `10 / 10` scenes, current-run audio proof `Proven`, and `10 / 10`
  run-matched Qdrant audio points.
- Runtime evidence now distinguishes strict audio-emotion labels from ranked
  review evidence: promoted labels `0 / 10`, ranked audio-emotion score
  segments `10 / 10`.
- Text emotion classification was repaired after this run by loading the
  CardiffNLP emotion model with `use_safetensors=True` and by not assuming
  `memory_fraction` is present in the GPU config. Existing `_02` artifacts
  still show `segments_with_text_emotion_ranking=0`; the next clean probe should
  populate `text_emotion_ranking` if `emotion_classify` remains healthy.
- Operator Console assets were cache-busted with
  `20260521-emotion-ranking-1`; the audio-emotion panel should show ranked
  coverage separately from promoted labels.
- Before the next probe, follow `docs/agent/workflows/CLEAN_MEMORY_START.md`:
  use a fresh epoch or reset Qdrant and verify FAISS targets are absent or
  explicit-ID indexes.

Clean `_04` emotion-ranking clip probe on 2026-05-21:

- Probe scope: short local clip extracted from the first redacted FAMILY media
  file, `1` video, `1` scene.
- Runtime run id: `7c811231-b85c-4489-91b4-672d7bae57be`.
- Full-source probe attempt against `_03` was stopped before step-ledger writes
  because `--max-scenes 1` still required full-video scene detection. Treat
  `_03` as partial scaffolding, not evidence for broad ingestion.
- `_04` started from a verified clean boundary: fresh Qdrant collections had
  `0` points, and configured FAISS/id-map targets were absent.
- `/api/status` reports `database.exists=true` and `database.scenes=1`.
- `_04` Qdrant counts after the probe: text `2`, CLIP `2`, DINO `2`, audio `1`.
- FAISS indexes read as explicit-ID `IndexIDMap2`: text `2`, CLIP `2`, DINO
  `2`, audio `1`.
- `step_runs.jsonl` contains `21` rows, all `ok`; `sentiment`,
  `emotion_classify`, `audio_embed_clap`, `scene_visual_embeddings`, and
  `cross_modal_harmonization` all completed.
- `/api/runs/latest/evidence` selects the configured output run, reports
  projection gaps `ok`, temporal scope `1` scene, transcript `1 / 1`,
  sentiment `1 / 1`, text emotion ranking `1 / 1`, ranked audio-emotion scores
  `1 / 1`, current-run audio proof `Proven`, and `1 / 1` run-matched Qdrant
  audio points.
- Top text-emotion signal is `admiration` with score about `0.955`; top
  audio-emotion score signal is `surprise` with score about `0.135`, below the
  `0.5` promotion threshold. This is the intended distinction between ranked
  review evidence and promoted emotion labels.
- Scene context LLM evidence is present and transcript-dominant; KG resolved
  `4` dialogue entities after transcript became available. Realtime KG still
  logs an early no-entity observation before transcript is present, so the next
  KG polish seam is ordering/labeling rather than total absence.

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
2. Confirm local config points to the intended fresh home-memory epoch.
3. Use the Operator Console Current Scope strip as the preflight check: API
   `30000`, run source, temporal scope, audio proof, selected browsing target,
   and read-only mode should be visible before broad ingestion.
4. Start local LLM support with `scripts/start_vllm_servers.bat` and verify
   `http://127.0.0.1:38005/v1/models` before LLM-backed scene analysis.
5. If the scene evidence remains acceptable in the Operator Console, run the
   first full source video.
