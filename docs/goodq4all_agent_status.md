<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-04-08 -->

# GoodQ4All Agent Status

_Generated: 2026-04-08T07:35:00_

This document is a generated operator snapshot of the current stitching-era and offline-package baseline.
Treat per-run artifacts and canonical runtime contracts as source of truth for live claims.

## System Mode
- MODE: Operational / Packaging / Hardening
Audit Status: ACTIVE (2026-04-08)

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
- Active 5-episode witness: `reports/fresh_ingest_runs/20260403_133244_season1_offline_package_witness/`
- Run id: `59ba9343-881f-4ceb-b625-3fbed5a59fd4`
- Launch commit: `e880c9e`
- Current observed state: completed successfully across all 5 episodes; Phase 6a and Phase 6b passed, `scene_ingest_results.json` was written, and Qdrant stayed healthy with CLIP + DINO vectors committed
- Current run seams: repeated non-fatal `[ENTITY] No entities found...` lines for weak vision-only scenes, 2 contained `image_embed_dino` native crashes recovered via `gpu_amp_disabled`, and 2 optional `audio_embed_clap` failures

## Current Benchmark
- Fully monitored 2-episode rerun: `../scratch/debug_runs/two_episode_baseline_verify_monitored_20260408/`
- Run id: `c0ee39ca-7ad0-467a-af5e-d9c4a0837c70`
- Current observed state: completed successfully across `01x01` + `01x02`; the earlier witness-shell false-stop was ruled out as a monitoring artifact, not a pipeline regression
- Fresh perception wiring now visible in canonical outputs:
  - `visible_person_object_count`
  - `audio_emotion`
  - `music_events`
  - `time_hints`
  - `speaker_voice_signature_count`
- Semantic state:
  - `candidate_visible_people` remains conservative / empty
  - `conversation_owner` remains intentionally unpromoted pending further interaction-ownership work

## Active Season Benchmark
- Active 5-episode witness: `reports/fresh_ingest_runs/20260408_070502_season1_main_benchmark_witness/`
- Run id: `420ba9d8-31f7-4614-934f-0ad8eddfd631`
- Launch commit: `31fd533`
- Current observed state: in progress on `main`; benchmark is intended as the first season-scale comparison point after the monitored 2-episode baseline restoration and perception wiring fixes
- Current checkpoint:
  - `01x01` is actively processing
  - stderr remains limited to the familiar non-fatal `[ENTITY] No entities found...` lines on weak caption/object-only scenes
  - no new ingestion regression has surfaced

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
- Launched the first full 5-episode benchmark witness from pushed `main` so desktop and laptop summaries can be compared against the same benchmarked branch state.

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
