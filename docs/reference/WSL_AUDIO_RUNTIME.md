<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-01 -->

# WSL Audio Runtime Reference

This is the current operator-facing truth surface for the WSL unified audio path.

## Current Execution Model

- Windows remains the primary runtime host.
- WSL is an optional compute extension for accelerated audio.
- The active accelerated path is the unified WSL audio worker rooted at `GOODQ_WSL_WORKSPACE`.
- The worker is local-first and offline-capable once models are staged in the WSL workspace/cache.
- When WSL is unavailable or degraded and strict mode is not enabled, the system may fall back to the Windows-safe audio path.
- Fallback is structured and non-recursive: once a scene downgrades, that call path does not bounce back into WSL.

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

## Readiness States

Current preflight / bootstrap / doctor surfaces distinguish:

- `gpu_ready`
  - CUDA-capable torch is available in the WSL worker runtime
- `transcription_ready`
  - the WSL worker can import `faster_whisper` and the core transcription path
- `process_import_ready`
  - the live `process_audio.py` worker imports successfully
- `diarization_ready`
  - `pyannote.audio` imports successfully and required auth/token state is present

Interpretation:

- transcription-ready but diarization-degraded is a valid warning state
- a single WSL warning does not automatically mean the whole audio worker is unusable

## Bootstrap / Doctor Meaning

- bootstrap and doctor treat WSL audio as:
  - `pass` when the accelerated worker is fully ready
  - `warn` when transcription is usable but ABI or diarization is degraded
  - `fail` only when strict WSL audio is required and the worker is not usable

## Runtime Error Surfacing

When the WSL processor exits nonzero, bridge diagnostics may include:

- `bridge_error_reason`
- `bridge_error_details.processor_error`
- `bridge_error_details.processor_traceback_tail`
- `bridge_error_details.processor_transcription_status`
- `bridge_error_details.processor_diarization_status`
- `bridge_error_details.processor_emotion_status`
- `bridge_error_details.processor_embeddings_status`

These fields are the first place to look when a WSL run reports a generic nonzero return code.

## Successful Payload Surface

Successful unified WSL payloads now carry, in addition to transcript / diarization / emotion / embeddings:

- `audio_backend_selected`
- `audio_backend_effective`
- `audio_backend_downgraded`
- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`

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
