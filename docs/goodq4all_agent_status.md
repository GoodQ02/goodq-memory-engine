<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-04-27 -->

# GoodQ4All Agent Status

_Operational restart checkpoint refreshed: 2026-04-27T17:42:44_

This document is a bounded operator snapshot of the current release-era
stitching and offline-package baseline.

Use canonical runtime contracts and released evidence surfaces as source of
truth for live claims. Do not treat this document as a live witness monitor.

## Current Restart Checkpoint
- Runtime feature parity:
  - `main` -> `2e895c6` (`feat: pilot exact-pair transcript normalization`)
  - `public` -> `ed2a265` (`feat: pilot exact-pair transcript normalization`)
- Main-side docs handoff:
  - `main` -> `8fbcc7d` (`docs: refresh restart handoff checkpoint`)
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
    - `python -m cli.control_recurrence_report`
    - default durable output: `reports/control_recurrence/`
    - artifact index: `reports/control_recurrence/index.json`
    - local API read surface:
      - `GET /api/control-recurrence/reports`
      - `GET /api/control-recurrence/reports/latest`
      - `GET /api/control-recurrence/reports/{report_id}`
      - `GET /api/control-recurrence/reports/{report_id}/markdown`
      - `GET /api/control-recurrence/reports/{report_id}/recommendations`
    - boundary: not healing yet. It does not activate `ControlAgent`, does not enable auto-healing, does not mutate configs, does not execute commands, does not use LLMs, does not generate reports from the API, and does not touch `cli/run_ingestion.py`.
  - Exact operator examples:
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --json`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --write-md`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --write-json-file`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json`
    - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports`
    - `curl http://127.0.0.1:30000/api/control-recurrence/reports/latest`
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
- Desktop machine audit: complete and authoritative in the workspace-adjacent pack
- Offline bundle root: `../scratch/offline_bundle/goodq4all-offline/`
- Machine-audit working copy: `../scratch/install_manifest/20260403_machine_audit/`
- Transport reconciliation: final gap report is `HIGH` confidence with canonical + follower + Linux runtime marked complete
- Phase 1 installer artifact: `../scratch/offline_bundle/GoodQ_Installer.exe`
- Closure status:
  - Linux wheels: complete
  - Windows wheels: complete
  - Host payloads: complete
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
- The `GOOD-SPEED-32` WSL audio bootstrap drift issue is now fixed on `main`; any remaining laptop follow-up is host-confirmation work rather than a desktop-side blocker.

## Recent Notable Changes
- Added the first safe read-only control-agent substrate: a recurrence report CLI/library that groups persisted run signals, classifies recurrence families, emits deterministic operator hints, compares two run ids, and can export markdown/JSON artifacts plus an index without enabling healing or changing canonical ingestion.
- Restored `GPU_ENHANCED` desktop runtime through bootstrap-managed environment repair and verified CUDA-backed `goodq_core`.
- Restored unified WSL audio with local-first/offline model resolution, diarization recovery, and non-recursive Windows fallback.
- Hardened Phase 6 and DINO runtime behavior; Qdrant scene-vector persistence is operational and explicit.
- Raised semantic quality by removing thin semantic scaffolding noise and tightening alias/noise filtering.
- Added the identity formation layer: `speaker_pattern`, `voice_pattern_match`, `identity_candidate`, `identity_supported`, `identity_evidence`.
- Removed the last active legacy launcher / WSL-toggle surfaces, collapsed compatibility adapters onto the canonical unified WSL bridge, and removed active ZenML references from runtime/bootstrap docs.
- Installed and wired Poppler + Piper for host-complete offline parity.
- Closed the desktop offline package audit and staged the current offline bundle under `../scratch/offline_bundle/goodq4all-offline/`.
- Built the first self-extracting offline installer wrapper and staged the repo mirror into the offline bundle.
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
- For next-session offline work, treat the workspace-adjacent offline bundle and machine-audit manifests as packaging truth, not older first-pass harvest files.

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
