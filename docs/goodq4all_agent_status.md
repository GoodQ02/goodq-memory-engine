<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-06-07 -->

# GoodQ4All Agent Status

_Operational restart checkpoint aligned: 2026-06-07._

This document is a bounded operator snapshot of the current release-era
stitching and offline-package baseline.

Use canonical runtime contracts and released evidence surfaces as source of
truth for live claims. Do not treat this document as a live witness monitor.

## Current Restart Checkpoint
- Pause checkpoint, 2026-06-08:
  - status: PowerShell environment recovery, registry path normalization, and agent instructions alignment completed.
  - Shell & PATH recovery: Corrected dynamic path restoration bug in the PowerShell profile (`Add-GoodCubePersistedPathEntries`), resolved nested environment variables, and broadcasted `WM_SETTINGCHANGE` to normalize global system paths without restarting terminal sessions.
  - MCP & SDK Integration: Unlocked `sequentialthinking` reasoning tool and registered official reference `everything` server in `mcp_config.json`; whitelisted `read_url(*)` global permission grant to support web search results parsing.
  - Agent instructions alignment: Added `gemini.md` and `PLAN.md` to the authoritative documentation list in `AGENTS.md` and indices in both `goodq4all` and `goodq4all_public` repositories to prevent documentation drift; corrected hardcoded ProgramData path to `%PROGRAMDATA%` in `current_state.json`.
- Pause checkpoint, 2026-06-07:
  - status: Native macOS and Linux cross-platform parity enabled.
  - Control scripts: Added `dev_on.sh` and `dev_off.sh` in the workspace root to manage Qdrant, API Server, and Ingestion Watchdog background processes with PID tracking and port 30000 safety guards.
  - Unix Bootstrap: Added `scripts/bootstrap_install_unix.sh` for dependency preflights, conda environment creation (Python 3.10), platform-tailored PyTorch stack configuration (MPS for macOS, CUDA/CPU for Linux), step environment provisioning, model cache prefetching, and Go launcher compilation.
  - Documentation: Aligned setup guides, scene manifest specs, and assessments to support native POSIX execution paths (`audio_backend_effective=native`).
- Pause checkpoint, 2026-06-05:
  - status: Complete forensic quality audit and hardening pass of Subsystems 1 to 8 validated and committed.
  - Subsystems audited and verified:
    - Subsystem 1 (Packaging & Installer): dynamically resolve ProgramData/AppData and grant recursive Users Modify permission (`icacls`).
    - Subsystem 2 (Watchdog Ingestion): Windows sharing violation exclusive write-locks checks, 0-byte file guard, corrupt destination file cleanups, collision ceiling, and empty/stale lockfile auto-healing.
    - Subsystem 3 (Phased Ingestion Pipeline): unified GPU step memory fraction configuration loadings, cv2 VideoCapture bounds protection, and keyframe selection timestamp deduplication.
    - Subsystem 4 (WSL2 Audio Lane): WSL configs dynamic resolution, cache CRLF line endings normalization, proactive mount existence checks, and offline Transformer fallback-first cache loaders.
    - Subsystem 5 (Web API Server): socket port collision fallback searches, case-insensitive log token redaction filters, progress track freshness limits, and drop zone redirects preventions.
    - Subsystem 6 (Vector Database & Search): process-safe exclusive-file FAISS HNSW locking (`FaissLock`), upsert/query connection loss auto-healing, and dynamic model dimension register mappings.
    - Subsystem 7 (Relational & Graph Memory): SQLite concurrent transaction WAL busy timeout queuing (5000ms), and read-only URI mapping `?mode=ro` with timeouts.
    - Subsystem 8 (Healer & Control Agent): robust `dry_run` constructors and try-except LLM connection timeout exceptions guards.
  - Verification: 493 tests passing, concurrent FAISS writes verified, concurrent WAL database writes verified, and Healer dry-run verified.
- Pause checkpoint, 2026-05-28:
  - status: unified sandboxed Setup Installer and local logs/GPU config mitigations are validated and committed.
  - Setup Installer features:
    - Zero-dependency sandbox installer (`GoodQ4All_Setup_1.0.0.exe`) bundling base PyPI packages, perception libraries (`opencv-python`, `scenedetect`, `imageio-ffmpeg`), and pre-allocated model/offline-document folders.
    - Go launcher supervisor (`LAUNCH_GOODQ.exe`) managing model signatures, booting Qdrant/API/Watchdog, and launching the browser console.
    - Bypasses Conda lookup (`python_paths.py`) and resolves modules dynamically relative to runtime when sandboxed.
  - Hardening & CPU-safe fallback:
    - Wrapped PyTorch imports in `scripts/gpu_config.py` in try-except blocks, allowing baseline steps to run on CPU-only clean machines without throwing ModuleNotFoundError.
    - Log redirection: mapped logger paths to writeable ProgramData (`%PROGRAMDATA%\GoodQ4All\logs`) and wrapped file handler creation in try-except to fail-safe gracefully to stdout.
    - Swagger/ReDoc served offline locally.
  - UI additions: Collapsible glowing cyber-helipad **Upload Pad** panel integrated into Retro Memory Explorer header, enabling seamless drag-and-drop file imports directly to watchdog.
- Pause checkpoint, 2026-05-27:
  - status: local LLM memory tuning and visual pipeline optimizations are validated and committed.
  - active API on port `30000` is bound to `epoch_2026_05_22_family_full_01`, reporting correct vector dimensions and successful FAISS parity writes.
  - local LLMs are fully optimized:
    - vLLM (Qwen2.5-0.5B-Instruct) allocation capped at `--gpu-memory-utilization 0.20` and `--kv-cache-dtype fp8` (~3.3 GB VRAM) maintaining full throughput (~275-365 tok/s).
    - Windows Ollama fallback (`phi4:latest`) optimized via Flash Attention and Q8 KV cache quantization, reclaiming 1.81 GB VRAM (from 15.23 GB to 13.42 GB) and achieving 50-70% speedups.
    - Combined posture: Both primary vLLM and fallback Ollama services run simultaneously in VRAM with plenty of headroom on the RTX 4070 Ti SUPER.
  - visual pipeline is fully optimized and upgraded:
    - CLIP upgraded to `openai/clip-vit-large-patch14` (768-d).
    - DINOv2 upgraded to `facebook/dinov2-large` (1024-d).
    - Vectorized GPU scene detection (`gpu_scene_detect.py` using PyTorch differences to minimize CPU-to-GPU syncs).
    - OpenCV-Native seeking frame extractor (`scene_frame_extractor.py` using Python-native `cv2.VideoCapture`).
    - Advanced keyframe selection based on Shannon entropy, Laplacian variance, and motion peaks.
    - Mixed-precision (AMP) batching flattens and processes frames in a single batch.
  - validation run on `samples/onboarding_fixture.mp4` completed in 5.7 seconds for visual embeddings, verifying Qdrant & FAISS parity writes (`faiss_ok = true`) under upgraded dimensions.
  - next safe move before broad home-movie ingestion: reset Qdrant, prepare the new epoch, and run a scene-first probe.
- Pause checkpoint, 2026-05-22:
  - status: local fallback/audio/entity repair is validated and committed on
    the active source line.
  - active API on port `30000` is bound to
    `epoch_2026_05_22_runtime_fallback_probe_02`, a three-scene validation
    epoch, not a broad-run seed.
  - Windows Ollama fallback is healthy on `127.0.0.1:31434` with
    `phi4:latest`; Task Scheduler fixture
    `GoodQ4All Ollama Fallback Startup` invokes
    `scripts/start_ollama_fallback.ps1`.
  - vLLM primary remains healthy on `127.0.0.1:38005`; LLM client validation
    reports `2 / 2` configured models healthy, speed-preferred on vLLM and
    quality-preferred on Ollama/Phi4.
  - API `/api/status` now checks the configured WSL worker runtime before
    reporting `faster_whisper`; live status reports WSL audio `available` and
    `faster_whisper` `1.2.1` ready.
  - latest three-scene probe run id:
    `785b5eae-ff3e-4cae-9b64-37bbf2151a74`.
  - strict current-run audio proof is `3 / 3` CLAP-ok scenes proven against
    run-matched Qdrant payloads.
  - Qdrant validation counts are audio `3`, text `6`, CLIP `6`, DINO `6`, all
    green.
  - FAISS validation confirms audio, text, CLIP, and DINO indexes are
    explicit-ID `IndexIDMap2` with expected counts.
  - sentiment, text-emotion rankings, audio-emotion rankings, and channelized
    entity evidence are present for `3 / 3` scenes.
  - ambiguous same-label person/non-person promotion is patched and retested;
    the validation probe reports `0` ambiguous conflicts.
  - new reusable agent workflow:
    `docs/agent/workflows/EVIDENCE_FIRST_RUNTIME_REPAIR.md`.
  - next safe move before broad home-movie ingestion: reset Qdrant again, use a
    new fresh epoch, verify FAISS starts absent or explicit-ID, then run a
    scene-first probe before the full source.
- Pause checkpoint, 2026-05-21 evening:
  - historical note: superseded by the 2026-05-22 runtime fallback/audio/entity
    validation above.
  - status: clean sentiment and emotion-ranking probe is validated on the
    active local source line.
  - active API on port `30000` is bound to
    `epoch_2026_05_21_family_full_clean_04`, a clean clip-probe evidence
    epoch, not a broad-run seed.
  - the latest local probe used a short clip extracted from the first redacted
    FAMILY media file to avoid full-source scene-detection cost during
    scene-first validation.
  - Qdrant was reset before the probe; fresh `_04` collections started at `0`
    points and populated to text `2`, CLIP `2`, DINO `2`, audio `1`.
  - FAISS targets were absent before the probe and now read as explicit-ID
    indexes: text `IndexIDMap2` `2`, CLIP `IndexIDMap2` `2`, DINO
    `IndexIDMap2` `2`, audio `IndexIDMap2` `1`.
  - latest evidence route reports transcript `1 / 1`, sentiment `1 / 1`, text
    emotion ranking `1 / 1`, audio emotion ranking `1 / 1`, and strict
    current-run audio proof `Proven`.
  - latest evidence route now also exposes channelized entity evidence instead
    of a KG-only boolean: `4` temporal-index entities are present in the active
    clip probe, with dialogue-mentioned entities, candidate visible people, and
    speaker-aligned mentions separated from strict scene-present identity.
  - retrieval read models preserve the same channel split through
    `POST /api/search/multimodal`; live local validation returned `kg_evidence`
    from `timeline_scene_entities` with dialogue mentions and candidate-visible
    identity evidence intact.
  - runtime run id:
    `7c811231-b85c-4489-91b4-672d7bae57be`.
  - top text-emotion signal is `admiration` with score about `0.955`; top
    audio-emotion score signal is `surprise` with score about `0.135`, below
    the `0.5` promotion threshold. Treat this as ranked review evidence, not a
    promoted hard audio-emotion label.
  - `emotion_classify` now completes after loading the CardiffNLP emotion model
    through safetensors; previous `_02` artifacts remain useful pre-repair
    evidence but should not be used to judge the repaired path.
  - realtime KG no-input passes are no longer labeled as total entity absence;
    later transcript/temporal passes remain the authority for entity evidence.
  - next safe move before any further probe or broad home-movie run: reset
    Qdrant again and use a new fresh epoch, or deliberately reset the active
    epoch and verify FAISS targets are absent or explicit-ID indexes.
- Pause checkpoint, 2026-05-21:
  - `/api/runs/latest/preview` and `/api/runs/latest/evidence` now consider
    both indexed report roots and the configured direct CLI output file, then
    choose the freshest read-only scope.
  - configured direct CLI output is surfaced as
    `scope=configured_output_scene_results`; the operator console labels this
    as `Direct CLI Output`.
  - Operator Console v1 now opens with a Current Scope strip above Flight Deck:
    API base, latest run, run source, temporal scope, strict audio proof,
    browsing target, selected scene, and read-only mode.
  - latest validated direct-output probe showed strict audio proof as
    `current_run_audio_vector_proven` for `1 / 1` CLAP-ok scene.
- Pause checkpoint, 2026-05-20:
  - status: operator proof visibility now separates strict latest-run audio
    evidence from run-tagged Qdrant audio inventory.
  - active read-only surfaces include:
    - `GET /api/runs/latest/evidence` for the indexed latest run scope
    - `GET /api/runs/audio-proof/latest` for historical run-tagged Qdrant
      audio inventory
  - run discovery now recognizes standalone/direct run roots that expose
    `output/scene_ingest_results.json` without a root `experiment_log.json`.
    These are labeled with `scope=scene_ingest_results` and must not be
    described as structured wrapper-ledger runs.
  - active `audio_embed_clap` scene output now echoes safe provenance fields in
    `audio.clap_meta` when available, including `run_id`, `embedding_id`,
    `commit_ts_utc`, Qdrant attempted/committed status, and Qdrant collection.
  - boundary: the Qdrant inventory can prove that run-tagged audio payloads
    exist, but it does not make latest-run audio proof current unless the
    payload `run_id` matches the run being audited.
- Pause checkpoint, 2026-05-19:
  - status: read-only operator visibility envelopes are implemented, verified,
    and pushed on both source lines. Local workspace is `dev` / `origin/dev`
    at `50c9107` (`feat: expose operator visibility envelopes`). Public mirror
    is sibling public checkout `main` / `origin/main` at `98df1e3`
    (`feat: expose operator visibility envelopes`).
  - supported UI now includes Operator Console v1 at
    `/ui/operator_console_v1/`, served by the API process. The older
    Justification Channel remains available at `/ui/justification_v1/`.
  - Operator Console panels currently cover Current Scope, Flight Deck
    orientation, proof/evidence status, retrieval inspection, storage/runtime
    summaries, recurrence report readouts, video inventory, selected timeline,
    and Justification Channel handoff.
  - verified live local route on 2026-05-19:
    `/ui/operator_console_v1/?api_base=http%3A%2F%2F127.0.0.1%3A30000`
    returned `200` and included Flight Deck, Proof Panel, and Retrieval Console
    markup.
  - verified read-only API surfaces for the console include latest run evidence,
    latest run preview, system videos, full timeline, scenes, storage summary,
    and multimodal search. Treat them as inspection surfaces only.
  - boundary: no UI action may trigger ingestion, reindex memory, mutate
    persistence, heal configs, generate recurrence reports, or activate
    ControlAgent.
  - next safe move after restart: continue with targeted schema/read-model or UI
    clarity passes only after route-level verification against real data.
- Pause checkpoint, 2026-05-17:
  - status: first-run truth closure is pushed on `dev`; current work is
    follow-on agent-facing truth refresh and remaining OPUS checklist triage,
    not runtime architecture change.
  - local source line: `dev` / `origin/dev`; first-run closure checkpoints
    pushed on 2026-05-17 are `e8ae169` (`docs: close first-run truth gaps`)
    and `588b8c2` (`fix: align wsl distro fallback`). Verify the live head
    with `git log -1 --oneline`.
  - public mirror line: sibling `goodq4all_public` on `main` / `origin/main`;
    public-safe closure checkpoints pushed on 2026-05-17 are `0b9ac99`
    (`docs: mirror first-run truth closure`) and `0ccf271`
    (`fix: align wsl distro fallback`).
  - org profile line: sibling `goodq02_profile` on `main` / `origin/main` at
    `f789962` (`docs: clarify goodq4all first-run path`).
  - selected policy: installer data-root behavior remains unchanged; active
    docs define `GOODQ_DATA_ROOT` as the base root and the runtime inbox as
    `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`.
  - root `smoke_inbox/` and `test_input/` are now ignored local scratch inbox
    names only; they are not supported first-run drop zones.
  - WSL distro fallback now uses the generic `Ubuntu` alias when no detected
    Ubuntu-like distro is available, while preserving explicit local settings.
  - current safe next move after restart: continue the OPUS checklist from the
    smallest remaining doc/runtime mismatch, then mirror only public-safe
    changes to public/profile repos.
- Pause checkpoint, 2026-05-11:
  - status: portability/bootstrap prep is active; do not start broad ingestion
    or UI work before confirming the current git head and reviewing the offline
    bundle contract.
  - canonical model cache authority is `<GOODQ_DATA_ROOT>/models` or an
    explicitly staged `%GOODQ_MODEL_CACHE_ROOT%`.
  - the legacy root-level model cache was audited: all nonzero material model
    payload files matched the canonical model cache by hash; unmatched files
    were non-runtime cache logs only.
  - legacy root-level model cache references are now treated as drift risk, not
    runtime or packaging authority.
  - active helper/template cleanup is in progress for this checkpoint:
    `.env.model_cache`, `scripts/audit_vision_pipeline.py`,
    `scripts/download_datasets.py`, `scripts/prepare_step_envs.ps1`,
    `scripts/utilities/gpu_config.py`, and legacy utility probes now resolve
    the model cache from `GOODQ_MODEL_CACHE_ROOT`, `GOODQ_DATA_ROOT`, or the
    configured `models_cache` path instead of a fixed root.
  - non-archive tracked source/docs were scanned for the old model-root literal
    after cleanup and returned no hits; remaining hits are archived historical
    material only.
  - active offline bundle contract is documented in
    `docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md`; scratch manifests remain local
    generated artifacts unless intentionally promoted.
  - current offline bundle source-evidence state:
    - 10 source artifacts hash-computed
    - 8 staged payload artifacts hash-computed
    - 1 supplemental artifact partial hash-computed
    - 2 optional artifacts deferred from the base installer
    - zero pending hashes
  - Windows env payload is staged and hash-sealed: 209 Conda tarballs plus a
    Python 3.10 no-index verified pip wheelhouse for 155 exact PyPI
    requirements; the source-owned `goodq4all` package is covered by the
    source pack.
  - WSL audio wheelhouse evidence is staged on the canonical cu121 lane, and a
    private WSL audio distro export is hash-sealed as the preferred near-term
    offline restore payload.
  - Host tools pack is staged and hash-sealed: FFmpeg, Tesseract, Poppler,
    Piper, Qdrant, and NSSM; staged Piper TTS smoke passed.
  - current safe next move after restart: restore-rehearse the staged payloads
    on a disposable target before creating any final archive or installer.
- Pause checkpoint, 2026-05-08:
  - status: Wav2Vec WSL enrichment is one-episode validated on laptop `GPU_ENHANCED`.
  - latest runtime/source fixes on `main`:
    - `3a06342` (`fix: load runtime pyannote from canonical cache`)
    - `86f032d` (`fix: align image step gpu budget mapping`)
  - same fixes are mirrored to `public`:
    - `e2e0b9d` (`fix: load runtime pyannote from canonical cache`)
    - `2a7b918` (`fix: align image step gpu budget mapping`)
  - public hygiene also includes `67ce408` (`chore: prune public legacy archives`) and `279c825` (`chore: tighten public utility path hygiene`)
  - laptop `GPU_ENHANCED` one-scene witness `20260508_104105_laptop_gpu_enhanced_one_scene_witness` completed with run id `02fdd2d9-7868-442b-8628-2550ed976820`
  - witness passed bootstrap/preflight, WSL torch lane `2.5.1+cu121`, Qdrant reachability, WSL audio execution, transcript persistence, CLAP/audio embedding, text embedding, Phase 6a/6b, `phase6_complete=true`, and `qdrant_ok=true`
  - witness found live runtime PyAnnote still needed the canonical HF cache dir in `wsl2_audio/process_audio.py` and `wsl2_audio/audio_service.py`; `3a06342` patches both runtime loaders
  - witness found laptop image-caption OOM was consistent with the active `scripts.gpu_config` map missing image-step budgets; `86f032d` aligns image-caption/DINO/CLIP budgets with the canonical vision step contract
  - WSL-side Wav2Vec emotion/embedding enrichment lane is now qualified with pinned `transformers==4.43.3`, `tokenizers==0.19.1`, and `safetensors==0.7.0`; base WSL readiness remains separate from `wav2vec_enrichment_ready`
  - laptop one-scene witness `20260508_173240_laptop_gpu_enhanced_one_scene_witness_wav2vec_artifact_fields` passed with Phase 6 complete, Qdrant ok, BLIP caption ok, diarization success, Wav2Vec enrichment success, and `embedding_dim=768`
  - post-pull laptop one-scene witness `20260508_191455_laptop_gpu_enhanced_one_scene_witness_wav2vec_post_pull` on `7a7fd15` exited `0` and confirmed the same live artifact fields: WSL runtime ready, diarization success, `wav2vec_enrichment_ready=true`, Wav2Vec emotion success, Wav2Vec embeddings success with `embedding_dim=768`, speaker signature `status=ok`, BLIP caption ok, Phase 6 complete, and Qdrant ok
  - one-episode laptop witness `20260508_214134_laptop_gpu_enhanced_one_episode_witness_wav2vec_post_pull` on `7a7fd15` exited `0` across `33` scenes: WSL audio success `33 / 33`, diarization success `33 / 33`, `wav2vec_enrichment_ready=true` `33 / 33`, Wav2Vec emotion success `33 / 33`, Wav2Vec embeddings success `33 / 33` with `embedding_dim=768`, BLIP caption ok `33 / 33`, CLAP ok `33 / 33`, transcript/full text present `33 / 33`, Phase 6 complete, and Qdrant ok
  - remaining WSL audio watch item is non-fatal `torchcodec_decoder_unavailable`; current runtime succeeds through preloaded-audio handling
  - WSL Wav2Vec qualification plan/proof trail: `docs/superpowers/plans/2026-05-08-wsl-wav2vec-transformers-lane.md`
- Pause checkpoint, 2026-05-07:
  - latest local docs-clearance commit: `103b17f` (`docs: add documentation forensics index`)
  - docs folder is now indexed for future agent lookup through `docs/reference/indexes/DOCS_FORENSICS_INDEX.md`
  - every active Markdown/text doc under `docs/` has an explicit `DOC_STATUS` marker as of the docs-clearance pass
  - the old WSL audio emotion sample output was preserved as `archive/docs/diagnostics/wsl2_audio_emotion_sample_output.json`; treat it as a historical diagnostic relic, not current runtime truth
  - only expected untracked local artifacts at pause were recurrence report artifacts under `reports/control_recurrence/`
  - immediate next action after pause: analyze the incoming laptop bootstrap audit before continuing project-root cleanup
- Current local workspace:
  - `dev` / `origin/dev` is the active local source line for this workspace;
    confirm the exact head with `git log -1 --oneline`
  - source includes the May 19 operator visibility envelope checkpoint through
    pushed checkpoint `50c9107`
- Current public-facing branch:
  - sibling `goodq4all_public` uses `main` / `origin/main`; public-safe
    operator visibility envelope work is mirrored through pushed checkpoint
    `98df1e3`
- Current state:
  - Full Season 1 recompare witness completed successfully across `01x01` through `01x05`
  - Full Season 2 fresh witness completed successfully across `02x01` through `02x12`
  - Read-only operator package is restored and shipped:
    - `lib/run_index.py`
    - `lib/run_summary.py`
    - `GET /api/runs/latest/preview`
    - `GET /api/runs/latest/evidence`
    - `GET /api/storage/summary`
    - `GET /api/system/videos`
    - `GET /api/videos/{video_id}/timeline/full`
    - `GET /api/videos/{video_id}/scenes`
    - `POST /api/search/multimodal`
    - `ui/operator_console_v1/` (observer-only local operator console)
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
    - control recurrence is source-complete as a read-only observability layer for operator-console and portability work; v0.5 status is recorded in `docs/releases/CONTROL_RECURRENCE_v0.5_STATUS.md`
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
  4. Refresh or clearly quarantine `archive/docs/bootstrap/SCRIPT_REGISTRY.md`; it is a stale generated aid, not runtime authority.
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
- Desktop machine audit: removed from active scratch; do not use it as rebuild authority
- Offline bundle root: no validated current offline bundle is in circulation
- Machine-audit working copy: removed from active scratch
- Active rebuild plan: `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- Transport reconciliation: use current source-evidence manifests; old
  machine-audit payload is unavailable
- Previous Phase 1 installer artifact: retired from circulation after stale-bundle audit
- Closure status:
  - Linux WSL audio wheelhouse: canonical `2.5.1+cu121` torch-family evidence is staged and hash-computed
  - Windows Conda tarballs: staged and hash-computed from current GoodQ envs
  - Windows pip wheelhouse: sealed in staged payload; 155 exact PyPI requirements verified with Python 3.10 no-index download checks
  - WSL restore strategy: private WSL audio distro export is hash-sealed; apt archive evidence remains supplemental partial evidence with direct package archives missing for `python3-pip`, `python3-venv`, `sox`, and `git`
  - Host payloads: copied and hash-sealed into staged tools pack
  - Piper: staged, hash-sealed, and smoke-tested with `en_US-joe-medium`
- Packaging doctrine:
  - `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128` is functional drift evidence, not a package recommendation and not an offline bundle target
  - bootstrap target remains the canonical WSL audio `2.5.1+cu121` torch family
- Host parity additions now installed and wired:
  - Poppler / `pdftotext`
  - Piper + `en_US-joe-medium` voice
- Optional asset state:
  - required model cache: present locally
  - NRC lexicon: staged locally
  - dataset corpus: optional eval/research/training material only; do not include
    the large dataset cache in the base installer
  - reference bank: optional external knowledge substrate only; it may
    contextualize output but is not GoodQ personal memory and is not a base
    installer payload until a separate manifest is selected
  - synthetic debug kit: future owned preflight/demo fixture lane only; do not
    substitute Seinfeld/test-run media for it
  - memory snapshot: none selected by design; base GoodQ should boot clean and
    create new memory unless a separate private/witness memory pack is
    deliberately installed

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
- Hardened and audited all 8 core subsystems (Installer paths & permissions, watchdog folder drop checks, ingestion pipeline seeks & GPU variables, WSL2 audio bridge configs & cache references, Web API socket & drop redirects, Vector DB concurrency locks & dimensions, Relational memory busy timeouts, and Healer dry-run & LLM exception guards). Verified all changes with 493 unit/integration tests and concurrent stress test runs in both dev and public repositories.
- Upgraded and optimized the visual processing pipeline: upgraded CLIP to `openai/clip-vit-large-patch14` (768-d) and DINOv2 to `facebook/dinov2-large` (1024-d); vectorized PyTorch GPU scene detection; added OpenCV-native seeking/decoding keyframe extraction; implemented Shannon-entropy, Laplacian-variance, and motion-peaks keyframe selection; and implemented mixed-precision (AMP) batching.
- Optimised local LLM services: tuned WSL2 vLLM to cap memory utilization at 0.20 and enable FP8 KV-cache (~3.3 GB footprint) for Qwen2.5-0.5B-Instruct; configured Windows Ollama fallback (Phi-4 14B) with Flash Attention and Q8 KV cache quantization (reducing VRAM footprint to 13.42 GB and accelerating inference speed by 50-70%), enabling simultaneous local hosting of both models.
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
