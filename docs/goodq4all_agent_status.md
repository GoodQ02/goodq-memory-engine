<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-04-10 -->

# GoodQ4All Agent Status

_Generated: 2026-04-10T10:30:00_

This document is a generated operator snapshot of the current stitching-era and offline-package baseline.
Treat per-run artifacts and canonical runtime contracts as source of truth for live claims.

## System Mode
- MODE: Operational / Packaging / Hardening
Audit Status: ACTIVE (2026-04-10)

## Phase Status
| Phase | Status | Notes |
|------|--------|-------|
| Scene Detection | ✅ Complete | Stable |
| Audio Extraction | ✅ Complete | Unified WSL worker + structured Windows fallback |
| Visual Captioning | ✅ Complete | Native faults surfaced as partial-scene errors |
| CLIP Embeddings | ✅ Complete | Phase 6a persisted to Qdrant |
| DINO Embeddings | ✅ Complete | Retry containment active for native crashes |
| Face Detection | ✅ Complete | Structural face evidence active |
| Knowledge Graph | ✅ Complete | Realtime inserts + identity ladder active |
| Vector Storage (Qdrant) | ✅ Wired | Port 6333 reachable |
| Phase 6b Harmonization | ✅ Operational | Epoch-scoped temporal index is canonical |
| Identity Stitching | ⚠️ Early Operational | speaker patterns live; promotion remains conservative |
| Final Report | ✅ Available | scene_ingest_results.json is canonical run summary |

## Current Witness
- Locked two-season baseline witness: `reports/fresh_ingest_runs/20260409_072106_two_season_benchmark_witness/`
- Run id: `4e35b14d-f19a-4ea4-8b4a-2213f165c6d0`
- Current observed state: completed successfully across `17` episodes with final `pipeline.ingestion` status `completed`, `processed_videos = 17`, and Phase 6 completed across the benchmark
- Canonical comparison memo: `docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md`
- Contained seams remained within the expected envelope:
  - repeated non-fatal `[ENTITY] No entities found...` lines for weak vision-only scenes
  - contained `object_detect` CPU fallbacks
  - contained `image_embed_dino` AMP-disabled retries
  - a small number of optional `audio_embed_clap` failures

## Current Benchmark
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

## Active Treatment Ladder
- Season 3 feature ladder authoritative pass roots:
  - `reports/fresh_ingest_runs/20260410_071121_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260410_164051_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260411_061212_season3_feature_ladder/`
- Treatment epoch: `epoch_2025_12_23`
- Execution model:
  - `03x01` -> `audio.metadata_time_hints`
  - `03x02` -> modernized `scene_summarizer`
  - `03x03` -> `scene_context_llm` (feature-gated; local LLM required)
- Confirmed treatment outcomes:
  - `03x01` validated `audio.metadata_time_hints` wiring with `scene_count = 40`, `phase6_complete = true`, and `qdrant_ok = true`; no file-tag metadata was present in the chunked-audio corpus, so the run is treated as an auditable no-signal pass.
  - `03x02` passed the modernized `scene_summarizer` verification with `scene_count = 39`, `summary_count = 39`, `scene_coverage = 39`, `visual_nested_proven = true`, `audio_nested_proven = true`, and `unique_ratio = 1.0`.
  - `03x03` passed the first clean `scene_context_llm` gate on run `20260411_061212_season3_feature_ladder` using local `vLLM` + `Qwen/Qwen2.5-0.5B-Instruct`, with `scene_count = 39`, `phase6_complete = true`, `qdrant_ok = true`, `segments_with_scene_context_llm = 38`, and `generic_context_detected = false`.
- Guardrails:
  - one feature change per run
  - local override only via `configs/config.local.yaml`
  - stop on regression before proceeding to the next feature

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

## Recent Notable Changes
- Restored `GPU_ENHANCED` desktop runtime through bootstrap-managed environment repair and verified CUDA-backed `goodq_core`.
- Restored unified WSL audio with local-first/offline model resolution, diarization recovery, and non-recursive Windows fallback.
- Hardened Phase 6 and DINO runtime behavior; Qdrant scene-vector persistence is operational and explicit.
- Raised semantic quality by removing placeholder scaffolding and tightening alias/noise filtering.
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
- Audited and explicitly marked secondary, deprecated, and experimental perception surfaces to reduce ambiguity before further integration work.

## Agent Instructions (Binding)
- Treat the epoch processing tree and per-run artifacts as canonical, not historical `logs/scene_ingest` paths.
- Trust the direct unified WSL worker contract over older queue-service-era notes.
- Keep segmentation on the legacy production path until an explicit promotion decision is approved.
- Operate surgically: verify through targeted tests, witness artifacts, or focused reruns before widening scope.
- For next-session offline work, treat the workspace-adjacent offline bundle and machine-audit manifests as packaging truth, not older first-pass harvest files.

## Read These First
- docs/HANDOFF_BASEMENT_PHASE.md
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
