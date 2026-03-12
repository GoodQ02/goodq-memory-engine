# Environment Variable Inventory

Generated: 2026-02-18 (static scan)

Scan scope: `configs/`, `api/`, `steps/`, `lib/`, `scripts/`, `wsl2_audio/`, `cli/`, `agents/`, `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat`.

Scan exclusions: `**/archive/**`, `**/__pycache__/**`, `*.pyc`, `*.backup*`, `*.old*`.

## Contract Variables

## ANTHROPIC_API_KEY

- Surfaces: LAUNCH_GOODQ.ps1:279
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: optional integration
- Safe if unset: Yes
- Notes: Currently only checked by launcher health surface.

## ELEVENLABS_API_KEY

- Surfaces: scripts/sync_env_local.ps1:8, steps/tts/step.py:75
- Default in code: ""
- Required in strict mode: Conditional
- Affects: optional integration
- Safe if unset: Conditional (required for ElevenLabs TTS)
- Notes: TTS provider key.

## ELEVENLABS_VOICE_ID

- Surfaces: scripts/sync_env_local.ps1:8, steps/tts/step.py:77
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: optional integration
- Safe if unset: Yes
- Notes: Preferred ElevenLabs voice id.

## GOODQ_API_HOST

- Surfaces: api/API_DOCUMENTATION.md:474, api/server.py:13, scripts/prepare_step_envs.ps1:34, scripts/start_api.ps1:21, scripts/sync_env_local.ps1:4, scripts/system_readiness_check.py:177
- Default in code: "0.0.0.0"
- Required in strict mode: No
- Affects: runtime/service
- Safe if unset: Yes (defaults to 0.0.0.0)
- Notes: API bind host override.

## GOODQ_API_PORT

- Surfaces: api/API_DOCUMENTATION.md:475, api/server.py:15, scripts/prepare_step_envs.ps1:35, scripts/start_api.ps1:22, scripts/sync_env_local.ps1:4, scripts/system_readiness_check.py:178
- Default in code: "30000"
- Required in strict mode: No
- Affects: runtime/service
- Safe if unset: Yes (defaults to 30000)
- Notes: API bind port override.

## GOODQ_CC_QUERY

- Surfaces: scripts/command_center.ps1:235, scripts/sync_env_local.ps1:5
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: dev utility
- Safe if unset: Yes
- Notes: Command center query override.

## GOODQ_CC_THUMBS

- Surfaces: scripts/command_center.ps1:470, scripts/sync_env_local.ps1:5
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: dev utility
- Safe if unset: Yes
- Notes: Command center thumbnail count override.

## GOODQ_COMMIT_EVENTS_JSONL

- Surfaces: steps/common/memory_commit_events.py:278
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (defaults true)
- Notes: Toggle memory commit JSONL mirror.

## GOODQ_CONDA_ENV

- Surfaces: LAUNCH_GOODQ.ps1:38, configs/config.yaml:126, configs/config.yaml:135, configs/config.yaml:46, scripts/INSTALL_WSL2_AUDIO.bat:70, scripts/SETUP_WEB_DEPENDENCIES.bat:25, scripts/SETUP_WEB_DEPENDENCIES.bat:26, scripts/SETUP_WEB_DEPENDENCIES.bat:28, scripts/SETUP_WEB_DEPENDENCIES.bat:34, scripts/SETUP_WEB_DEPENDENCIES.bat:40 ...
- Default in code: "goodq_core", goodq_core
- Required in strict mode: No
- Affects: bootstrap/install/service
- Safe if unset: Yes (defaults to goodq_core)
- Notes: Canonical conda env selector for launcher/bindings.

## GOODQ_DATA_ROOT

- Surfaces: LAUNCH_GOODQ.ps1:22, api/main.py:72, configs/config.yaml:43, configs/config.yaml:55, configs/config.yaml:56, configs/config.yaml:57, configs/config.yaml:58, configs/config.yaml:59, configs/config.yaml:63, configs/config.yaml:64 ...
- Default in code: canonical host data-root fallback (`<GOODQ_DATA_ROOT>` default)
- Required in strict mode: No
- Affects: runtime/bootstrap/install
- Safe if unset: Yes (falls back through canonical host data-root config)
- Notes: Canonical host data root abstraction.

## GOODQ_DB_PATH

- Surfaces: LAUNCH_GOODQ.ps1:108, LAUNCH_GOODQ.ps1:378
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for resolved memory.db path.

## GOODQ_DEBUG_KEEP_TEMP

- Surfaces: steps/audio_transcribe/step.py:154, steps/audio_transcribe/step.py:310, steps/audio_transcribe/step.py:655
- Default in code: ''
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Transcribe debug temp retention flag.

## GOODQ_FAISS_AUDIO_PATH

- Surfaces: LAUNCH_GOODQ.ps1:112, LAUNCH_GOODQ.ps1:382
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for FAISS audio index path.

## GOODQ_FAISS_DIR

- Surfaces: LAUNCH_GOODQ.ps1:111, LAUNCH_GOODQ.ps1:381
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for FAISS directory.

## GOODQ_HEALTH_AUTH_HEADER

- Surfaces: scripts/health/pull_health_export.py:50
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: optional integration
- Safe if unset: Yes
- Notes: Optional custom auth header for health export HTTP request.

## GOODQ_HEALTH_AUTH_TOKEN

- Surfaces: scripts/health/pull_health_export.py:51
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: optional integration
- Safe if unset: Yes
- Notes: Optional auth token for health export HTTP request.

## GOODQ_HEALTH_EXPORT_URL

- Surfaces: scripts/health/pull_health_export.py:17, scripts/health/pull_health_export.py:47
- Default in code: none (or inherited via config resolution)
- Required in strict mode: Conditional
- Affects: optional integration
- Safe if unset: No for pull_health_export.py
- Notes: Required for passive health export pull script.

## GOODQ_HEALTH_SOURCE_ID

- Surfaces: scripts/health/pull_health_export.py:18, scripts/health/pull_health_export.py:48
- Default in code: none (or inherited via config resolution)
- Required in strict mode: Conditional
- Affects: optional integration
- Safe if unset: No for pull_health_export.py
- Notes: Required source identifier for health export script.

## GOODQ_HOST_PROFILE

- Surfaces: configs/config.yaml:42, scripts/bootstrap_verify.py:74, scripts/bootstrap_verify.py:88, scripts/bootstrap_verify.py:90, scripts/smoke_phase_a.py:157, scripts/smoke_phase_a.py:169, steps/common/profile_config.py:38
- Default in code: UNSET
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (legacy UNSET behavior)
- Notes: Profile semantic selector: UNSET|BASELINE|GPU_ENHANCED.

## GOODQ_KG_DB_PATH

- Surfaces: LAUNCH_GOODQ.ps1:109, LAUNCH_GOODQ.ps1:379
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for resolved knowledge graph DB path.

## GOODQ_MODELS_DIR

- Surfaces: scripts/bootstrap_models.py:102, scripts/pin_model_versions.py:84, scripts/preflight_check.ps1:19, scripts/setup/setup_agents.ps1:109, scripts/setup/setup_agents.ps1:12, scripts/sync_env_local.ps1:5, scripts/utils/verify_model_lockdown.py:235
- Default in code: canonical model-cache root (`<GOODQ_DATA_ROOT>/models`)
- Required in strict mode: No
- Affects: runtime/bootstrap/install
- Safe if unset: Yes
- Notes: Model root override used by bootstrap/setup/model utilities.

## GOODQ_NO_AUTO_GPU

- Surfaces: scripts/smoke_phase_a.py:160, scripts/smoke_phase_a.py:311, scripts/smoke_phase_a.py:314, scripts/smoke_phase_a.py:317, scripts/smoke_phase_a.py:323, scripts/smoke_phase_a.py:382, scripts/smoke_phase_a.py:88, steps/common/gpu_config.py:191, steps/common/gpu_config.py:194, steps/common/gpu_config.py:196 ...
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (auto GPU config remains enabled unless baseline)
- Notes: Disables automatic GPU config path when set to 1.

## GOODQ_PROCESSING_ROOT

- Surfaces: LAUNCH_GOODQ.ps1:110, LAUNCH_GOODQ.ps1:380
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for processing root.

## GOODQ_QDRANT_COLLECTION_AUDIO

- Surfaces: LAUNCH_GOODQ.ps1:118
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher-injected audio collection override.

## GOODQ_QDRANT_COLLECTION_CLIP

- Surfaces: LAUNCH_GOODQ.ps1:115
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher-injected CLIP collection override.

## GOODQ_QDRANT_COLLECTION_DINO

- Surfaces: LAUNCH_GOODQ.ps1:116
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher-injected DINO collection override.

## GOODQ_QDRANT_COLLECTION_TEXT

- Surfaces: LAUNCH_GOODQ.ps1:117
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher-injected text collection override.

## GOODQ_QDRANT_URL

- Surfaces: LAUNCH_GOODQ.ps1:113, LAUNCH_GOODQ.ps1:383
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/launcher
- Safe if unset: Yes
- Notes: Launcher override for Qdrant endpoint.

## GOODQ_READONLY_ENVELOPE_PATH

- Surfaces: api/main.py:1527, api/main.py:1529
- Default in code: ""
- Required in strict mode: Conditional
- Affects: runtime/api
- Safe if unset: Yes (endpoint returns 404)
- Notes: Required only for /api/read/envelope endpoint usage.

## GOODQ_REQUIRE_GPU

- Surfaces: scripts/smoke_phase_a.py:158, scripts/smoke_phase_a.py:173, scripts/smoke_phase_a.py:381, scripts/smoke_phase_a.py:391, steps/common/gpu_config.py:197, steps/common/profile_config.py:50, wsl2_audio/audio_service.py:197, wsl2_audio/audio_service.py:198, wsl2_audio/audio_service.py:216, wsl2_audio/audio_service.py:35 ...
- Default in code: ""
- Required in strict mode: No
- Affects: runtime/service
- Safe if unset: Yes
- Notes: Fail-fast GPU strictness when set truthy.

## GOODQ_REQUIRE_WSL_AUDIO

- Surfaces: scripts/smoke_phase_a.py:159, scripts/smoke_phase_a.py:175, scripts/smoke_phase_a.py:409, scripts/smoke_phase_a.py:412, scripts/smoke_phase_a.py:413, scripts/wsl2_audio_bridge.py:16, scripts/wsl2_audio_bridge.py:34, steps/audio_transcribe/step.py:413, steps/audio_transcribe/step.py:450, steps/audio_transcribe/step.py:454 ...
- Default in code: ""
- Required in strict mode: No
- Affects: runtime/service
- Safe if unset: Yes
- Notes: Fail-fast WSL audio strictness when set truthy.

## GOODQ_RETRIEVAL_CONTEXT

- Surfaces: steps/common/memory_stores.py:106, steps/common/memory_stores.py:241, steps/common/qdrant_client.py:210
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (normalizes to unknown)
- Notes: Retrieval context normalizer input.

## GOODQ_RETRIEVAL_EVENTS

- Surfaces: cli/observability_health.py:181, cli/observability_health.py:182, cli/observability_health.py:189, cli/observability_health.py:191, steps/common/retrieval_events.py:113, steps/common/retrieval_events.py:114
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (defaults true in retrieval_events helpers)
- Notes: Enable/disable retrieval events writes.

## GOODQ_RETRIEVAL_EVENTS_JSONL

- Surfaces: steps/common/retrieval_events.py:84, steps/common/retrieval_events.py:85
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes (defaults true)
- Notes: Toggle retrieval JSONL fallback logging.

## GOODQ_SMOKE_OVERRIDE_ROOT

- Surfaces: scripts/smoke_phase_a.py:25
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: test/dev utility
- Safe if unset: Yes
- Notes: Smoke matrix override root for test harness.

## GOODQ_STEP_TIMEOUT_MS

- Surfaces: cli/watchdog.py:625, cli/watchdog.py:716, cli/watchdog.py:813, scripts/sync_env_local.ps1:4, steps/common/conda_runner.py:66
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Per-step timeout override for conda runner/watchdog paths.

## GOODQ_SUMMARIES_PREVIEW

- Surfaces: cli/conduits_memory.py:100, cli/conduits_memory.py:101
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/ui
- Safe if unset: Yes (defaults false)
- Notes: Enables summary preview features.

## GOODQ_SUMMARY_TTL_HOURS

- Surfaces: scripts/sync_env_local.ps1:5, steps/common/memory.py:511
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Optional TTL override for summary memory rows.

## GOODQ_VAULT_ROOT

- Surfaces: scripts/health/pull_health_export.py:19, scripts/health/pull_health_export.py:49, steps/common/sensitive_staging.py:18
- Default in code: none (or inherited via config resolution)
- Required in strict mode: Conditional
- Affects: optional integration
- Safe if unset: No for non-dry-run pull_health_export.py
- Notes: Vault write root for passive health export script.

## GOODQ_VECTOR_DEBUG

- Surfaces: steps/common/epistemic_formatter.py:135, steps/common/epistemic_formatter.py:142, steps/common/memory.py:477, steps/common/memory_commit_events.py:42, steps/common/memory_provenance.py:13, steps/common/memory_router.py:48, steps/common/qdrant_client.py:291, steps/common/qdrant_client.py:41, steps/common/retrieval_events.py:40
- Default in code: ""
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Enables extra vector/memory debug diagnostics.

## GOODQ_VERBOSE

- Surfaces: scripts/sync_env_local.ps1:4, steps/common/conda_runner.py:63
- Default in code: ""
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Verbosity toggle for selected runtime paths.

## GOODQ_WSL_AUDIO_COMPUTE_TYPE

- Surfaces: scripts/smoke_phase_a.py:163, steps/common/profile_config.py:78
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Override WSL audio compute type in baseline profile.

## GOODQ_WSL_AUDIO_DEVICE

- Surfaces: scripts/smoke_phase_a.py:162, steps/common/profile_config.py:77
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Override WSL audio device resolution for baseline profile.

## GOODQ_WSL_AUDIO_MIXED_PRECISION

- Surfaces: scripts/smoke_phase_a.py:164, steps/common/profile_config.py:79
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Override WSL mixed precision in baseline profile.

## GOODQ_WSL_DISTRO

- Surfaces: LAUNCH_GOODQ.ps1:107, LAUNCH_GOODQ.ps1:377, api/main.py:83, configs/config.yaml:44, scripts/INSTALL_WSL2_AUDIO.bat:48, scripts/_lib/interpreter_bindings.bat:4, scripts/_lib/interpreter_bindings.bat:8, scripts/_lib/interpreter_bindings.ps1:5, scripts/bootstrap_verify.py:64, scripts/bootstrap_verify.py:66 ...
- Default in code: "Ubuntu", Ubuntu
- Required in strict mode: No
- Affects: runtime/bootstrap/service
- Safe if unset: Yes (defaults to Ubuntu)
- Notes: WSL distro binding used by launcher + bridge + setup.

## GOODQ_WSL_MODEL_PATH

- Surfaces: scripts/wsl/install_vllm_service.sh:9
- Default in code: /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct
- Required in strict mode: No
- Affects: install/service
- Safe if unset: Yes (script default path)
- Notes: WSL vLLM model path override.

## GOODQ_WSL_PROJECT_ROOT

- Surfaces: scripts/wsl/install_audio_service.sh:13, scripts/wsl/install_audio_service.sh:6, wsl2_audio/setup_wsl2_audio.sh:23
- Default in code: canonical WSL-mounted repo root (`/mnt/<drive>/<repo_root>`)
- Required in strict mode: No
- Affects: install/service
- Safe if unset: Yes (defaults to canonical WSL-mounted repo root in install scripts)
- Notes: WSL-side repo path for service installers.

## GOODQ_WSL_USER

- Surfaces: api/main.py:84, configs/config.yaml:45, scripts/bootstrap_verify.py:92, scripts/setup_wsl2_audio_fast.py:16, scripts/setup_wsl2_audio_userspace.py:15, scripts/wsl/install_audio_service.sh:10, scripts/wsl/install_audio_service.sh:6, scripts/wsl/install_vllm_service.sh:6, scripts/wsl2_audio_bridge.py:29, scripts/wsl2_audio_bridge.py:34 ...
- Default in code: "", $(whoami), auto
- Required in strict mode: Conditional
- Affects: runtime/bootstrap/service
- Safe if unset: Conditional (required when GOODQ_REQUIRE_WSL_AUDIO=1 in bridge)
- Notes: Deterministic WSL identity override.

## GOODQ_WSL_VLLM_HOME

- Surfaces: scripts/wsl/install_vllm_service.sh:8
- Default in code: ${WSL_HOME
- Required in strict mode: No
- Affects: install/service
- Safe if unset: Yes (defaults to /home/<wsl_user>/vllm_server)
- Notes: WSL vLLM service home.

## GOODQ_WSL_WORKSPACE

- Surfaces: api/main.py:87, scripts/bootstrap_verify.py:92, scripts/setup_wsl2_audio.py:16, scripts/wsl/install_audio_service.sh:12, scripts/wsl/install_audio_service.sh:6, scripts/wsl2_audio_bridge.py:42, scripts/wsl2_audio_bridge.py:76, wsl2_audio/start_wsl2_service.bat:10, wsl2_audio/start_wsl2_service.bat:34, wsl2_audio/start_wsl2_service.bat:48 ...
- Default in code: "/home/<resolved_user>/goodq_audio"
- Required in strict mode: No
- Affects: runtime/bootstrap/service
- Safe if unset: Yes (defaults to /home/<resolved_user>/goodq_audio)
- Notes: Primary WSL workspace root.

## HA_TOKEN

- Surfaces: configs/config.yaml:104, scripts/sync_env_local.ps1:9, steps/home_assistant_status/step.py:22, steps/home_assistant_status/step.py:23
- Default in code: none (or inherited via config resolution)
- Required in strict mode: Conditional
- Affects: optional integration
- Safe if unset: Conditional (required for Home Assistant status step)
- Notes: Home Assistant auth token.

## HF_AUTH_TOKEN

- Surfaces: scripts/utils/validate_critical_fixes.py:33
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: dev utility
- Safe if unset: Yes
- Notes: Used by validation utility script; not core runtime.

## HF_DATASETS_CACHE

- Surfaces: scripts/download_datasets.py:21, scripts/download_datasets.py:84, scripts/system_readiness_check.py:62, steps/common/conda_runner.py:42
- Default in code: str(cache_root
- Required in strict mode: No
- Affects: bootstrap
- Safe if unset: Yes
- Notes: Datasets cache path.

## HF_DATASETS_OFFLINE

- Surfaces: scripts/mission_launch.ps1:49, scripts/sync_env_local.ps1:6, steps/emotion_classify/step.py:81, steps/sentiment/step.py:51, steps/sentiment/step_fixed.py:114
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Force datasets offline mode.

## HF_DOWNLOAD_GATED

- Surfaces: scripts/download_datasets.py:109, scripts/download_datasets.py:91
- Default in code: ''
- Required in strict mode: No
- Affects: bootstrap
- Safe if unset: Yes
- Notes: Allow gated dataset pulls when set truthy.

## HF_HOME

- Surfaces: cli/run_ingestion.py:104, cli/run_ingestion.py:517, configs/paths.py:177, scripts/audit_vision_pipeline.py:320, scripts/bootstrap_models.py:172, scripts/bootstrap_models.py:24, scripts/bootstrap_models.py:63, scripts/cache_readiness_check.py:115, scripts/cache_readiness_check.py:72, scripts/cache_readiness_check.py:77 ...
- Default in code: canonical model-cache root, unset env fallback, and env-backed resolution (`HF_HOME`)
- Required in strict mode: No
- Affects: runtime/bootstrap
- Safe if unset: Yes (multiple script defaults)
- Notes: Hugging Face cache root.

## HF_HUB_ENABLE_HF_TRANSFER

- Surfaces: cli/run_ingestion.py:516, scripts/bootstrap_models.py:28, scripts/cache_readiness_check.py:82, scripts/download_datasets.py:89, scripts/prepare_step_envs.ps1:33, scripts/sync_env_local.ps1:9, scripts/system_readiness_check.py:114, scripts/system_readiness_check.py:174, scripts/system_readiness_check.py:261, scripts/system_readiness_check.py:268 ...
- Default in code: "0", '0', '1'
- Required in strict mode: No
- Affects: runtime/bootstrap
- Safe if unset: Yes
- Notes: HF transfer optimization toggle.

## HF_HUB_TOKEN

- Surfaces: scripts/download_datasets.py:86, scripts/system_readiness_check.py:241
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: bootstrap/optional integration
- Safe if unset: Yes
- Notes: HF token alias used by dataset/bootstrap scripts.

## HF_TOKEN

- Surfaces: scripts/bootstrap_models.py:105, scripts/cache_readiness_check.py:83, scripts/cache_readiness_check.py:85, scripts/cache_readiness_check.py:87, scripts/download_datasets.py:115, scripts/download_datasets.py:75, scripts/download_datasets.py:86, scripts/download_datasets.py:88, scripts/download_datasets.py:9, scripts/pin_model_versions.py:81 ...
- Default in code: hf_token, token
- Required in strict mode: Conditional
- Affects: runtime/bootstrap/optional integration
- Safe if unset: Conditional (required for gated HF assets)
- Notes: Primary Hugging Face token.

## HUGGINGFACE_TOKEN

- Surfaces: wsl2_audio/HF_CLI_LOGIN_GUIDE.md:113, wsl2_audio/HF_CLI_LOGIN_GUIDE.md:119, wsl2_audio/HF_CLI_LOGIN_GUIDE.md:148, wsl2_audio/HF_QUICK_REF.txt:41, wsl2_audio/PIPELINE_UPGRADE.md:289, wsl2_audio/QUICK_REFERENCE.md:41, wsl2_audio/QUICK_REFERENCE.md:78, wsl2_audio/TEST_RESULTS.md:178, wsl2_audio/TEST_RESULTS.md:22, wsl2_audio/TEST_RESULTS.md:30 ...
- Default in code: ""
- Required in strict mode: No
- Affects: wsl service
- Safe if unset: Yes (WSL scripts attempt aliasing from HF_TOKEN)
- Notes: WSL-facing token alias consumed by audio service/process paths.

## OPENAI_API_KEY

- Surfaces: LAUNCH_GOODQ.ps1:278, scripts/preflight_check.ps1:252, scripts/preflight_check.ps1:272, scripts/preflight_check.ps1:78, scripts/sync_env_local.ps1:8, scripts/utils/check_llm_availability.py:55, steps/llm_chat/step.py:102
- Default in code: none (or inherited via config resolution)
- Required in strict mode: Conditional
- Affects: runtime/optional integration
- Safe if unset: Conditional (needed for OpenAI-backed flows)
- Notes: Used by llm_chat step and preflight checks.

## PYANNOTE_AUDIO_AUTH

- Surfaces: scripts/sync_env_local.ps1:7, steps/audio_diarize/step.py:306
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime/optional integration
- Safe if unset: Yes
- Notes: Fallback auth token env for diarization.

## PYANNOTE_TOKEN

- Surfaces: configs/model_registry.yaml:39, scripts/bootstrap_models.py:106, scripts/cache_readiness_check.py:83, scripts/cache_readiness_check.py:85, scripts/cache_readiness_check.py:88, scripts/diagnostics/verify_phase1.ps1:88, scripts/pin_model_versions.py:82, scripts/sync_env_local.ps1:7, scripts/system_readiness_check.py:176, scripts/system_readiness_check.py:262 ...
- Default in code: token
- Required in strict mode: Conditional
- Affects: runtime/optional integration
- Safe if unset: Conditional (needed for diarization models)
- Notes: Primary pyannote token env.

## TORCH_HOME

- Surfaces: cli/run_ingestion.py:518, configs/paths.py:178, scripts/audit_vision_pipeline.py:321, scripts/bootstrap_models.py:173, scripts/bootstrap_models.py:25, scripts/bootstrap_models.py:63, scripts/cache_readiness_check.py:78, scripts/cache_readiness_check.py:81, scripts/command_center.ps1:106, scripts/command_center.ps1:109 ...
- Default in code: canonical model-cache root, unset env fallback, and env-backed resolution (`TORCH_HOME`)
- Required in strict mode: No
- Affects: runtime/bootstrap
- Safe if unset: Yes
- Notes: Torch cache root.

## TRANSFORMERS_CACHE

- Surfaces: configs/paths.py:179, scripts/audit_vision_pipeline.py:322, scripts/bootstrap_models.py:26, scripts/sync_env_local.ps1:6, scripts/utilities/gpu_config.py:50, scripts/utils/check_gpu_status.py:162, steps/common/conda_runner.py:41, steps/image_caption/step.py:42, steps/sentiment/step.py:21, steps/sentiment/step_fixed.py:26 ...
- Default in code: canonical transformers cache root (`<GOODQ_DATA_ROOT>/models/transformers`) and unset env fallback
- Required in strict mode: No
- Affects: runtime/bootstrap
- Safe if unset: Yes
- Notes: Transformers cache path.

## TRANSFORMERS_OFFLINE

- Surfaces: scripts/mission_launch.ps1:50, scripts/sync_env_local.ps1:7, steps/emotion_classify/step.py:81, steps/sentiment/step.py:51, steps/sentiment/step_fixed.py:113
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: runtime
- Safe if unset: Yes
- Notes: Force transformers offline mode.

## elevenlabs_voice_id

- Surfaces: configs/config.yaml:95, scripts/config_schema.py:77, scripts/sync_env_local.ps1:8, steps/tts/step.py:11, steps/tts/step.py:23, steps/tts/step.py:29, steps/tts/step.py:78
- Default in code: none (or inherited via config resolution)
- Required in strict mode: No
- Affects: optional integration
- Safe if unset: Yes
- Notes: Legacy lowercase alias for voice id.

## Legacy/Non-Contract Literals (Detected)

- `GOODQ_CONFIG_PATH`: scripts/setup/setup_agents.ps1:110
- `GOODQ_DATA_DIR`: scripts/setup/setup_agents.ps1:108
- `GOODQ_PIPELINE_HA_API`: steps/home_assistant_status/step.py:22
- `GOODQ_POINT_ID_NAMESPACE`: steps/common/qdrant_client.py:11, steps/common/qdrant_client.py:66, steps/common/qdrant_client.py:69

These literals are intentionally excluded from `.env.template` because they are deprecated, constant identifiers, or generated-only scaffolding.

## System-Provided / Runtime Ambient Variables (Not in .env.template)

- `CONDA_DEFAULT_ENV`: scripts/comprehensive_gpu_setup.py:202, scripts/gpu_config.py:24, scripts/gpu_config.py:59, steps/common/step_logger.py:113
- `CONDA_EXE`: configs/python_paths.py:59, scripts/INSTALL_AUDIO_DIARIZE_ENV.bat:29, scripts/INSTALL_AUDIO_DIARIZE_ENV.bat:40, scripts/INSTALL_AUDIO_DIARIZE_ENV.bat:51, scripts/INSTALL_AUDIO_DIARIZE_ENV.bat:62, scripts/INSTALL_AUDIO_DIARIZE_ENV.bat:76 ...
- `CONDA_PREFIX`: cli/run_ingestion.py:573, scripts/system_readiness_check.py:93
- `CONDA_ROOT`: scripts/_lib/interpreter_bindings.ps1:25, scripts/_lib/interpreter_bindings.ps1:26, scripts/install_vision_gpu.bat:26, scripts/install_vision_gpu.bat:27, scripts/install_vision_gpu.bat:30, scripts/system_readiness_check.py:94
- `CUBLAS_WORKSPACE_CONFIG`: cli/run_ingestion.py:528, scripts/utilities/gpu_config.py:57
- `CUDA_LAUNCH_BLOCKING`: scripts/diagnose_gpu_pipeline.py:124, steps/common/gpu_config.py:73
- `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE`: scripts/utilities/gpu_config.py:109
- `CUDA_VISIBLE_DEVICES`: cli/run_ingestion.py:524, scripts/comprehensive_gpu_setup.py:188, scripts/comprehensive_gpu_setup.py:4, scripts/diagnose_gpu_pipeline.py:122, scripts/diagnose_gpu_pipeline.py:249, scripts/diagnostics/audit_gpu_steps.py:23 ...
- `LD_LIBRARY_PATH`: wsl2_audio/CUDA_SETUP.md:131, wsl2_audio/CUDA_SETUP.md:26, wsl2_audio/CUDA_SETUP.md:61, wsl2_audio/CUDA_SETUP.md:64, wsl2_audio/QUICK_REFERENCE.md:127, wsl2_audio/QUICK_REFERENCE.md:128 ...
- `LOGNAME`: api/main.py:86, scripts/wsl2_audio_bridge.py:36
- `PIP_DISABLE_PIP_VERSION_CHECK`: configs/paths.py:182, scripts/prepare_step_envs.ps1:101, scripts/prepare_step_envs.ps1:105, scripts/prepare_step_envs.ps1:113, scripts/prepare_step_envs.ps1:134, scripts/prepare_step_envs.ps1:135 ...
- `PIP_NO_CACHE_DIR`: configs/paths.py:181, scripts/prepare_step_envs.ps1:100, scripts/prepare_step_envs.ps1:104, scripts/prepare_step_envs.ps1:112, scripts/prepare_step_envs.ps1:134, scripts/prepare_step_envs.ps1:135 ...
- `PYTHONNOUSERSITE`: `cli/run_ingestion.py::_base_env`, `cli/step_runner.py` top-level default, `configs/paths.py::set_environment_variables`, `scripts/prepare_step_envs.ps1` env guards ...
- `PYTHONPATH`: LAUNCH_GOODQ.ps1:49, LAUNCH_GOODQ.ps1:50, LAUNCH_GOODQ.ps1:82, cli/run_ingestion.py:519, cli/run_ingestion.py:521, cli/run_ingestion.py:572 ...
- `USER`: api/main.py:86, configs/config.yaml:6, scripts/config_schema.py:11, scripts/wsl2_audio_bridge.py:36, wsl2_audio/audio_bridge.py:63, wsl2_audio/setup_windows.ps1:52
- `USERNAME`: api/main.py:86, scripts/setup_wsl2_audio_fast.py:25, scripts/setup_wsl2_audio_userspace.py:24, scripts/wsl2_audio_bridge.py:36
- `USERPROFILE`: scripts/install_pipeline_windows.ps1:9, scripts/preflight_check.ps1:69
- `VIRTUAL_ENV`: wsl2_audio/check_cuda.py:105, wsl2_audio/check_cuda.py:87, wsl2_audio/check_cuda.py:93
- `WSL_DISTRO_NAME`: configs/python_paths.py:93

These variables come from shell/OS/conda runtime and are not part of the GoodQ operator contract.
