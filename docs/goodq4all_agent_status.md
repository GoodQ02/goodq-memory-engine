<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-05-08 -->

# GoodQ4All Agent Status

_Operational restart checkpoint aligned: 2026-05-08._

This document is a bounded operator snapshot of the current release-era
stitching and offline-package baseline.

Use canonical runtime contracts and released evidence surfaces as source of
truth for live claims. Do not treat this document as a live witness monitor.

## Current Restart Checkpoint
- Pause checkpoint, 2026-05-08:
  - latest runtime/source fixes on `main`:
    - `3a06342` (`fix: load runtime pyannote from canonical cache`)
    - `86f032d` (`fix: align image step gpu budget mapping`)
  - same fixes are mirrored to `public`:
    - `e2e0b9d` (`fix: load runtime pyannote from canonical cache`)
    - `2a7b918` (`fix: align image step gpu budget mapping`)
  - laptop `GPU_ENHANCED` one-scene witness `20260508_104105_laptop_gpu_enhanced_one_scene_witness` completed with run id `02fdd2d9-7868-442b-8628-2550ed976820`
  - witness passed bootstrap/preflight, WSL torch lane `2.5.1+cu121`, Qdrant reachability, WSL audio execution, transcript persistence, CLAP/audio embedding, text embedding, Phase 6a/6b, `phase6_complete=true`, and `qdrant_ok=true`
  - witness found live runtime PyAnnote still needed the canonical HF cache dir in `wsl2_audio/process_audio.py` and `wsl2_audio/audio_service.py`; `3a06342` patches both runtime loaders
  - witness found laptop image-caption OOM was consistent with the active `scripts.gpu_config` map missing image-step budgets; `86f032d` aligns image-caption/DINO/CLIP budgets with the canonical vision step contract
  - remaining watch item: WSL-side Wav2Vec emotion/embedding enrichment reports `transformers not installed`; this is optional and should be handled as a future package-lane audit, not folded into the runtime cache or GPU-budget patches
- Pause checkpoint, 2026-05-07:
  - latest local docs-clearance commit: `103b17f` (`docs: add documentation forensics index`)
  - docs folder is now indexed for future agent lookup through `docs/reference/indexes/DOCS_FORENSICS_INDEX.md`
  - every active Markdown/text doc under `docs/` has an explicit `DOC_STATUS` marker as of the docs-clearance pass
  - the old WSL audio emotion sample output was preserved as `docs/archive/diagnostics/wsl2_audio_emotion_sample_output.json`; treat it as a historical diagnostic relic, not current runtime truth
  - only expected untracked local artifacts at pause were recurrence report artifacts under `reports/control_recurrence/`
  - immediate next action after pause: analyze the incoming laptop bootstrap audit before continuing project-root cleanup
- Current local workspace:
  - `main` / `origin/main` are the active source line; confirm the exact head with `git log -1 --oneline`
  - source includes WSL runtime PyAnnote cache-dir loading and image-step GPU budget alignment through `86f032d`
- Current public-facing branch:
  - `public` / `origin/public` includes the public-safe WSL runtime cache-dir and image-step GPU budget fixes through `2a7b918`
- Current state:
  - Full Season 1 recompare witness completed successfully across `01x01` through `01x05`
  - Full Season 2 fresh witness completed successfully across `02x01` through `02x12`
  - Read-only operator package is restored and shipped:
    - `lib/run_index.py`
    - `lib/run_summary.py`
    - `GET /api/runs/latest/preview`
  - First safe control-agent substrate is active as read-only observability:
    - `lib/control_recurrence_report.py`
    - `lib/control_recurrence_index.py`
    - `lib/control_recurrence_recommendations.py`
    - `lib/control_recurrence_trend.py`
    - `python -m cli.control_recurrence_report`
    - default durable output: `reports/control_recurrence/`
    - artifact index: `reports/control_recurrence/index.json`
    - direct canonical run roots without wrapper `experiment_log.json` are discoverable from existing output/workspace/operator-log artifacts
    - direct run discovery supports one or more videos, metadata-described output/workspace paths, and captured stdout/stderr retry evidence
    - recurrence reports now include read-only step latency evidence from existing `step_runs.jsonl` `duration_ms` rows, including p50/p95/max, slow outlier counts, timeout-boundary exceedance counts, and WSL audio timing buckets
    - shared direct-run stdout events are scoped by persisted video/scene identity before becoming recurrence signals, so multi-video direct roots do not borrow native retry evidence across episodes
    - post-seal status: `control-recurrence-v0.4.1` remains a valid sealed milestone for direct-run discoverability and truth-surface alignment; latest control recurrence tag is `control-recurrence-v0.4.2`, with current source beyond it for read-only trend mode, audio Qdrant provenance hardening, native model smoke diagnostics, shared runtime recurrence scoping, and WSL audio runtime black-box diagnostics
    - bounded direct-run discovery limits are expected when required artifacts are absent; local `reports/control_recurrence/index.json` state is workspace artifact hygiene unless explicitly tracked
    - local API read surface:
      - `GET /api/control-recurrence/reports`
      - `GET /api/control-recurrence/reports/latest`
      - `GET /api/control-recurrence/reports/trend`
      - `GET /api/control-recurrence/reports/{report_id}`
      - `GET /api/control-recurrence/reports/{report_id}/markdown`
      - `GET /api/control-recurrence/reports/{report_id}/recommendations`
    - boundary: not healing yet. Latency evidence is observer-only; it does not activate `ControlAgent`, does not enable auto-healing, does not mutate configs, does not execute commands, does not use LLMs, does not generate reports from the API, and does not touch `cli/run_ingestion.py`.
  - Exact operator examples:
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root>`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --json`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --write-md`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --write-json-file`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --trend --json`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports/latest`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports/trend`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/recommendations`
  - Upstream normalization remains in pilot state only:
    - exact pair allowlist contains exactly `Jerry Seinfeld -> Jerry`
    - projection-only instrumentation:
      - `normalization_applied`
      - `normalization_source`
    - no extraction, KG, identity ladder, retrieval, or embedding changes
  - Current next-step bias after restart:
    - keep normalization allowlist single-entry unless new proof clears the same gate
    - prefer read-only audits and copy-on-write reprojection over broad runtime changes
    - treat audio-vector success as provenance-defined: `clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and required provenance fields
    - treat legacy or stale scene-id-only audio vector presence as insufficient current-run proof
    - treat unified WSL audio as healthy but scheduling-expensive; recent controlled witnesses show about `58.2s` p50 / `62.1s` p95 per `audio_unified_wsl2` scene and roughly `61.6%` to `63.9%` of summed step duration
    - same-scene probes on 2026-05-04 found a diagnostic forced-CPU Windows transcript-only path can finish faster for sampled `02x02` scenes, but it does not produce the unified WSL diarization, emotion, speaker-count, or speaker-signature surfaces and is not an equivalent replacement
    - one-episode black-box witness `20260504_074335_wsl_black_box_02x02_witness` completed `38 / 38` `audio_unified_wsl2` rows ok, persisted `bridge_runtime_probe` on all scene results and all canonical scene-manifest scenes, and kept Phase 6/Qdrant healthy
    - that witness observed the sourced WSL worker on `torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, and `torchaudio==2.8.0+cu128`; this is recorded as `torch_lane_status=differs_from_expected`, not as an ingestion failure
    - `torchcodec_ready=false` remained visible in the recorder; the active worker succeeded through preloaded-audio handling, so this is a surfaced environment warning, not hidden success and not authorization for package mutation
    - lane classification: `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128`
    - bootstrap target remains `torch` / `torchvision` / `torchaudio` on `2.5.1+cu121`; the observed sourced WSL worker lane is `2.8.0+cu128`
    - the active lane was functionally observed through repeated no-ingestion probes and no current ingestion blocker was found from the witness, but it is not bootstrap-approved, not lane-approved for promotion, and not a package recommendation
    - promotion requires a future explicit lane-promotion audit; do not change packages, configs, source, ingestion behavior, or lockfiles from this drift classification alone

## Project-Root Audit Checkpoint (2026-05-07)
- Docs-index-guided audit status:
  - read-only audit completed using `docs/reference/indexes/DOCS_FORENSICS_INDEX.md` as the routing map
  - validation passed: docs drift lint, `git diff --check`, and the canonical test wrapper with `493` passing unit tests and `5` warnings
  - tracked source state was clean; untracked recurrence artifacts under `reports/control_recurrence/` remain workspace hygiene unless intentionally promoted
  - cache-authority fix `a1d34df` is in current main history; HF cache ref newline fix `684308a` writes generated `refs/main` files as raw commit hash bytes; WSL PyAnnote preflight cache fix `af6fff3` loads the pipeline from the canonical WSL Hugging Face cache env
- Current readiness notes:
  - Qdrant responded locally
  - WSL audio preflight returned ready with diarization ready, while retaining the observed cu128 drift lane and `torchcodec_ready=false`
  - laptop bootstrap audit confirmed the WSL audio cache-authority seam is patched forward: `facebook/wav2vec2-base-960h` is now part of the authoritative bootstrap model cache set, WSL preflight uses pinned offline revisions, and optional NRC lexicon handling matches registry optionality
  - follow-up laptop audit confirmed `18 / 18` model prefetch and pinned offline PyAnnote lookup, but default `main` offline lookup still failed when `refs/main` ended with LF; `684308a` patches that exact runtime cache-ref seam
  - latest laptop audit confirmed default offline `main` lookup and `Pipeline.from_pretrained(..., cache_dir=...)` both work when pointed at the canonical cache, but preflight itself was not passing `cache_dir`; `af6fff3` patches that exact readiness gate
  - final laptop bootstrap validation on current `main` passed: bootstrap install exited `0`, model prefetch reported `18 / 18`, WSL preflight returned `ready=true` and `diarization_ready=true`, HF refs were raw 40-byte hashes with no CR/LF, offline default and pinned lookups succeeded, and `bootstrap_validate.bat` passed
  - remaining laptop note is non-fatal persistent WSL audio service install state `PENDING_SUDO`; direct WSL audio execution is ready and the existing service process was left untouched
  - model prefetch reports should now expect `18 / 18` assets including YOLO and the WSL runtime cache gate
  - local focused verification after the preflight cache fix passed: `48` bootstrap/cache/WSL authority tests with `4` warnings
- Pause instruction:
  - next gate is one controlled `GPU_ENHANCED` scene witness on the freshly validated laptop/bootstrap state before broader ingestion
- Ranked next cleanup/audit seams:
  1. Completed: the `17` tracked `steps/*/step.py.backup_*` files beside active modules were removed after audit proved no active runtime/test consumers; `*.backup*` is now ignored.
  2. Completed: the retired root `config.json` scene-detection override and its obsolete fixer/monitor helper scripts were removed after audit proved canonical runtime config flows through `configs/config.yaml` and `steps.common.config_loader`.
  3. Completed: local repo-root scratch/workspace directories are root-ignored; do not stage local scratch contents or recurrence artifacts unless intentionally promoted.
  4. Refresh or clearly quarantine `docs/bootstrap/SCRIPT_REGISTRY.md`; it is a stale generated aid, not runtime authority.
  5. Keep default pytest on the canonical wrapper; avoid broad `pytest .` until archived script harnesses are explicitly excluded.
  6. Next source seam after cleanup triage: silent observability/provenance drops in observer, memory commit, retrieval event, provenance, API status, and audio helper paths.

## Audio Vector Provenance Doctrine
- Contract:
  - `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
- Current-run CLAP/Qdrant audio coverage requires:
  - scene audio `clap_meta.status == ok`
  - Qdrant audio payload with matching `run_id`
  - matching `scene_id`
  - matching `video_id` when available
  - required provenance fields: `run_id`, `embedding_id`, `component`, `step`, `model`, `created_at`, `commit_ts_utc`
- Non-proof states:
  - matching `scene_id` only
  - missing `run_id`
  - different `run_id`
  - legacy payload with missing provenance
  - `clap_meta.status == error`
  - `clap_meta.status == skipped`
- Witness evidence:
  - one-episode baseline `20260501_114445_audio_qdrant_provenance_02x01_witness`: `40` scenes, `40` CLAP ok, `40` current-run Qdrant audio points with provenance
  - two-episode boundary witness `20260501_153532_audio_qdrant_provenance_s2_two_episode_witness`: `78` scenes, `75` CLAP ok, `75` current-run Qdrant audio points with provenance, `2` optional CLAP errors, `1` `audio_silent` skip
- Consumer rule:
  - audits, UI, retrieval status, and recurrence reports must count current-run audio vectors by matching `run_id`, not by scene-id presence alone

## System Mode
- MODE: Operational / Packaging / Hardening
Audit Status: ACTIVE (2026-04-10)

## Phase Status
| Phase | Status | Notes |
|------|--------|-------|
| Scene Detection | ✅ Complete | Stable |
| Audio Extraction | ✅ Complete | Unified WSL worker + structured Windows fallback + explicit sub-step truth surfaces |
| Visual Captioning | ✅ Complete | Native faults surfaced as partial-scene errors |
| CLIP Embeddings | ✅ Complete | Phase 6a persisted to Qdrant |
| DINO Embeddings | ✅ Complete | Retry containment active for native crashes |
| Face Detection | ✅ Complete | Structural face evidence active |
| Knowledge Graph | ✅ Complete | Realtime inserts + identity ladder active |
| Vector Storage (Qdrant) | ✅ Wired | Port 6333 reachable |
| Phase 6b Harmonization | ✅ Operational | Epoch-scoped temporal index is canonical |
| Identity Stitching | ⚠️ Early Operational | speaker patterns and voice signatures can surface when voiced speech is stable; promotion remains conservative |
| Final Report | ✅ Available | scene_ingest_results.json is canonical run summary |

## Release-Era Witness Baseline
- Locked two-season baseline witness: `reports/fresh_ingest_runs/20260409_072106_two_season_benchmark_witness/`
- Run id: `4e35b14d-f19a-4ea4-8b4a-2213f165c6d0`
- Current observed state: completed successfully across `17` episodes with final `pipeline.ingestion` status `completed`, `processed_videos = 17`, and Phase 6 completed across the benchmark
- Canonical comparison memo: `docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md`
- Contained seams remained within the expected envelope:
  - repeated non-fatal `[ENTITY] No entities found...` lines for weak vision-only scenes
  - contained `object_detect` CPU fallbacks
  - contained `image_embed_dino` AMP-disabled retries
  - a small number of optional `audio_embed_clap` failures

## Locked Benchmark Baseline
- Two-season totals from the locked baseline:
  - `381` dialogue-entity scenes
  - `316` mentioned-people scenes
  - `131` candidate-visible scenes
  - `70` interaction-dominance scenes
  - `10` conversation-owner scenes
  - `651` audio-emotion scenes
  - `167` time-hint scenes
  - `14` music-event scenes
- The current authoritative baseline remains `epoch_2025_12_22`
- `audio.metadata_time_hints`, the modernized `scene_summarizer`, and `scene_context_llm` are post-baseline additions and should be treated as treatment features rather than part of the overnight control

## Release-Era Treatment Ladder
- Season 3 feature ladder authoritative pass roots:
  - `reports/fresh_ingest_runs/20260410_071121_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260410_164051_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260411_171418_season3_feature_ladder/`
- Treatment epoch: `epoch_2025_12_23`
- Execution model:
  - `03x01` -> `audio.metadata_time_hints`
  - `03x02` -> modernized `scene_summarizer`
  - `03x03` -> `scene_context_llm` (feature-gated; local LLM required)
- Confirmed treatment outcomes:
  - `03x01` validated `audio.metadata_time_hints` wiring with `scene_count = 40`, `phase6_complete = true`, and `qdrant_ok = true`; no file-tag metadata was present in the chunked-audio corpus, so the run is treated as an auditable no-signal pass.
  - `03x02` passed the modernized `scene_summarizer` verification with `scene_count = 39`, `summary_count = 39`, `scene_coverage = 39`, `visual_nested_proven = true`, `audio_nested_proven = true`, and `unique_ratio = 1.0`.
  - `03x03` passed the final authoritative `scene_context_llm` gate on run `20260411_171418_season3_feature_ladder` using local `vLLM` + `Qwen/Qwen2.5-0.5B-Instruct`, with `scene_count = 39`, `phase6_complete = true`, `qdrant_ok = true`, `segments_with_scene_context_llm = 36`, and `generic_context_detected = false`.
- Guardrails:
  - one feature change per run
  - local override only via `configs/config.local.yaml`
  - stop on regression before proceeding to the next feature
- Canonical treatment docs:
  - `docs/testing/SEASON3_TREATMENT_LADDER_MEMO_2026-04-11.md`
  - `docs/testing/SEASON3_FIVE_EPISODE_RUNBOOK_2026-04-11.md`
  - `docs/testing/SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md`
  - `docs/diagnostics/SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md`
  - `docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md`
- Multi-episode treatment campaign:
  - run root: `reports/fresh_ingest_runs/20260411_194713_season3_feature_ladder/`
  - scope: `03x04` through `03x08`
  - result: `5 / 5` passed
  - totals:
    - `193` scenes processed
    - `189` scenes with `scene_context_llm`
    - `97.9%` scene-context coverage
  - all five runs held:
    - `phase6_complete = true`
    - `qdrant_ok = true`
    - `generic_context_detected = false`
- Post-campaign treatment validation:
  - `03x09` authoritative self-audit witness:
    - run root: `reports/fresh_ingest_runs/20260412_140550_season3_feature_ladder/`
    - result: passed
    - metrics:
      - `scene_count = 39`
      - `phase6_complete = true`
      - `qdrant_ok = true`
      - `segments_with_scene_context_llm = 36`
      - `generic_context_detected = false`
  - canonical references:
    - `docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md`
    - `docs/diagnostics/SEASON3_EPISODE_FORENSIC_AUDIT_03x05_2026-04-12.md`

## Public Release Checkpoint
- Release checkpoint witness root: `reports/fresh_ingest_runs/20260417_163530_season3_feature_ladder/`
- Release checkpoint witness state:
  - `03x10` passed:
    - `scene_count = 40`
    - `phase6_complete = true`
    - `qdrant_ok = true`
    - `segments_with_scene_context_llm = 38`
    - `generic_context_detected = false`
  - `03x11` passed:
    - `scene_count = 40`
    - `phase6_complete = true`
    - `qdrant_ok = true`
    - `segments_with_scene_context_llm = 39`
    - `generic_context_detected = false`
- Current engineering truth:
  - `scene_context_arbitration` is now a canonical additive Phase 6 output and projected witness surface
  - the three-tier `scene_context_llm` contract (`primary_tags`, `contextual_tags`, `structural_tags`) is active and persists explicit arrays instead of `null`
  - the transcript-beat seam family on `03x10` / `03x11` is closed in the proving lane, including `Steve Pocatillo`, `alternate side`, and `rental car`
  - WSL audio readiness now requires real offline diarization loadability instead of import-and-token heuristics alone
  - successful unified audio payloads preserve `diarization_status`, `diarization_error`, `emotion_status`, and `emotion_error` instead of hiding those fields on the success path
  - speaker continuity surfaces (`speaker_count`, `dominant_speaker_id`, `speaker_voice_signature_count`) are part of the active runtime truth when stable voiced speech is present
  - local episode-reference eval now uses curated IMDb-backed anchor artifacts under `reports/reference_anchors/seinfeld/episodes/` for audit only; these anchors inform witness scoring but do not override runtime scene truth
  - the proving witness improved local episode-reference eval to `6/6` core beats and `9.0/9.0` salience
  - remaining interpretation differences are policy-level texture choices inside the three-tier model rather than blocking seams
  - canonical forensic reference: `docs/diagnostics/MEMORY_ARBITRATION_FORENSIC_AUDIT_03x10_2026-04-12.md`

## Post-Release Speaker / Continuity Validation
- Season 5 transition smoke:
  - run root: `reports/fresh_ingest_runs/20260419_144732_season5_transition_smoke/`
  - result: `05x01` and `05x02` both passed on fresh material with `phase6_complete = true`, `qdrant_ok = true`, and `generic_context_detected = false`
- Season 5 projection smoke:
  - run root: `reports/fresh_ingest_runs/20260419_191136_season5_projection_smoke/`
  - result: `05x01` and `05x02` both passed with the repaired truth surface aligned across `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`
  - observed smoke totals across both episodes:
    - `83 / 84` scenes with `speaker_count > 0`
    - `80 / 84` scenes with `speaker_voice_signature_count > 0`
    - `84 / 84` scenes with `diarization_status`
    - `84 / 84` scenes with `emotion_status`
    - `83 / 84` scenes with `dominant_speaker_id`
  - live KG activity in the smoke epoch now includes:
    - `speaker` nodes
    - `voice_pattern_match` edges
    - `identity_candidate` edges
    - `identity_supported` edges
  - practical interpretation:
    - speaker continuity is now operational in persisted output
    - cross-episode identity stitching is active but still conservative on short smokes

## Offline Package State
- Desktop machine audit: complete and preserved as rebuild input in the workspace-adjacent pack
- Offline bundle root: no validated current offline bundle is in circulation
- Machine-audit working copy: `../scratch/install_manifest/20260403_machine_audit/`
- Active rebuild plan: `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- Transport reconciliation: historical input only until the new staged payload validates
- Previous Phase 1 installer artifact: retired from circulation after stale-bundle audit
- Closure status:
  - Linux WSL audio wheelhouse: open until canonical `2.5.1+cu121` torch-family evidence is proven or explicitly marked incomplete
  - Windows wheels: rebuild input only until the new staged payload validates
  - Host payloads: rebuild input only until the new staged payload validates
- Packaging doctrine:
  - `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128` is functional drift evidence, not a package recommendation and not an offline bundle target
  - bootstrap target remains the canonical WSL audio `2.5.1+cu121` torch family
- Host parity additions now installed and wired:
  - Poppler / `pdftotext`
  - Piper + `en_US-joe-medium` voice
- Optional asset state:
  - required model cache: present locally
  - NRC lexicon: staged locally
  - dataset prefetch: active locally and growing the Hugging Face datasets cache under the local model root

## Storage & Memory Health
- SQLite (epoch-scoped memory.db): healthy
- Knowledge Graph (epoch-scoped knowledge_graph.db): healthy
- Qdrant (6333): reachable
- FAISS: enabled (secondary parity/fallback)
- Canonical artifact root: `<GOODQ_DATA_ROOT>/GoodQ_Data/epochs/<epoch>/processing/`

## Known Active Gaps
- Native vision-step crashes can still surface occasionally (`image_caption`, `object_detect`, `image_embed_dino`).
- Identity promotion is intentionally conservative; multi-episode evidence is required before stronger links appear.
- Some caption/object-rich scenes still yield no persisted person entities; continue auditing the vision-semantic seam before widening inference rules.
- Entity-noise cleanup still has a few season-level tails to inspect (`God`, `Wednesday`, `Tuesday`, `Superman`, `West`).
- `conversation_owner` remains sparse on the current short smoke and should not be treated as a primary operator-facing truth surface yet.
- `interaction_dominance` is now genuinely live, but still sparse enough that it should be treated as additive context rather than a required output lane.
- `speaker_aligned_mentions` is now exposed through the active scene/timeline read surfaces as an additive evidence lane.
- transcript/entity disagreement rollups are now exposed through timeline metadata so operator audits can isolate upstream normalization seams without changing inference behavior.
- The `GOOD-SPEED-32` WSL audio bootstrap drift issue is now fixed on `main`;
  current source pins the WSL bootstrap lane to `pyannote.audio==3.3.2` plus
  `huggingface-hub==0.35.3`, adds `facebook/wav2vec2-base-960h` to the
  authoritative bootstrap model cache set, and treats the stale
  `wsl2_audio/requirements-locked.txt` snapshot as historical only.
  Remaining laptop follow-up is host-confirmation work rather than a
  desktop-side blocker.

## Recent Notable Changes
- Added the first safe read-only control-agent substrate: a recurrence report CLI/library that groups persisted run signals, classifies recurrence families, emits deterministic operator hints, compares two run ids, and can export markdown/JSON artifacts plus an index without enabling healing or changing canonical ingestion.
- Restored `GPU_ENHANCED` desktop runtime through bootstrap-managed environment repair and verified CUDA-backed `goodq_core`.
- Restored unified WSL audio with local-first/offline model resolution, diarization recovery, and non-recursive Windows fallback.
- Recorded WSL audio scheduling doctrine: current unified WSL audio is stable and truthful, but recent witnesses show it dominates summed step time and must be budgeted explicitly for multi-episode/full-season runs; same-scene CPU transcript-only probes are faster but not surface-equivalent.
- Hardened Phase 6 and DINO runtime behavior; Qdrant scene-vector persistence is operational and explicit.
- Raised semantic quality by removing thin semantic scaffolding noise and tightening alias/noise filtering.
- Added the identity formation layer: `speaker_pattern`, `voice_pattern_match`, `identity_candidate`, `identity_supported`, `identity_evidence`.
- Removed the last active legacy launcher / WSL-toggle surfaces, collapsed compatibility adapters onto the canonical unified WSL bridge, and removed active ZenML references from runtime/bootstrap docs.
- Installed and wired Poppler + Piper for host-complete offline parity.
- Retired the stale offline bundle generation from circulation and recorded the rebuild as a GoodQ ExecPlan before creating any replacement package artifacts.
- Added the GoodQ ExecPlan protocol for restartable, high-risk, or multi-session work such as offline bundle rebuilds.
- Restored the monitored multi-episode ingestion baseline on the current branch and verified the new perception wiring in fresh epoch artifacts.
- Confirmed that interaction ownership remains an additive next-step concern rather than a reason to loosen visible-person promotion.
- Completed the first full 5-episode benchmark witness from pushed `main` so desktop and laptop summaries can be compared against the same benchmarked branch state.
- Published a compact benchmark memo with season totals and representative scene samples for cross-host comparison.
- Completed the locked 17-episode Season 1-2 baseline witness and published a compact two-season memo for control-vs-treatment comparisons.
- Added provenance-safe `audio.metadata_time_hints` surfacing into canonical scene truth and Phase 6 rollups.
- Modernized the canonical `scene_summarizer` template path to read the current nested `keyframe` and `audio` scene shape.
- Added the feature-gated additive `scene_context_llm` surface and a one-feature-per-episode Season 3 experiment ladder for isolated treatment validation.
- Proved the first clean Season 3 treatment ladder passes for `audio.metadata_time_hints`, the modernized `scene_summarizer`, and `scene_context_llm`, with local `vLLM` serving `Qwen/Qwen2.5-0.5B-Instruct` for the `03x03` interpretation run.
- Prepared the first reusable five-episode Season 3 treatment campaign path so the validated `scene_context_llm` logic can be replayed over `03x03` through `03x07` without changing the locked control epoch.
- Confirmed the first five-episode Season 3 `scene_context_llm` campaign across `03x04` through `03x08` and added a five-scene qualitative audit covering dialogue-heavy, environment-heavy, identity-adjacent, ambiguous, and low-signal scenes.
- Audited and explicitly marked secondary, deprecated, and experimental perception surfaces to reduce ambiguity before further integration work.
- Hardened WSL audio readiness and selection so ABI-degraded runtimes no longer present as healthy during bootstrap or canonical ingest selection.
- Completed the full Season 1 recompare witness:
  - witness roots:
    - `reports/fresh_ingest_runs/20260424_003250_season1_recompare_witness/`
    - `reports/fresh_ingest_runs/20260424_065027_season1_remaining_witness/`
  - totals:
    - `5 / 5` passed
    - `185` scenes
    - `179` `scene_context_llm` segments
    - `47` candidate-visible segments
    - `23` interaction-dominance segments
    - `3` conversation-owner segments
    - `70` speaker-aligned-mention segments
    - `27` transcript/entity disagreement segments
- Completed the full Season 2 fresh witness:
  - witness root:
    - `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/`
  - totals:
    - `12 / 12` passed
    - `466` scenes
    - `461` `scene_context_llm` segments
    - `84` candidate-visible segments
    - `47` interaction-dominance segments
    - `7` conversation-owner segments
    - `131` speaker-aligned-mention segments
    - `51` transcript/entity disagreement segments
- Restored the read-only operator run package:
  - `run_index` discovers structured witness roots under `reports/fresh_ingest_runs`
  - `run_summary` stitches root ledgers, per-episode ledgers, and canonical artifact pointers
  - `/api/runs/latest/preview` now exposes truthful latest-run state without reviving retired `/runs` shells
  - run-state freshness now projects a `pending` episode to `running` when lane-start artifacts already exist on disk
- Published the first exact-pair upstream normalization pilot:
  - allowlist contains exactly `Jerry Seinfeld -> Jerry`
  - applied only at the projection / reconciliation boundary in Phase 6
  - segment-level instrumentation now records:
    - `normalization_applied`
    - `normalization_source`
  - witness-proven outcome:
    - local disagreement reduction only
    - no owner drift
    - no candidate-visible drift
    - no KG or retrieval drift

## Agent Instructions (Binding)
- Treat the epoch processing tree and per-run artifacts as canonical, not historical `logs/scene_ingest` paths.
- Trust the direct unified WSL worker contract over older queue-service-era notes.
- Keep segmentation on the legacy production path until an explicit promotion decision is approved.
- Operate surgically: verify through targeted tests, witness artifacts, or focused reruns before widening scope.
- For next-session offline work, treat `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md` plus the preserved machine-audit pack as rebuild inputs. Do not treat retired offline bundle artifacts as current packaging truth.

## Read These First
- docs/HANDOFF_BASEMENT_PHASE.md
- docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md
- docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md
- docs/testing/SEASON1_SEASON2_FORENSIC_COMPARISON_MEMO_2026-04-25.md
- docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md
- docs/architecture/IDENTITY_STITCHING_CONTRACT.md
- docs/reference/WSL_AUDIO_RUNTIME.md
- docs/SCENE_MANIFEST_SPECIFICATION.md
- docs/bootstrap/REPO_GROUNDED_CLEANUP_CHECKLIST.md
- docs/architecture/SYSTEM_ARCHITECTURE.md
- docs/architecture/ARCHITECTURE_REFERENCE.md
- docs/architecture/MEMORY_STORAGE.md
- docs/architecture/components/VISION_PIPELINE.md
- docs/systems/WATCHDOG_SYSTEM.md
- docs/CONTROL_AGENT.md
- docs/PHASE6_MULTIMODAL_FUSION.md
- docs/CLI-REFERENCE.md
- docs/technical/LIB_COMPONENTS.md
