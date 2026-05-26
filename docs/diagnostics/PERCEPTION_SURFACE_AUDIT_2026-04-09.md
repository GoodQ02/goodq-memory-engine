<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-09 -->

# Perception Surface Audit

This memo inventories perception and interpretation surfaces that exist in the repo and classifies whether they are part of the canonical runtime, secondary but intentional, deprecated compatibility layers, or experimental / currently unwired.

Scope:
- read-only audit of step surfaces, call sites, and current pipeline entry points
- no runtime changes
- goal is to reduce "we built it but never surfaced it" drift before further integration work

## First-Pass Disposition

After the initial audit, the first cleanup pass should treat surfaces this way:

- `quarantined legacy surface`: [phase2_llm_integration.py](../../scripts/phase2_llm_integration.py)
  - keep for historical reference only
  - require explicit acknowledgement before direct execution
- `experimental, keep but mark clearly`:
  - [memory_writer.py](../../steps/common/memory_writer.py)
  - [step.py](../../steps/video_ingest/step.py)
  - [step_llm_enhanced.py](../../steps/tagger/step_llm_enhanced.py)
- `leave alone for now`:
  - segmentation `phase4_audio_processor.py` / `phase6_integration.py`
  - [scene_summarizer.py](../../steps/common/scene_summarizer.py)
  - [step.py](../../steps/audio_emotion/step.py)

This keeps the canonical runtime clear without deleting secondary compatibility surfaces that still deserve later review.

## Canonical 기준

A surface is `canonical` only if it is on the scene-centric ingestion path rooted in [run_ingestion.py](../../cli/run_ingestion.py) or in the active Phase 6 scene harmonization path rooted in [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py).

A surface is:
- `secondary` if it is still intentionally used in side workflows or compatibility flows but is not the main scene-memory path
- `deprecated` if it is retained for compatibility or watchdog coverage but superseded by newer canonical logic
- `experimental` if it exists as a script-only, draft, or proof-of-concept layer and is not part of the live canonical path

## Classification Summary

| Surface | File | Status | Why |
| --- | --- | --- | --- |
| Unified WSL audio perception | [audio_wsl2_bridge.py](../../steps/audio/audio_wsl2_bridge.py) | canonical | Main accelerated scene-audio path used by [run_ingestion.py](../../cli/run_ingestion.py) |
| Scene-centric harmonization | [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py) | canonical | Canonical Phase 6 truth surface for scene memory |
| Audio metadata | [step.py](../../steps/audio_metadata/step.py) | canonical | Step is active; metadata-derived time hints are now surfaced separately as `audio.metadata_time_hints` |
| Audio time hints | [step.py](../../steps/audio_time_hints/step.py) | canonical | Explicitly merged in scene ingestion and rolled up in Phase 6 |
| Audio music events | [step.py](../../steps/audio_music_events/step.py) | canonical | Explicitly merged in scene ingestion and rolled up in Phase 6 |
| Standalone audio emotion | [step.py](../../steps/audio_emotion/step.py) | deprecated compatibility | Registered and callable, but canonical ingestion now uses unified WSL audio emotion |
| Audio diarize WSL compatibility step | [step_wsl2.py](../../steps/audio_diarize/step_wsl2.py) | secondary | Still callable through [step_runner.py](../../cli/step_runner.py) but delegates to unified bridge |
| Unified audio compatibility step | [step_wsl2.py](../../steps/audio_ingest_unified/step_wsl2.py) | secondary | Legacy adapter around unified WSL bridge |
| Segmentation Phase 4 heavy processor | [phase4_audio_processor.py](../../steps/audio/segmentation/phase4_audio_processor.py) | secondary with dormant hooks | Used by segmentation orchestrator but richer perception hooks are still TODO |
| Segmentation Phase 6 integration | [phase6_integration.py](../../steps/audio/segmentation/phase6_integration.py) | secondary | Valid for segmentation engine, not the canonical scene-memory Phase 6 |
| Scene summarizer | [scene_summarizer.py](../../steps/common/scene_summarizer.py) | canonical but partially stale consumer | Still used by [memory.py](../../steps/common/memory.py) for summaries, but some audio assumptions predate current payload shapes |
| Video ingest and summarize | [step.py](../../steps/video_ingest/step.py) | experimental / off-path | Not on canonical ingestion path; appears to be an alternate summary/indexing flow |
| LLM context analyzer | [context_analyzer_llm.py](../../steps/common/context_analyzer_llm.py) | canonical additive / feature-gated | Safe subset now powers optional `scene_context_llm` in Phase 6 when enabled |
| Central memory writer | [memory_writer.py](../../steps/common/memory_writer.py) | experimental / draft | Explicitly marked draft and not used by canonical persistence |

## Detailed Findings

### 1. `context_analyzer_llm.py` graduated into a feature-gated additive surface

File:
- [context_analyzer_llm.py](../../steps/common/context_analyzer_llm.py)

It provides three substantial interpretation functions:
- `analyze_scene_context_llm`
- `analyze_emotional_progression`
- `build_relationship_map`

Current wiring:
- safe scene-scoped subset is now referenced by [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)
- gated behind `llm.features.scene_context_analysis`
- persisted as additive `scene_context_llm` only when enabled
- `relationships` and cross-scene interpretation remain unwired

Assessment:
- this is no longer off-path
- it is now a canonical additive interpretation layer with a deliberately narrow scope

Risk:
- future engineers may assume the whole module is canonical when only the scene-context subset is currently approved

### 2. `audio_metadata` is canonical, and metadata time hints now have a separate truth surface

File:
- [step.py](../../steps/audio_metadata/step.py)

Current wiring:
- `audio_metadata` is merged on the canonical scene path in [run_ingestion.py](../../cli/run_ingestion.py)
- the step emits `audio_meta`
- inside that payload it may also emit `tag_time_hints`

Current consumption:
- the canonical pipeline separately runs:
  - [audio_time_hints](../../steps/audio_time_hints/step.py)
  - [audio_music_events](../../steps/audio_music_events/step.py)
- `audio_meta.tag_time_hints` is promoted into `audio.metadata_time_hints`
- Phase 6 now rolls it up separately via metadata-specific counters and tops

Assessment:
- the step is active and the metadata-derived temporal surface is now wired correctly without being fused into semantic `time_hints`

Risk:
- provenance must stay separate; metadata hints should not be treated as spoken temporal evidence

### 3. Standalone `audio_emotion` is superseded, not fully retired

Files:
- [step.py](../../steps/audio_emotion/step.py)
- [audio_wsl2_bridge.py](../../steps/audio/audio_wsl2_bridge.py)

Current wiring:
- `audio_emotion` remains registered in [step_runner.py](../../cli/step_runner.py)
- watchdog still lists it in [watchdog.py](../../cli/watchdog.py)
- `memory_context_writer` still knows how to persist it in [memory_context_writer.py](../../steps/common/memory_context_writer.py)

Canonical reality:
- scene ingestion uses unified WSL audio through [run_ingestion.py](../../cli/run_ingestion.py)
- unified WSL audio already returns:
  - `emotion`
  - `emotion_scores`
  - compatibility `audio_emotion`

Assessment:
- this is a compatibility / watchdog surface, not the main current scene-memory source of emotional perception

Risk:
- if we debug "audio emotion" without checking the source surface, we can end up fixing the old step instead of the canonical one

### 4. Segmentation `phase4_audio_processor.py` contains dormant perception hooks

Files:
- [phase4_audio_processor.py](../../steps/audio/segmentation/phase4_audio_processor.py)
- [orchestrator.py](../../steps/audio/segmentation/orchestrator.py)

Current wiring:
- still used by the segmentation orchestrator

What is dormant:
- explicit TODO hooks remain for:
  - CLAP embeddings
  - audio emotion
  - music detection

Assessment:
- this is not unused
- but it is a secondary perception branch with richer hooks that are not realized in that path

Risk:
- engineers may assume "segmentation phase 4 does the full audio enrichment" when in practice those enrichments are incomplete there

### 5. Segmentation `phase6_integration.py` is valid, but not canonical scene-memory Phase 6

Files:
- [phase6_integration.py](../../steps/audio/segmentation/phase6_integration.py)
- [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)

Current wiring:
- segmentation orchestrator uses [phase6_integration.py](../../steps/audio/segmentation/phase6_integration.py)
- the canonical scene-memory truth surface uses [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)

Assessment:
- both are real
- only the latter is the authoritative scene-memory Phase 6 for current ingestion

Risk:
- "Phase 6" is overloaded in repo language and can confuse audits unless explicitly differentiated

### 6. `memory_writer.py` is a real alternate persistence layer, but still draft

File:
- [memory_writer.py](../../steps/common/memory_writer.py)

Current status:
- file header explicitly says `DRAFT - awaiting approval for integration`
- search only showed references in docs and legacy utilities
- canonical persistence instead runs through:
  - [memory.py](../../steps/common/memory.py)
  - [memory_context_writer.py](../../steps/common/memory_context_writer.py)
  - MemoryRouter / scene bundle registration

Assessment:
- this is experimental and not authoritative

Risk:
- docs or future contributors may mistake it for the active storage API

### 7. `video_ingest/step.py` is an alternate ingest-and-summary surface

File:
- [step.py](../../steps/video_ingest/step.py)

Current status:
- defines `video_ingest_and_summarize`
- search showed no runtime call sites in canonical ingestion
- contains its own summarization, FAISS, and audio-stat logic

Assessment:
- off-path / experimental
- likely useful for older or standalone workflows, not the authoritative current pipeline

Risk:
- another example of a substantial surface that can be mistaken for active ingestion logic

### 8. `scene_summarizer.py` is active, but partially stale relative to current audio payloads

Files:
- [scene_summarizer.py](../../steps/common/scene_summarizer.py)
- [memory.py](../../steps/common/memory.py)

Current wiring:
- used by `register_scene_bundle(...)` in [memory.py](../../steps/common/memory.py)
- therefore still active in canonical scene persistence

Concern:
- parts of the summarizer still expect older audio shapes, especially around `audio_emotion` as a list-oriented structure
- current canonical ingestion increasingly emits normalized fields through unified WSL audio and Phase 6 rollups

Assessment:
- canonical, but a likely candidate for future alignment work
- not unwired, just partially stale as a consumer

## Second-Pass Deep Audit: Remaining Three Surfaces

### `scene_summarizer.py`

Status:
- canonical, keep active

Why:
- imported and used by [memory.py](../../steps/common/memory.py) during `register_scene_bundle(...)`
- still used by [apply_scene_summaries.py](../../scripts/apply_scene_summaries.py)
- covered by active unit tests in [test_scene_summarizer_semantic_quality.py](../../tests/unit/test_scene_summarizer_semantic_quality.py)

What is actually stale:
- the template path still favors older nested audio payload assumptions such as `audio.audio_emotion` as a list-like structure
- `generate_scene_summary_llm(...)` still points at a raw local chat endpoint and is not part of the canonical ingestion path because [memory.py](../../steps/common/memory.py) calls `generate_scene_summary(..., use_llm=False)`

Disposition:
- do not remove
- do not treat the LLM summary path as canonical
- next likely improvement is to modernize the template summarizer against current top-level audio/emotion surfaces

### `phase4_audio_processor.py`

Status:
- secondary, intentional, keep active

Why:
- imported by [orchestrator.py](../../steps/audio/segmentation/orchestrator.py)
- exported by [__init__.py](../../steps/audio/segmentation/__init__.py)
- covered by [test_segmentation_shadow_mode.py](../../tests/unit/test_segmentation_shadow_mode.py)

What is mismatched:
- module docstring advertises full heavy audio enrichment
- implementation currently performs transcription + diarization only through the WSL bridge
- CLAP, audio emotion, and music detection remain explicit TODO hooks

Disposition:
- do not remove
- document it as a segmentation-shadow processor with dormant enrichment hooks
- if we ever invest here, either finish those hooks or narrow the description so it stops overstating current behavior

### `phase6_integration.py`

Status:
- secondary, intentional, keep active

Why:
- imported by [orchestrator.py](../../steps/audio/segmentation/orchestrator.py)
- exported by [__init__.py](../../steps/audio/segmentation/__init__.py)
- still produces a valid segmentation manifest for the segmentation engine

What makes it different from canonical Phase 6:
- it merges segmented audio artifacts into a segmentation-oriented manifest
- it is not the authoritative scene-memory harmonizer used by [cross_modal_harmonizer.py](../../steps/video/cross_modal_harmonizer.py)
- the shared "Phase 6" name is semantic drift, not runtime equivalence

Disposition:
- do not remove
- keep it clearly documented as segmentation-path Phase 6, not scene-memory Phase 6
- future cleanup should focus on naming/authority clarity, not deletion

## Recommended Next Moves

### Immediate documentation move

Create a small “surface authority” note in the architecture docs that explicitly names:
- canonical scene-memory perception path
- secondary segmentation path
- compatibility adapter surfaces
- experimental script-only interpretation surfaces

### Immediate runtime move

Do not wire everything at once.

Best first targets:
1. decide whether `tag_time_hints` should be promoted into canonical truth or retired as an internal helper
2. mark [context_analyzer_llm.py](../../steps/common/context_analyzer_llm.py) as experimental/script-only unless we intentionally adopt it
3. decide whether `memory_writer.py` should be archived, documented as draft, or explicitly excluded from authoritative docs

### What not to touch yet

- do not merge segmentation `phase6_integration.py` and scene-memory Phase 6 just because both use the same label
- do not revive standalone `audio_emotion` as canonical if unified WSL audio remains the source of truth
- do not treat [video_ingest/step.py](../../steps/video_ingest/step.py) as a live runtime path without a deliberate adoption decision

## Short Version

The repo does contain additional perception / interpretation logic beyond the live scene-memory path.

The most important classes are:
- `canonical additive but tightly scoped`: [context_analyzer_llm.py](../../steps/common/context_analyzer_llm.py)
- `secondary but intentional`: segmentation `phase4_audio_processor.py` / `phase6_integration.py`, compatibility WSL step adapters
- `canonical with provenance-preserving metadata surface`: `audio.metadata_time_hints`
- `canonical but partially stale consumer`: [scene_summarizer.py](../../steps/common/scene_summarizer.py)

That means your instinct was right: there are more surfaces here than the live benchmark path is currently using, and now we have an explicit map before making any runtime changes.
