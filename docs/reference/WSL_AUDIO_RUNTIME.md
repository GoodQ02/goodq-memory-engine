<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-19 -->

# WSL Audio Runtime Reference

This is the current operator-facing truth surface for the WSL unified audio
path.

## Current Execution Model

- Windows remains the primary runtime host.
- WSL is an optional compute extension for accelerated audio.
- The active accelerated path is the unified WSL audio worker rooted at `GOODQ_WSL_WORKSPACE`.
- The worker is local-first and offline-capable once the exact model chain is
  staged in the active runtime cache.
- When WSL is unavailable or degraded and strict mode is not enabled, the system may fall back to the Windows-safe audio path.
- Fallback is structured and non-recursive: once a scene downgrades, that call path does not bounce back into WSL.
- The active cache root is defined by the sourced WSL runtime. If the mounted
  shared cache does not contain the exact diarization chain, the runtime may
  fall back to the local WSL cache instead of presenting a false-ready state.

## Deterministic Environment Contract

These variables define the current WSL runtime identity:

- `GOODQ_WSL_DISTRO`
- `GOODQ_WSL_USER`
- `GOODQ_WSL_WORKSPACE`
- `GOODQ_REQUIRE_WSL_AUDIO`
- `GOODQ_HOST_PROFILE`

Notes:

- `GOODQ_REQUIRE_WSL_AUDIO=1` converts WSL audio into a fail-fast requirement.
- `GOODQ_WSL_USER` and `GOODQ_WSL_WORKSPACE` are part of deterministic host setup on accelerated systems.
- The current conservative WSL audio torch lane is:
  - `torch==2.5.1+cu121`
  - `torchvision==0.20.1+cu121`
  - `torchaudio==2.5.1+cu121`
- The bootstrap installers now stage and honor `wsl2_audio/requirements-bootstrap-constraints.txt` to keep later dependency installs from drifting off that lane.

## Readiness States

Current preflight / bootstrap / doctor surfaces distinguish:

- `gpu_ready`
  - CUDA-capable torch is available in the WSL worker runtime
- `transcription_ready`
  - the WSL worker can import `faster_whisper` and the core transcription path
- `process_import_ready`
  - the live `process_audio.py` worker imports successfully
- `diarization_ready`
  - the sourced WSL runtime can resolve and load the configured diarization
    pipeline offline from its active cache root

Interpretation:

- transcription-ready but diarization-degraded is a valid warning state
- a single WSL warning does not automatically mean the whole audio worker is unusable

## Bootstrap / Doctor Meaning

- bootstrap and doctor treat WSL audio as:
  - `pass` when the accelerated worker is fully ready
  - `warn` in doctor/verify mode when transcription is usable but ABI or diarization is degraded
  - `fail` only when strict WSL audio is required and the worker is not usable

Additional operator truth:

- bootstrap install does **not** treat `runtime_ready=true` as sufficient on its own
- WSL audio must be both `runtime_ready=true` and `abi_ready=true` before bootstrap considers the workspace ready
- canonical ingestion does **not** select the WSL backend when `abi_ready=false`
- when WSL is ABI-degraded and strict mode is not enabled, the system should fall back to the Windows-safe audio path instead of attempting the canonical WSL worker
- `diarization_ready=true` is only valid when the sourced runtime can load the
  configured diarization repo chain offline; import success and token presence
  alone are not enough
- WSL bootstrap installers must end with:
  - `python -m pip check == 0`
  - the validated torch / torchvision / torchaudio trio still installed
  - successful `torchvision.ops.nms` import before the environment is considered ready

## Runtime Error Surfacing

When the WSL processor exits nonzero, bridge diagnostics may include:

- `bridge_error_reason`
- `bridge_error_details.processor_error`
- `bridge_error_details.processor_traceback_tail`
- `bridge_error_details.processor_transcription_status`
- `bridge_error_details.processor_diarization_status`
- `bridge_error_details.processor_emotion_status`
- `bridge_error_details.processor_embeddings_status`

These fields are the first place to look when a WSL run reports a generic
nonzero return code.

The successful-path bridge surface should also preserve:

- `diarization_status`
- `diarization_error`
- `diarization_note`
- `emotion_status`
- `emotion_error`

This keeps partial sub-step failures visible even when the overall WSL call
returns success.

## Successful Payload Surface

Successful unified WSL payloads now carry, in addition to transcript / diarization / emotion / embeddings:

- `audio_backend_selected`
- `audio_backend_effective`
- `audio_backend_downgraded`
- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`
- `diarization_status`
- `diarization_error`
- `diarization_note`
- `emotion_status`
- `emotion_error`

Operator meaning:

- `speaker_transcript` is the aligned speaker-owned text surface used by higher layers.
- `speaker_voice_signatures` is the per-speaker pattern surface used by the identity stitching layer.
- `speaker_voice_signature_meta` records whether signatures were emitted and which minimum thresholds applied.

Current runtime thresholds for signature emission are:

- minimum voiced audio: `4.0s`
- minimum usable segments: `2`
- minimum per-segment duration: `0.75s`

See:
- [`docs/architecture/IDENTITY_STITCHING_CONTRACT.md`](../architecture/IDENTITY_STITCHING_CONTRACT.md)

## Related Contracts

- Platform contract:
  [`docs/reference/PLATFORM_SUPPORT.md`](PLATFORM_SUPPORT.md)
- Environment map:
  [`docs/reference/indexes/ENVIRONMENT_INDEX.md`](indexes/ENVIRONMENT_INDEX.md)
- GPU / LLM / WSL index:
  [`docs/guides/gpu/GPU_LLM_WSL_INDEX.md`](../guides/gpu/GPU_LLM_WSL_INDEX.md)
- Segmentation shadow contract:
  [`docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`](../technical/SEGMENTATION_ARTIFACT_CONTRACT.md)
