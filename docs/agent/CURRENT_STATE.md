<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_AGENT_STATE -->
<!-- DOC_LAST_VERIFIED: 2026-05-29 -->

# GoodQ4All Current Agent State

This is the first-read handoff for fresh GoodQ4All agents. It is a routing
surface, not a replacement for the canonical runtime contracts.

## Current Mission

Prepare the local-first GoodQ4All runtime for a clean home-movie memory test.
Prior proving-ground memory, including Seinfeld/sample/test and prior home-movie
test runs, is disposable and should not seed the next run.

## Active Agent Workflows

- `docs/agent/workflows/CLEAN_MEMORY_START.md`: clean-slate Qdrant, epoch, and
  FAISS preparation before personal-memory ingestion.
- `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`: evidence-first repair
  loop for capability gaps where config, runtime, persistence, and UI surfaces
  must be reconciled before broad reruns.

## Verified Runtime Posture

- Local API target: `http://127.0.0.1:30000`
- Qdrant target: `http://127.0.0.1:6333`
- Primary host: Windows 11 desktop
- Conda environment: `goodq_core`
- Current profile from runtime config: `BASELINE`
- WSL distro from runtime config: `Ubuntu-22.04`
- Standalone Setup Installer (`GoodQ4All_Setup_1.0.0.exe`): Active zero-dependency sandboxed package containing full PyPI dependency closure, preflight perception libraries (`opencv-python`, `scenedetect`, `imageio-ffmpeg` for auto-resolved FFmpeg binaries), and a supervising Go launcher (`LAUNCH_GOODQ.exe`) that manages Qdrant/API/Watchdog and launches the browser automatically on boot.
- Sandboxed execution safety: The python execution path loader (`python_paths.py`) automatically bypasses Conda when running in the sandboxed target environment or when conda is missing. The GPU configuration manager (`gpu_config.py`) wraps PyTorch (`torch`) imports in try-except blocks, falling back to CPU mode dynamically instead of failing with ModuleNotFoundError.
- Log permission redirection: The mission logger (`goodq_logger.py`) dynamically maps log directories to writeable ProgramData (`%PROGRAMDATA%\GoodQ4All\logs`) when no custom path is specified, and wraps file logger creation in a try-except block to gracefully fall back to console logging on write permission errors.
- Offline API documentation: Mounts and serves `/docs` and `/redoc` locally from offline caches (`ui/docs_offline/`) when internet access is absent.
- Operator console: read-only UI, no ingestion/control authority
  - Retro Memory Explorer: read-only memory viewer, served at `/ui/retro_console_v1/`
    (v1.4.7). Features: collapsible Cyber-Helipad **Upload Pad** panel in the header for drag-and-drop file ingestion; four-panel dynamic layout (Search · Map · Inspector · Timeline)
    with individually resizable and collapsible panels and floating restore tabs; entity
    co-occurrence canvas graph with pan/drag/wheel zoom, dynamic coordinate-level spacing zoom
    (separating nodes on zoom without bloating shapes or text labels), and smooth zoom-flight to
    selected nodes; entity filter checklist with bidirectional canvas sync; deterministic
    interaction model (single-click selects and zooms, checkbox toggles multi-select,
    double-click deselects, empty canvas click resets entity selection while preserving
    search results, Reset View button clears everything); multi-entity filter narrows
    timeline scene cards incrementally; Inspector with VS Code-style subsection splitter
    for the Data Trail Logs section (collapsible, resizable, fills remaining space when
    collapsed); canvas ResizeObserver prevents aspect-ratio distortion during panel
    resizes; forensic data trail query logging; search query centers and zooms to
    matching entity node; cyber-blue (`#00d2ff`) selection highlights; reduced-motion
    media query support; dynamic keyframe image viewer (CRT animated standby / fallback) and
    transcript display positioned directly below the keyframe in the Inspector.
- Local vLLM primary: `http://127.0.0.1:38005/v1`, systemd unit
  `vllm-llama1b.service`, model
  `/home/jdben/models/Qwen2.5-0.5B-Instruct` (optimized with memory allocation
  capped at `--gpu-memory-utilization 0.60` and FP8 KV-cache `--kv-cache-dtype fp8`,
  limiting the active pool to ~9.6 GB of VRAM while maintaining ~275 - 365 tok/sec
  generation speeds and ~14ms TTFT).
- WSL vLLM lifetime: Windows operator sessions should start through
  `scripts/start_vllm_servers.bat`, which starts one named
  `goodq-vllm-keepalive` anchor so WSL remains alive while vLLM serves.
- Windows logon fixture: Task Scheduler task `GoodQ4All vLLM WSL Startup`
  invokes the same wrapper with pauses disabled.
- Ollama fallback: healthy Windows fallback on `http://127.0.0.1:31434/v1`
  running `phi4:latest` (14.6B), optimized via Flash Attention (`OLLAMA_FLASH_ATTENTION=1`),
  quantized KV cache (`OLLAMA_KV_CACHE_TYPE=q8_0`), and single-model constraints.
  Optimizations reclaimed 1.81 GB VRAM (reducing peak usage from 15.23 GB to 13.42 GB)
  and yielded a 50% to 70% speedup (up to ~59 tok/sec) and a 12-14% decrease in TTFT.
  Windows logon fixture `GoodQ4All Ollama Fallback Startup` invokes the same wrapper.

## Clean-Start Checkpoint

Read `docs/agent/workflows/CLEAN_MEMORY_START.md` before deleting or rerunning
memory surfaces.

Tracked cleanup audit summary:

- `docs/diagnostics/MEMORY_CLEAN_START_AUDIT_2026-05-20.md`
- `docs/diagnostics/POWER_LOSS_INGESTION_AUDIT_2026-05-20.md`
- `docs/diagnostics/HOME_MEMORY_WITNESS_RUN_2026-05-22.md`

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
- Active API status on port `30000` is bound to the
  `epoch_2026_05_29_family_clean_01` epoch. It currently reports the onboarding
  verification run (1 video, 1 scene) under a completely fresh, wiped blank slate.

Latest full home-memory validation epoch:

- `epoch_2026_05_29_family_clean_01`

The active validation epoch uses these Qdrant collections:

- `goodq_clip_epoch_2026_05_29_family_clean_01`
- `goodq_dino_epoch_2026_05_29_family_clean_01`
- `goodq_text_epoch_2026_05_29_family_clean_01`
- `goodq_audio_epoch_2026_05_29_family_clean_01`

This epoch now contains runtime fallback, WSL audio, sentiment, entity, Qdrant,
FAISS, Operator Console freshness validation, and runtime problem-scope
evidence. It is useful for audit and UI verification, but it must not seed the
next broad personal-memory pass unless the operator deliberately keeps this
scope. The previous `_01`, `_02`, `_03`, `_04`, ten-scene, and runtime fallback
probe attempts also contain validation or partial probe residue and must not be
treated as the active full-run scope.

## Latest Full Home-Memory Validation Run

The first broad FAMILY home-memory run completed in
`epoch_2026_05_22_family_full_01`.

Scope:

- Source scope: first redacted FAMILY media file.
- Probe scope: `1` video, `141` scenes.
- Runtime run id: `364f6a6b-37fb-4613-bf06-4c2099c9e6c8`.
- Pipeline status after run: idle.
- `/api/status.processing.cli_progress`: available, status `completed`,
  active `false`, progress `100`.

Validated memory/evidence posture:

- Current-run audio proof: `140 / 141`; one optional `audio_embed_clap`
  terminal error remains visible.
- Step ledger: `2536` ok, `3` skipped, `1` error.
- Runtime step-error logs: `6` native step-error events, `5` recovered,
  `1` terminal.
- Qdrant point counts: audio `140`, text `281`, CLIP `282`, DINO `282`.
- FAISS indexes: audio, text, CLIP, and DINO are all explicit-ID
  `IndexIDMap2` indexes in the active epoch.
- SQLite memory projection: `141` scenes and `985` embeddings.
- Knowledge graph projection: `838` nodes, `2738` edges, and `141` events.
- Entity evidence: `504` total entities, `198` unique entities, and
  `120 / 141` scenes with any entity evidence.
- Sentiment: `139 / 141` sentiment labels, `140 / 141` text-emotion rankings,
  and `141 / 141` audio-emotion score rankings.
- Scene-context LLM: `137 / 141` temporal segments.
- Projection gaps: `ok`, `0` missing.
- Operator Console Evidence Surfaces expose episode errors, recovered step
  errors, step skips, vector-count scope notes, human-review audio tier, and
  home-memory privacy note.

Known follow-up from this validation:

- Native CLAP crash mitigation now preserves non-speech audio embedding
  intent: `audio_embed_clap` keeps the original audio fallback when speech VAD
  finds no speech, and a Windows native crash retries once with
  `GOODQ_CLAP_FORCE_CPU=1`.
- Validate the CLAP CPU fallback on the next scene-first or broad ingestion
  run; the completed full run still truthfully contains one pre-mitigation
  optional terminal CLAP error.
- Scene-context LLM coverage root cause was audited after the full run:
  the `4` missing temporal segments were signal-bearing, but the analyzer could
  collapse to no payload when the LLM response path failed, and caption/OCR/audio
  signal alone was not always sufficient to enter scene-context projection.
  Future runs now use a conservative grounded fallback for LLM transport,
  parse, or normalization failures and treat visual/audio evidence as eligible
  context signal. The completed full-run artifact remains `137 / 141` until the
  affected scene scope is rerun or re-harmonized.
- Retrieval audio proof and retrieval audio query are now visibly separate:
  current-run CLAP/Qdrant proof remains scene-level evidence, while the
  audio-only text-query lane uses the same pinned
  `laion/clap-htsat-unfused` embedding space. The local pinned CLAP snapshot now
  includes `model.safetensors`, and the `goodq_core` retrieval encoder returns
  nonzero 512-d query vectors instead of the prior CLAP weight-format loader
  failure.
- Keep the direct CLI progress bridge as read-only status; completed progress
  must remain non-active so the UI does not imply ingestion is still running.

## Runtime Fallback, Audio, Sentiment, And Entity Validation

A fresh three-scene probe completed in
`epoch_2026_05_22_runtime_fallback_probe_02` after installing/configuring the
Windows Ollama fallback and validating the sourced WSL audio worker.

Scope:

- Source scope: first redacted FAMILY media file.
- Probe scope: `1` video, `3` scenes.
- Runtime run id: `785b5eae-ff3e-4cae-9b64-37bbf2151a74`.
- Pipeline status after probe: idle.

Validated runtime posture:

- Local vLLM primary: healthy on `127.0.0.1:38005`.
- Windows Ollama fallback: healthy on `127.0.0.1:31434`, model
  `phi4:latest`.
- Fallback chain: `2 / 2` configured LLM endpoints healthy;
  `prefer_speed` uses vLLM, `prefer_quality` uses Ollama/Phi4.
- API `/api/status` WSL probe now checks the configured WSL audio worker, not
  plain WSL `python3`.
- WSL audio status: `available`; `faster_whisper` status: `ready`; observed
  version: `1.2.1`.

Validated memory/evidence posture:

- Current-run audio proof: `3 / 3` CLAP-ok scenes proven against run-matched
  Qdrant payloads.
- Qdrant point counts: audio `3`, text `6`, CLIP `6`, DINO `6`; all fresh
  validation collections green.
- FAISS indexes: audio, text, CLIP, and DINO are all explicit-ID
  `IndexIDMap2` indexes with expected point counts.
- Sentiment: `3 / 3` scenes have sentiment labels, text-emotion rankings, audio
  emotion scores, and audio-emotion rankings.
- Entity evidence: `3 / 3` scenes have channelized entity evidence; latest
  evidence reports `10` total and `10` unique entities.
- Ambiguous same-label person/non-person promotion was patched and retested;
  the probe now reports `0` ambiguous person/non-person label conflicts.
- Scene-context LLM evidence is present in the retrieval read model and remains
  transcript-dominant when visual/audio signals are weaker.

Known follow-up from this validation:

- Retrieval result-level audio proof explanation was polished after this
  validation: selected-scene proof now stays top-level under
  `proof_scope=retrieval_result_scene`, while run-wide mismatch diagnostics are
  nested under `collection_scope`. Strict latest-run audio proof remains green.

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
- Ollama fallback at that time: offline. This is superseded by the
  2026-05-22 runtime fallback validation above, where Windows Ollama/Phi4 is
  healthy.
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
- The old ten-scene target was `epoch_2026_05_22_family_probe_10scene_01`; the
  current completed full-run target is `epoch_2026_05_22_family_full_01`.
  Before another broad home-memory run, use a fresh epoch or reset Qdrant and
  confirm target FAISS files are absent or explicit-ID indexes.

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
- Scene context LLM evidence is present and transcript-dominant.
- Entity evidence is now projected through `/api/runs/latest/evidence` as a
  channelized envelope instead of a KG-only boolean. The active clip probe
  reports `4` total entities from the temporal index, with dialogue-mentioned
  entities, candidate-visible people, and speaker-aligned mentions surfaced
  separately from strict scene-present identity.
- The Operator Console proof/surface panels now expose entity counts, top
  dialogue mentions, candidate visible people, speaker-aligned mentions, and
  channel status. Do not collapse `scene_present=0` into "no entities"; it means
  no strict scene-present identity was proven in that scope.
- Live retrieval validation against `POST /api/search/multimodal` for the active
  clip topic returns the selected scene with entity channels and `kg_evidence`
  preserved: `4` entities, `0` strict scene-present entities, `4`
  dialogue-mentioned entities, `1` candidate visible person, and `1`
  speaker-aligned mention.
- The early realtime KG "no entities found" observation is now labeled as a
  no-input extraction pass when transcript/caption/OCR/object/tag inputs are not
  available yet. Later transcript/temporal passes can still resolve entities;
  this is no longer a total KG absence signal.

Operator Console freshness and route-id pass on 2026-05-22:

- Active validation scope:
  `epoch_2026_05_22_family_probe_10scene_01`, `10` scenes, runtime run id
  `571ee750-6a6e-4744-93a3-4bc19373d273`.
- `/api/runs/latest/preview` and `/api/runs/latest/evidence` now expose the
  processing folder id as `timeline_video_id`. For the active probe this is
  `family_probe_1987_1988_45m_15m`.
- Per-video timeline/drilldown routes should use `timeline_video_id` or the
  processing folder id, not the SQLite/video hash. A hash-route `404` is not
  data loss by itself.
- Operator Console GET reads use no-store request cache-busting, media/keyframe
  URLs are cache-bound to the current run scope, and stale selected
  video/scene/retrieval state is cleared when the API/run/video inventory scope
  changes.
- The Current Scope strip includes a Refresh item so operators can see when the
  local read surface was refreshed and that it is using the no-store boundary.
- Live post-restart validation against port `30000` reports temporal scope
  `10`, current-run audio proof `Proven` for `10 / 10` CLAP-ok scenes, entity
  evidence `54` total entities, sentiment labels for `10 / 10` scenes, and text
  emotion ranking for `10 / 10` scenes.
- Early `[ENTITY]` zero-entity messages with available partial inputs are now
  preliminary extraction notices at info level. They do not mean the late
  transcript/temporal KG pass failed.

## Visual Processing and Model Dimension Optimization on 2026-05-27

A complete visual pipeline and model dimension optimization run was completed, upgrading core visual embeddings (CLIP and DINOv2) to higher-fidelity variants and vectorizing scene processing for maximum GPU efficiency.

Optimizations implemented:
- **Model Upgrades**: CLIP was upgraded from base to `openai/clip-vit-large-patch14` (expanding vectors from 512 to 768 dimensions). DINOv2 was upgraded from base to `facebook/dinov2-large` (expanding vectors from 768 to 1024 dimensions). Config and registry schemas are updated dynamically to support these dimensions.
- **Vectorized GPU Scene Detection**: Migrated `gpu_scene_detect.py` to use batched CUDA PyTorch mean absolute difference calculations, reducing CPU-GPU sync calls to one per batch.
- **OpenCV-Native Seeking**: Upgraded `scene_frame_extractor.py` to seek and decode keyframes natively using `cv2.VideoCapture` in Python, significantly reducing subprocess overhead. FFmpeg remains a structured fallback.
- **Advanced Keyframe Selection**: Keyframe extraction now ranks candidate frames in each scene using Shannon entropy (texture density), Laplacian variance (sharpness), and motion peaks (visual change).
- **Mixed-Precision (AMP) Batching**: Streamlined visual embedding generation in `scene_embedder.py` by pooling and flattening frame extraction tasks into a single batch processed under mixed-precision FP16 AMP and inference mode.

Validated memory/evidence posture:
- **Validation Run**: Executed end-to-end on `samples/onboarding_fixture.mp4` under the new posture. The visual embedding phase completed in 5.7 seconds on the RTX 4070 Ti SUPER.
- **Vector Parity**: Fresh Qdrant collections initialized with upgraded dimensions: CLIP (768) and DINOv2 (1024).
- **FAISS Parity**: FAISS indices successfully committed vectors using explicit, stable IDs with expected dimensions (`faiss_ok = true`).
- **OpenMP Collision Mitigation**: In pipelines, `KMP_DUPLICATE_LIB_OK=TRUE` is explicitly set to prevent duplicate OpenMP library crashes during torch/faiss imports.

## Ingestion Pipeline and Concurrency Optimization on 2026-05-31

A complete performance, retrieval, and VRAM optimization cycle was completed to harden the relational and vector database systems under concurrency.

Optimizations implemented:
- **Hybrid Retrieval + FTS5 RRF Blending**: Registered FTS5 virtual tables inside SQLite `memory.db` for full-text transcripts and frame OCR data, blended with Qdrant vector retrieval scores using Reciprocal Rank Fusion (RRF).
- **Summary Vector Indexing**: Encoded theme-synthesized scene summaries into 384-dimensional SentenceTransformer embeddings, routed to explicit FAISS/Qdrant collection targets under dynamic dimension validation checks.
- **Heartbeat VRAM Allocator**: Programmed a process-safe locking system mapping PID reservations and Heartbeat timestamps to prevent OOM errors on concurrent deep learning steps, routing dynamically to CPU-safe overrides when VRAM thresholds are breached.
- **Failure Isolation**: Intercepted single-frame load errors in batch CLIP/DINO inference, falling back to individual frame decodes and enforcing strict numpy verification to isolate pipeline failures.
- **Async DAG Ingestion Loop**: Migrated the orchestrator to an asynchronous DAG process utilizing gather-level concurrency for non-dependent steps, serializing index database writes under asyncio locks to eliminate database locking errors.
- **CI Test Isolation**: Injected autouse pytest database isolation fixtures, mocking relational SQLite schemas and vector targets to allow clean CI test execution without local directory residue.

## Progressive Chunk Ingestion & Recovery Checkpointing on 2026-06-01

The ingestion loop was evolved from full-file batch ingestion to a timeline-sliced progressive ingestion architecture.

Features implemented:
- **Sliding Windows**: Added CLI parameters (`--chunk-size` and `--chunk-overlap`) to partition media files deterministically into progressive analysis windows.
- **Recovery Checkpoints**: Updates to a durable `progressive_ingestion_state.json` track committed window indices. On orchestrator restarts, completed windows are bypassed, resuming from the first uncompleted window.
- **Deduplication Scene Guard**: Configured the orchestrator to bypass database scene list reuse if a progressive checkpoint file exists, loading the complete scene boundaries from the authoritative segmentation cache instead.
- **Sequential-Progressive Parity Check**: Validated sequential and progressive ingestion paths on `samples/onboarding_fixture.mp4`, generating `progressive_parity_report.json` to confirm exact database, Qdrant, and KG node alignment.

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

1. Run the setup installer `GoodQ4All_Setup_1.0.0.exe` to deploy on a clean follower machine (laptop).
2. Test watchdog folder drop events under progressive chunk parameters.
3. Validate search blending results via `/api/search/temporal` using the local Retro UI.

