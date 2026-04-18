<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-04-17 -->

# System Snapshot

_Generated: 2026-04-17T19:15:00_

## Host & OS
- Hostname: GOOD-CUBE
- OS: Windows 10 Pro (10.0.26200)
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

## Active Treatment State
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
  - local episode-reference eval now uses curated IMDb-backed anchor artifacts under `reports/reference_anchors/seinfeld/episodes/` for audit only; they score witness output without overriding runtime scene truth
  - proving-witness local eval improved to `6/6` core beats and `9.0/9.0` salience
  - local forensic reference: `docs/diagnostics/MEMORY_ARBITRATION_FORENSIC_AUDIT_03x10_2026-04-12.md`
  - the `GOOD-SPEED-32` WSL audio bootstrap drift fix is now shipped on `main`; remaining follow-up is laptop-side confirmation of the repaired installer path.

## Recent Hardening
- WSL audio readiness now requires `abi_ready=true` before bootstrap or canonical ingest will treat the workspace as healthy.
- Canonical WSL selection now rejects ABI-degraded runtimes instead of running in warning-only mode.
- Cache readiness now resolves the canonical `models_cache` path correctly, avoiding false repo-local `_DATA/models` fallbacks.
