<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-05-04 -->

# System Snapshot

_Operational operator-state alignment refreshed: 2026-05-04._

This is a bounded release-era system snapshot. It is useful for understanding
the supported host/runtime baseline, but it is not a live witness monitor.

## Host & OS
- Hostname: GOOD-CUBE
- OS: Windows 11 (10.0.26200)
- Architecture: AMD64
- Timezone: Central Standard Time

## CPU / Memory
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel
- RAM: 68465905664

## GPU
- GPU(s): NVIDIA GeForce RTX 4070 Ti SUPER
- CUDA: 595.79

## Storage (Top-Level)
- System volume: total=3352GB free=2074GB
- Workspace volume: total=3353GB free=3249GB

## Toolchain
- Python: Python 3.13.11
- Conda: conda 25.11.1
- Git: git version 2.53.0.windows.1
- Node: v24.14.0
- Codex CLI: unavailable

## Installed Host Tools
- FFmpeg: present
- Tesseract: present
- Poppler / `pdftotext`: present
- Piper: present
- Qdrant / NSSM payloads: present

## WSL
- WSL enabled: Default Distribution: Ubuntu-22.04 | Default Version: 2 | WSL1 is not supported with your current machine configuration. | Please enable the "Windows Subsystem for Linux" optional component to use WSL1.
- Distros: NAME            STATE           VERSION | * Ubuntu-22.04    Stopped         2

## Local Services (Presence Check)
- Qdrant (6333): reachable
- Ollama (unknown): unavailable
- LM Studio (1234): not reachable

## Offline Packaging State
- Workspace-adjacent machine-audit pack: present
- Workspace-adjacent offline bundle root: present
- Repo payload staged into offline bundle: present
- Transport reconciliation final gap report: `HIGH` confidence
- Phase 1 self-extracting installer: present
- Closure state:
  - Linux wheels: complete
  - Windows wheels: complete
  - Host payloads: complete
- Current large local asset work:
  - required model cache: present locally
  - NRC lexicon: present locally
  - dataset prefetch: active / large cache already materialized

## Benchmark State
- Locked two-season benchmark witness: `reports/fresh_ingest_runs/20260409_072106_two_season_benchmark_witness/`
- Episodes processed: `17`
- Total scenes: `651`
- Baseline totals:
  - `381` dialogue-entity scenes
  - `316` mentioned-people scenes
  - `131` candidate-visible scenes
  - `70` interaction-dominance scenes
  - `10` conversation-owner scenes
  - `651` audio-emotion scenes
  - `167` time-hint scenes
  - `14` music-event scenes
- Canonical baseline memo: `docs/testing/SEASON1_2_BASELINE_MEMO_2026-04-10.md`
- Note: `audio.metadata_time_hints`, the modernized `scene_summarizer`, and `scene_context_llm` landed after this benchmark started and are treatment features, not part of the locked control

## Current Witness State
- Full Season 1 recompare witness:
  - roots:
    - `reports/fresh_ingest_runs/20260424_003250_season1_recompare_witness/`
    - `reports/fresh_ingest_runs/20260424_065027_season1_remaining_witness/`
  - result:
    - `5 / 5` passed
    - `185` total scenes
    - `179` `scene_context_llm` segments
    - `47` candidate-visible segments
    - `23` interaction-dominance segments
    - `3` conversation-owner segments
    - `70` speaker-aligned-mention segments
    - `27` transcript/entity disagreement segments
- Full Season 2 fresh witness:
  - root:
    - `reports/fresh_ingest_runs/20260424_182406_season2_fresh_witness/`
  - result:
    - `12 / 12` passed
    - `466` total scenes
    - `461` `scene_context_llm` segments
    - `84` candidate-visible segments
    - `47` interaction-dominance segments
    - `7` conversation-owner segments
    - `131` speaker-aligned-mention segments
    - `51` transcript/entity disagreement segments

## Current Operator State
- Active read-only run surfaces:
  - `lib/run_index.py`
  - `lib/run_summary.py`
  - `/api/runs/latest/preview`
  - `lib/control_recurrence_report.py`
  - `lib/control_recurrence_index.py`
  - `lib/control_recurrence_recommendations.py`
  - `lib/control_recurrence_trend.py`
  - `python -m cli.control_recurrence_report`
  - `/api/control-recurrence/reports`
  - `/api/control-recurrence/reports/latest`
  - `/api/control-recurrence/reports/trend`
  - `/api/control-recurrence/reports/{report_id}`
  - `/api/control-recurrence/reports/{report_id}/markdown`
  - `/api/control-recurrence/reports/{report_id}/recommendations`
- Current operator behavior:
  - reads structured artifacts under `reports/fresh_ingest_runs`
  - projects more truthful in-flight status by detecting episode lane-start artifacts
  - does not revive retired legacy `/runs` compatibility shells
  - reads recurrence truth from existing `step_runs.jsonl`, run warnings, `scene_ingest_results.json`, `scene_manifest.json`, `temporal_index.json`, and `experiment_log.json`
  - supports direct canonical run roots without a wrapper `experiment_log.json` by reading existing `operator_run_metadata.json`, `output/scene_ingest_results.json`, `workspace/_resolved_config.json`, canonical `step_runs.jsonl`, and captured ingestion stdout/stderr events
  - supports multi-video direct run roots and metadata-described output/workspace paths without creating a second execution path
  - scopes shared direct-run stdout events by persisted video/scene identity before turning them into recurrence signals
  - surfaces read-only step latency evidence from existing `step_runs.jsonl` `duration_ms` rows, including p50/p95/max by step, slow outlier counts, timeout-boundary exceedance counts, and WSL audio timing buckets
  - treats `control-recurrence-v0.4.1` as a valid sealed milestone for direct-run discoverability and truth-surface alignment, with the latest control recurrence tag at `control-recurrence-v0.4.2`
  - current source beyond the latest control recurrence tag includes read-only recurrence trend mode, CLAP audio Qdrant payload provenance hardening, native model smoke diagnostics, shared runtime recurrence scoping, and WSL audio runtime black-box diagnostics through `05ae539`
  - audio-vector success is provenance-defined by `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
  - current-run CLAP/Qdrant audio coverage requires `clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and required provenance fields
  - legacy, stale, or scene-id-only Qdrant audio points are not current-run proof
  - one-episode audio-provenance baseline showed `40 / 40` CLAP ok scenes with current-run Qdrant provenance
  - two-episode boundary witness showed `75 / 75` CLAP ok scenes with current-run Qdrant provenance across `78` scenes, while `2` optional CLAP errors and `1` `audio_silent` skip remained uncredited in current-run Qdrant
  - treats bounded direct-run discovery limits as expected when required artifacts are absent, not as recurrence-layer boundary violations
  - classifies recurrence families as `informational`, `watch`, `actionable`, or `blocking`
  - emits deterministic operator hints and inspection targets without changing runtime state
  - can write markdown to `reports/control_recurrence/` when `--write-md` is explicitly supplied
  - can write durable JSON artifacts with `--write-json-file`
  - records durable artifact discovery in `reports/control_recurrence/index.json`
  - derives conservative trends from the recurrence artifact index and indexed durable JSON reports only
  - treats untracked local `reports/control_recurrence/index.json` state as workspace artifact hygiene unless it is intentionally tracked
  - marks legacy markdown-only index entries explicitly with `artifact_status=markdown_only` and an index warning
  - exposes a local read-only API over the existing recurrence index and indexed artifacts
  - drafts deterministic operator inspection steps from existing durable JSON reports
  - boundary: not healing yet. The recurrence report/API latency evidence is observer-only; it does not activate `ControlAgent`, does not enable auto-healing, does not mutate configs, does not execute commands, does not use LLMs, does not generate reports from the API, and does not touch `cli/run_ingestion.py`.
- Current WSL audio scheduling truth:
  - recent controlled witnesses from 2026-05-01 through 2026-05-03 show unified WSL audio is healthy but expensive
  - `audio_unified_wsl2` p50/p95 is about `58.2s` / `62.1s` per scene across `234` observed rows
  - WSL audio consumed roughly `61.6%` to `63.9%` of summed step duration in recent one- and two-episode witnesses
  - same-scene probes on 2026-05-04 showed diagnostic forced-CPU Windows transcript-only processing was faster on sampled `02x02` scenes, but it omitted the unified WSL diarization, emotion, speaker-count, and speaker-signature surfaces
  - black-box witness `20260504_074335_wsl_black_box_02x02_witness` completed `38 / 38` WSL audio rows ok and persisted `bridge_runtime_probe` in all scene results and all canonical scene-manifest scenes
  - the witnessed sourced WSL worker reported `torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, `torchaudio==2.8.0+cu128`, `torch_lane_status=differs_from_expected`, and `torchcodec_ready=false`
  - this is an environment truth warning surfaced by the recorder; it is not an ingestion failure and not approval for package mutation
  - use `step_runs.jsonl`, recurrence latency summaries, and surface-equivalent probes for current scheduling truth; do not treat historical projected GPU speedup tables as current scheduling proof
- Exact control recurrence commands:
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

## Current Upstream Normalization State
- Exact-pair pilot only:
  - `Jerry Seinfeld -> Jerry`
- Scope:
  - projection / reconciliation boundary only
  - no extraction changes
  - no KG changes
  - no identity ladder changes
  - no retrieval changes
- Instrumentation now visible on segment read surfaces:
  - `normalization_applied`
  - `normalization_source`
- Operational interpretation:
  - this is a controlled mutation experiment, not a general normalization system
  - no broader allowlist expansion should occur without the same proof gate

## Release-Era Treatment State
- Feature ladder authoritative pass roots:
  - `reports/fresh_ingest_runs/20260410_071121_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260410_164051_season3_feature_ladder/`
  - `reports/fresh_ingest_runs/20260411_171418_season3_feature_ladder/`
- Treatment epoch: `epoch_2025_12_23`
- Execution order:
  - `03x01`: `audio.metadata_time_hints`
  - `03x02`: modernized `scene_summarizer`
  - `03x03`: `scene_context_llm`
- Feature enablement rule: local override only through `configs/config.local.yaml`
- Confirmed state:
  - `03x01` is an auditable no-signal pass: wiring proved, but chunked scene WAVs did not contain file-tag metadata.
  - `03x02` passed with full summary coverage against the modern nested scene shape.
  - `03x03` passed with `scene_context_llm` coverage in `36/39` scenes and `generic_context_detected = false` on the authoritative `20260411_171418` run.
- Canonical treatment memo: `docs/testing/SEASON3_TREATMENT_LADDER_MEMO_2026-04-11.md`
- Next campaign runbook: `docs/testing/SEASON3_FIVE_EPISODE_RUNBOOK_2026-04-11.md`
- Five-episode campaign close-out: `docs/testing/SEASON3_FIVE_EPISODE_CAMPAIGN_MEMO_2026-04-12.md`
- Next-layer implementation prework: `docs/architecture/NEXT_LAYER_IMPLEMENTATION_PLAN_2026-04-12.md`
- Supplemental five-scene audit: `docs/diagnostics/SEASON3_FIVE_SAMPLE_AUDIT_2026-04-12.md`
- Post-campaign validation:
  - `03x09` passed as the authoritative self-audit witness on `reports/fresh_ingest_runs/20260412_140550_season3_feature_ladder/`
  - canonical audit: `docs/diagnostics/SCENE_CONTEXT_LLM_AUDIT_03x09_2026-04-12.md`
- Campaign completion state:
  - run root: `reports/fresh_ingest_runs/20260411_194713_season3_feature_ladder/`
  - episodes: `03x04` through `03x08`
  - result: `5 / 5` passed
  - totals:
    - `193` scenes processed
    - `189` scenes with `scene_context_llm`
    - `97.9%` scene-context coverage
  - all five runs preserved:
    - `phase6_complete = true`
    - `qdrant_ok = true`
    - `generic_context_detected = false`
- Current release checkpoint:
  - proving witness: `reports/fresh_ingest_runs/20260417_163530_season3_feature_ladder/`
  - additive `scene_context_arbitration` is now canonical in Phase 6 outputs and projected run summaries
  - the three-tier `scene_context_llm` contract is active, with explicit array persistence for low-signal scenes
  - transcript-beat seam closure is witness-proven on `03x10` / `03x11`, including `Steve Pocatillo`, `alternate side`, and `rental car`
  - WSL audio readiness now requires real offline diarization loadability under the sourced runtime, not import-only checks
  - successful unified audio outputs preserve `diarization_status` / `diarization_error` and `emotion_status` / `emotion_error` on the success path
  - speaker continuity surfaces can now persist when stable voiced speech is present, rather than remaining structurally absent
  - local episode-reference eval now uses curated IMDb-backed anchor artifacts under `reports/reference_anchors/seinfeld/episodes/` for audit only; they score witness output without overriding runtime scene truth
  - proving-witness local eval improved to `6/6` core beats and `9.0/9.0` salience
  - local forensic reference: `docs/diagnostics/MEMORY_ARBITRATION_FORENSIC_AUDIT_03x10_2026-04-12.md`
  - the `GOOD-SPEED-32` WSL audio bootstrap drift fix is now shipped on `main`; remaining follow-up is laptop-side confirmation of the repaired installer path.
  - post-release projection smoke: `reports/fresh_ingest_runs/20260419_191136_season5_projection_smoke/`
    - `05x01` and `05x02` both passed on fresh Season 5 material
    - speaker continuity now persists end to end through `scene_ingest_results.json`, `scene_manifest.json`, and `temporal_index.json`
    - smoke totals:
      - `83 / 84` scenes with `speaker_count > 0`
      - `80 / 84` scenes with `speaker_voice_signature_count > 0`
      - `84 / 84` scenes with `diarization_status`
      - `84 / 84` scenes with `emotion_status`
    - current short-smoke KG state now includes `speaker`, `voice_pattern_match`, `identity_candidate`, and `identity_supported` activity instead of transcript-only continuity

## Recent Hardening
- WSL audio readiness now requires `abi_ready=true` before bootstrap or canonical ingest will treat the workspace as healthy.
- Canonical WSL selection now rejects ABI-degraded runtimes instead of running in warning-only mode.
- Cache readiness now resolves the canonical `models_cache` path correctly, avoiding false repo-local `_DATA/models` fallbacks.
- WSL diarization readiness now depends on offline loadability of the exact configured pipeline chain.
- Unified audio success-path payloads preserve diarization and emotion sub-step truth instead of hiding those fields behind a coarse success result.
