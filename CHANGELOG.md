# Changelog

This changelog tracks public-facing GoodQ4All milestones and release-readiness
checkpoints.

It is intentionally lightweight. Historical phase-by-phase notes, internal
audits, and archived release artifacts remain under [`docs/archive/`](docs/archive/)
and related canonical docs.

## [Unreleased]

## [2.5.2] - 2026-06-20

### Added
- **Central Model Registry**: Centralized all permitted model/repo IDs inside `configs/model_registry.yaml` and `steps/common/model_provisioner.py`. Prevents loading arbitrary un-registered models and secures concurrent loader threads using a 5-minute timeout file locking mechanism.
- **WSL2 Offline Caching Helper**: Added `wsl2_audio/model_cache.py` shared caching helper to scan environmental cache routes (`GOODQ_MODEL_CACHE_ROOT`, `TORCH_HOME`, `HF_HOME`, `HUGGINGFACE_HUB_CACHE` / `HF_HUB_CACHE`, and user home `~/.cache`) inside WSL2, resolving and loading Silero VAD locally.
- **Redacted Env Logging**: Masked active environment tokens (e.g. `HF_TOKEN` / `PYANNOTE_TOKEN`) on WSL2 service startup.

### Fixed
- **System Encoding crash protection**: Forced watchdog and direct ingestion JSON file readers to use explicit `encoding='utf-8'` (preventing CP1252/Charmap decoder crashes on Windows).
- **WSL Staging Sync**: Registered `model_cache.py` as a staged asset in `bootstrap_install.py` to prevent import failures inside the WSL environment.

## [2.5.1] - 2026-06-18

### Fixed
- **KG Dematerialization**: Replaced unsafe `scene_id LIKE 'scene_%'` wildcard
  in `_dematerialize_active_views` with parameterized `video_hash` + `file_path`
  + `scene_ids` IN-list query. The LIKE clause could match scenes from other
  videos and failed entirely for hash-based scene IDs. (commit `a28d5348`)

## [2.5.0] - 2026-06-18

### Added
- **Governed Materialization Bridge**: First full materialization bridge from
  promoted UCF evidence into active relational and graph views. Ingestion writes
  only to `ucf_ledger.db` (staged) and Qdrant (staged); `memory.db` and
  `knowledge_graph.db` are populated only on promotion via `MiniAgentClient`
  tool path. (commit `46f07c3e`)
- **Ingestion Isolation**: `ingestion_isolation: true` config flag ensures zero
  active memory/KG writes during ingestion.
- **Provenance Mapping**: `ucf_provenance_mapping` table traces every active
  materialized record back to UCF evidence.
- **Search Visibility Lifecycle**: Active search returns only promoted evidence;
  staged, validated, rejected, and superseded are excluded.
- **Support-Aware Dematerialization**: `supersede_ucf_frames` deactivates
  materialized records while preserving UCF evidence with `superseded` status.
- **Materialization Run Manifest**: Promotion produces a persistent manifest
  with frame counts, record counts, KG statistics, and error/warning lists.

### Verified
- 9-phase smoke test on Seinfeld S01E01 clip (2 min): 4 scenes, 115 UCF frames,
  32 Qdrant points, 22 pipeline steps audited, 14/14 UCF validation categories,
  full lifecycle (staged → validated → promoted → superseded), idempotency clean.

### Fixed
- **Qdrant Lifecycle Coverage** (Phase 0.9): All 7 Qdrant write paths now include
  `ucf_promotion_status: "staged"` at point creation time, achieving 100%
  lifecycle coverage. (commits `99943a19`, `c9a7b50d`, `430efa08`)

### Added
- Closed the 2026-05-17 first-time user audit gaps for prerequisite/host
  framing, local env template guidance, root scratch inbox hygiene, sample
  fixture expectations, Qdrant readiness messaging, and WSL distro fallback
  alignment.
- Added the 2026-05-17 visual first-run command-card surface, guided demo
  guide, and public/profile mirror alignment for the onboarding film.
- Documented the post-seal audit result for `control-recurrence-v0.4.1`:
  the tag remains a valid sealed milestone, while current `main` is beyond it
  with `control-recurrence-v0.4.2` plus retry attribution/coalescing
  tightening.
- Published the `control-recurrence-v0.4.2` operator release note:
  [`docs/releases/CONTROL_RECURRENCE_v0.4.2.md`](docs/releases/CONTROL_RECURRENCE_v0.4.2.md).
- Hardened direct canonical recurrence mapping for multi-video direct run roots,
  operator metadata output/workspace fallbacks, stderr-only recovered native
  retry visibility, and explicit markdown-only index warnings.
- Published the `control-recurrence-v0.4.1` operator release note:
  [`docs/releases/CONTROL_RECURRENCE_v0.4.1.md`](docs/releases/CONTROL_RECURRENCE_v0.4.1.md).
- Extended read-only control recurrence reporting to direct canonical
  `cli.run_ingestion` run roots that do not have wrapper `experiment_log.json`
  ledgers, using existing output/workspace/operator-log artifacts only.
- Published the `control-recurrence-v0.4.0` operator release note:
  [`docs/releases/CONTROL_RECURRENCE_v0.4.0.md`](docs/releases/CONTROL_RECURRENCE_v0.4.0.md).
- Added the read-only deterministic control recurrence recommendation draft
  surface for existing durable recurrence JSON reports. This includes
  `--recommendations-for <report_id>` and
  `GET /api/control-recurrence/reports/{report_id}/recommendations`.

### Boundary
- The post-seal audit found no recurrence-layer boundary violation. Local
  `reports/control_recurrence/index.json` state is workspace artifact hygiene
  unless it is explicitly tracked as a repo surface.
- The v0.4.2 hardening pass remains read-only. It expands artifact discovery
  only; it does not trigger ingestion, generate reports from the API, heal,
  mutate configs, use LLMs, or activate `ControlAgent`.
- The v0.4.1 direct-run map does not generate reports unless explicitly asked,
  does not trigger ingestion, does not import or activate `ControlAgent`, and
  does not create a second execution path.
- The v0.4.0 recommendation draft layer does not activate `ControlAgent`, heal,
  mutate configs, execute commands, use LLMs, generate reports from the API,
  trigger ingestion, or touch `cli/run_ingestion.py`.

## [0.1.1] - 2026-04-17

Reference checkpoint:
[`docs/releases/RELEASE_0.1.1.md`](docs/releases/RELEASE_0.1.1.md)

### Changed
- Published the scene-context interpretation hardening batch after the proving witness on `03x10` and `03x11` closed cleanly at `reports/fresh_ingest_runs/20260417_163530_season3_feature_ladder/`.
- Added the additive `scene_context_arbitration` read model to canonical Phase 6 outputs and run-result projection surfaces without breaking the existing `context_tags` compatibility field.
- Formalized the three-tier `scene_context_llm` contract with `primary_tags`, `contextual_tags`, and `structural_tags`, and tightened low-signal scene handling so tier fields persist as explicit arrays instead of `null`.
- Hardened transcript-topic recovery in `scene_context_llm` so transcript-rich scenes stop flattening to weak setting labels when the episode beat is explicit in dialogue, including the repaired `Steve Pocatillo`, `alternate side`, and `rental car` seam family.
- Hardened Phase 6b harmonization to tolerate legacy or malformed tier payloads safely, preventing `NoneType` tier-field crashes while preserving the canonical explicit-array write shape.
- Added a local episode-reference evaluation lane using curated IMDb-backed anchors under `reports/reference_anchors/seinfeld/episodes/` for witness scoring only; these anchors inform beat coverage and salience evaluation without overriding runtime scene truth.
- Promoted the proven iterative repair loop into canonical agent doctrine and tied it back to the ingest orchestration contract so future pipeline fixes stay seam-first, contract-preserving, and witness-driven.

### Validated
- The proving witness closed cleanly on both `03x10` and `03x11`, with Phase 6a and Phase 6b completing successfully and `generic_context_detected = false` on both episodes.
- The local episode-reference eval on the proving witness improved from `5/6` core beats and `8.25/9.0` salience to `6/6` core beats and `9.0/9.0` salience.
- Canonical manifests now persist the three-tier `scene_context_llm` payload without null tier arrays across the audited `03x10` / `03x11` proving lane.

### Notes
- Remaining interpretation differences are policy-level texture choices inside the three-tier model, not blocking seams. Examples include contextual memory cues such as `Clear Blue Sky` and lightweight structural cues such as `table`.

### Included Groundwork
- Added a next-layer implementation plan that maps existing repo scaffolding for self-auditing cognition, memory arbitration, and episode/season consolidation so the next roadmap can extend validated epistemic surfaces instead of inventing a parallel architecture.
- Added a supplemental five-scene Season 3 audit covering dialogue-heavy, environment-heavy, low-signal, identity-adjacent, and ambiguous scenes so the campaign now has both batch-level and sample-level proof.
- Closed the Season 3 treatment ladder into an authoritative three-step pass set, documenting the validated `03x03` `scene_context_llm` result against local WSL `vLLM` with `Qwen/Qwen2.5-0.5B-Instruct` and publishing a five-episode campaign runbook for the next treatment expansion.
- Locked and documented a full 17-episode Season 1-2 baseline witness, publishing a compact two-season benchmark memo with the strongest control metrics and representative scene samples for laptop-side review.
- Added provenance-safe `audio.metadata_time_hints` surfacing so metadata-derived temporal cues now persist separately from semantic `time_hints` and can be validated independently.
- Modernized the canonical template `scene_summarizer` to read the current nested `keyframe` and `audio` scene shape instead of relying on stale top-level fields.
- Added the feature-gated additive `scene_context_llm` surface and a one-feature-per-episode Season 3 feature ladder script for isolated treatment validation in a new epoch.
- Validated the first clean Season 3 treatment ladder passes: `03x01` proved `audio.metadata_time_hints` wiring as an auditable no-signal corpus case, `03x02` passed the modernized `scene_summarizer`, and `03x03` passed `scene_context_llm` against local WSL `vLLM` serving `Qwen/Qwen2.5-0.5B-Instruct`.
- Hardened `scene_context_llm` grounding with explicit evidence priority, dry operator-note output rules, monologue/low-signal fallbacks, generic-tag suppression, and transcript-topic normalization so treatment runs stop inventing social events and unsupported roles.
- Audited perception surfaces and explicitly marked legacy, secondary, experimental, and canonical interpretation paths to reduce repo ambiguity before further integration work.
- Published a compact Season 1 benchmark memo from the completed 5-episode `main` witness, including season totals, representative interaction/visual samples, and comparison guidance for cross-host validation.
- Started a clean season-scale benchmark witness from `main` commit `31fd533` after restoring the monitored 2-episode ingestion baseline, creating a benchmarkable proof surface for laptop-side comparison.
- Restored the fully monitored 2-episode ingestion baseline after the witness-shell false-stop investigation, proving the core multi-episode pipeline remains healthy and benchmarkable from `main`.
- Wired stranded perception surfaces into Phase 6 outputs so fresh scene/temporal artifacts now expose visible person-object counts, audio emotion, music events, time hints, and speaker voice-signature coverage.
- Removed the last active legacy launcher and queue-era WSL toggle surfaces, collapsed compatibility adapters onto the canonical unified WSL bridge, and removed active ZenML references from the maintained runtime/bootstrap surface.
- Installed and wired Poppler / `pdftotext` plus Piper + `en_US-joe-medium` for host-complete offline parity, including explicit GoodQ tool-path resolution for Piper.
- Closed the desktop offline package audit into a canonical machine-audit set and staged a workspace-adjacent offline bundle containing Conda payloads, Windows/Linux wheelhouses, model caches, binaries, installers, and the exported WSL distro.
- Launched a fresh five-episode offline-package witness run from commit `e880c9e` to confirm the packaged host/tool/model state still reproduces the current ingestion pipeline.
- Restored the desktop `GPU_ENHANCED` runtime through bootstrap-managed environment repair, bringing `goodq_core` back onto a CUDA-backed stack and revalidating the canonical bootstrap path.
- Restored the unified WSL audio path with local-first/offline model resolution, diarization recovery, per-scene non-recursive Windows fallback, and explicit backend truth persisted in scene artifacts.
- Hardened Phase 6 and scene-level runtime resilience: Qdrant scene-vector persistence is explicit, DINO native crashes are contained through staged retry/fallback behavior, and per-run results remain truthful under partial-scene failures.
- Raised semantic quality and identity readiness by removing placeholder scaffolding, tightening alias/noise filtering, adding per-speaker voice signatures, and introducing the conservative identity stitching ladder (`speaker_pattern`, `voice_pattern_match`, `identity_candidate`, `identity_supported`, `identity_evidence`).
- Realigned the active documentation surface around epoch-scoped artifacts, the direct WSL worker contract, the stitching-era architecture, and the current agent/operator read order.
- Switched supported step-env provisioning back to the pinned lock recipes under `envs/locks/`, added per-env smoke validation during bootstrap, hardened step subprocesses against user-site package leakage, and rebuilt the `goodq_face_embed` recipe around Conda `dlib` plus a portable pip-native lock set.
- Bound `scripts/bootstrap_validate.bat` to the canonical `goodq_core` interpreter for verification and pytest instead of the ambient shell Python, added explicit `pdftotext` / Poppler readiness checks to bootstrap verification, and corrected the isolated step runner to launch `python -m cli.step_runner` from the repo root instead of the non-importable `goodq4all.cli.step_runner` path.
- Restored the live image/audio/text step routing to the supported specialized env boundaries where `goodq_core` did not actually carry the full dependency stack, and taught bootstrap to provision that step-env pack in one shot for full pipeline capability.
- Archived the last small pack of phase-era validation and operator helper scripts, including the retired command-center dashboard, phase control-agent harnesses, quick GPU setup helper, and one-off audio/VAD probes.
- Realigned active runbooks and quick-reference docs to the maintained status/readiness surfaces: `cli.system_status`, `scripts/system_readiness_check.py`, `scripts/utils/check_watchdog_status.py`, and the current GPU setup flow.
- Relaxed the WSL-audio strict override guard to use the documented `GOODQ_WSL_USER` fallback chain instead of requiring an explicit env var, and made the WSL audio metadata tests deterministic against host profile/env leakage.
- Routed pytest temp and cache state into a dedicated repo-local `.pytest_tmp/` workspace to reduce Windows temp cleanup and cache-permission noise during local validation runs.

- Ongoing doc cleanup and archive alignment around the remaining historical
  surfaces.
- Archived historical test harnesses and obsolete validation helpers out of the
  active `tests/` and `scripts/` surfaces, while keeping the canonical unit
  suite and current manual watchdog/LLM/WSL/GPU utilities in place.
- Rewrote the remaining agent/recovery and cleanup-map docs to match the
  current conditional Control Agent contract instead of the older phase-era
  self-healing narrative.
- Archived the remaining browser-UI/dashboard proof-of-concept docs under
  `docs/archive/proof_of_concept/ui/` and removed them from the active support
  surface.
- Rewrote `docs/guides/general/SCRIPTS_GUIDE.md` and
  `docs/guides/CONSOLIDATION_EXPLAINED.md` so they match the current launcher,
  bootstrap, and hybrid env contract instead of the older dashboard and
  single-env narratives.
- Corrected `docs/architecture/ARCHITECTURE_REFERENCE.md` so it reflects the
  explicit local API surface, experimental-only UI scaffold, and the supported
  specialized step-env pack.
- Corrected the specialized step-env pins for `goodq_image_caption` and
  `goodq_audio_embed` so bootstrap no longer tries to resolve incompatible
  `numpy==2.2.6` combinations on fresh machines.
- Hardened Phase 6 reruns so existing extracted frames are safely reused or atomically replaced, restored a real default step timeout when `--step-timeout` is omitted, preserved prior `phase6_*` manifest truth during reruns, and normalized quoted directory-style `GOODQ_FFMPEG_EXE` overrides to a concrete executable path.
- Normalized scene-local transcript segments onto scene-absolute timelines before memory/Phase 6 processing and preserved explicit `0.0` segment starts so rerun warnings like `start=928.68, end=1.84` no longer appear.
- Made `progress.json` truthful for real ingest runs by updating it through scene processing and Phase 6 milestones and marking successful or failed completion explicitly.
- Changed CLAP audio embedding readiness to report a structured `model_not_cached` unavailable state with a repair hint instead of surfacing a misleading generic Hugging Face-style load failure, and taught bootstrap to optionally prefetch the required local model cache for offline-ready ingest.
- Model-cache prefetch now streams live console progress and retries transient download failures automatically so bootstrap no longer appears idle during large first-run model downloads.
- Bootstrap model prefetch now uses `configs/model_registry.yaml` as the actual Hugging Face download manifest, which fixes stale hardcoded model ids such as `pyannote/speaker-diarization@2.1` and ensures required registry entries like PyAnnote segmentation are staged consistently.
- Bootstrap now hands the canonical Qdrant storage/log paths directly into the service installer and waits briefly for the service to come online after installation, reducing fresh-machine failures across the UAC elevation boundary.
- Corrected the `dslim/bert-base-NER` pinned revision in `configs/model_registry.yaml` and added a registry sanity check so placeholder 40-character hashes are caught before they can break clean-machine model prefetch again.

## [0.1.0] - 2026-03-20

Reference checkpoint:
[`docs/releases/RELEASE_0.1.0.md`](docs/releases/RELEASE_0.1.0.md)

### Release Highlights

- Fresh-machine Windows bootstrap is now a supported path through
  `python scripts/bootstrap_install.py`.
- The active release surface is aligned around the canonical local API, CLI,
  watchdog, bootstrap, and persisted runtime artifacts.
- `BASELINE` remains CPU-safe by default while GPU/WSL acceleration stays
  additive and optional.
- The API contract is aligned around loopback host `127.0.0.1` and port
  `30000`.
- Qdrant is handled consistently as a Windows service-first dependency.
- Forward-facing docs, quick references, and support indexes were rewritten to
  reflect the real launcher/API/watchdog contract.
- Large legacy clusters were retired or archived from the active support
  surface, including obsolete UI scaffolding, legacy orchestration surfaces,
  process-manager residue, and raw vLLM direct-start helpers.
- Second-wave historical docs were quarantined out of the active support
  surface, with current GPU/LLM/WSL/Watchdog indexes and technical refs
  retargeted to canonical docs or explicit archive paths.
- Documentation governance now guards against active drive-root drift,
  corrupted characters, and generated snapshots that overclaim authority.

### Validation

- Local CI-equivalent baseline passed with `python -m pytest -q`.
- Active documentation governance lint passed with
  `python scripts/docs/doc_drift_lint.py`.
- Fresh laptop bootstrap succeeded after bootstrap hardening.
- Forced-ingest runtime sanity validation succeeded after the Windows audio
  fallback repair.

## [2026-03-10] Public Readiness Checkpoint

Tag: `public-readiness-2026-03-10`

### Added

- Portable bootstrap installer entrypoint via
  [`scripts/bootstrap_install.py`](scripts/bootstrap_install.py)
- Public install environment definition in
  [`environment.yml`](environment.yml)
- Baseline GitHub Actions CI and CodeQL workflows under
  [`.github/workflows/`](.github/workflows/)
- Root public changelog for release-facing milestones

### Changed

- Sanitized public configuration surface with example/local override patterns
- Public docs aligned to the canonical runtime surface and bootstrap path
- API/package/public-doc version reporting unified around a single shared
  version constant
- Launcher isolation defaults aligned to `PYTHONNOUSERSITE=1`
- API CORS defaults tightened to config-gated localhost-only behavior
- Qdrant vendor config now binds to `127.0.0.1` by default

### Removed From Public Surface

- Private runtime snapshots and machine-local report artifacts
- Copyright-sensitive Seinfeld-derived text artifacts
- Tracked env-style local files in favor of example/template variants

## [2026-03-09] Season 1 Witness Baseline

Tag: `season1-witness-run-2026-03-09`

### Added

- Formal witness-run publication bundle for the five-episode control set
- Clean-release experiment summary in
  [`docs/experiments/SEINFELD_EXPERIMENT_SUMMARY.md`](docs/experiments/SEINFELD_EXPERIMENT_SUMMARY.md)

### Validated

- `185` scenes processed across Season 1 control media
- `182/185` transcript-bearing scenes
- `0` processing-error scenes
- WSL audio effective across all witness scenes
- Typed KG and vector persistence preserved under clean reruns

## Historical Notes

- Older internal milestones and phase reports remain archived under
  [`docs/archive/`](docs/archive/).
- Legacy runtime tags remain in Git history for internal traceability, but this
  changelog focuses on current public-facing release checkpoints.
## 2026-04-12

- Hardened WSL audio readiness and selection policy:
  - `bootstrap_install` now requires `abi_ready=true` before considering the WSL audio workspace ready
  - canonical ingestion no longer selects the WSL audio backend when preflight reports an ABI-degraded runtime
  - `wsl2_audio_bridge` now surfaces ABI-degraded WSL as an explicit preflight error instead of proceeding with warnings
  - fixed `cache_readiness_check.py` so it resolves the canonical `models_cache` path correctly instead of falling back to repo-local `_DATA\models`
- Completed the first five-episode Season 3 `scene_context_llm` campaign:
  - `03x04` through `03x08` all passed
  - `193` scenes processed
  - `189` scenes with `scene_context_llm`
  - all five runs preserved `phase6_complete = true`, `qdrant_ok = true`, and `generic_context_detected = false`
