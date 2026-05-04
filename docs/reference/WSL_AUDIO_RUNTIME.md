<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-04 -->

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
- The configured expected / bootstrap-target WSL audio torch lane is:
  - `torch==2.5.1+cu121`
  - `torchvision==0.20.1+cu121`
  - `torchaudio==2.5.1+cu121`
- The bootstrap installers now stage and honor `wsl2_audio/requirements-bootstrap-constraints.txt` to keep later dependency installs from drifting off that lane.
- The active sourced worker must still be inspected on the target machine. If the
  runtime recorder reports a different installed lane, that is environment truth
  to investigate, not a reason to pretend the target lane is installed.

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

## Runtime Black Box Recorder

The WSL audio preflight now emits a read-only runtime recorder payload. Run it
directly when accelerated audio behavior needs inspection:

```powershell
conda run -n goodq_core python scripts/wsl_audio_preflight.py --compact
```

The recorder does not install packages, mutate WSL, change configs, or select
an audio backend. It records the sourced WSL runtime as observed:

- `runtime_black_box.package_versions`
- `runtime_black_box.torch`
- `runtime_black_box.torchvision_abi`
- `runtime_black_box.torchaudio`
- `runtime_black_box.torchcodec`
- `runtime_black_box.ffmpeg`
- `runtime_black_box.ffmpeg_libraries`
- `torch_lane_status`
- `torchcodec_ready`
- `torchcodec_detail`
- `runtime_warnings`

The bridge preserves a compact copy as `bridge_runtime_probe` on success and
error payloads so scene-level WSL audio outcomes can be audited without
guessing which runtime produced them.

Current interpretation rules:

- `torch_lane_status=differs_from_expected` means the sourced worker differs
  from the configured expected lane. It is an environment truth warning, not an
  ingestion failure by itself.
- `torchcodec_ready=false` means torchcodec-backed decoding is unavailable;
  if the WSL worker still completes through its active decoding path, this is
  a surfaced degradation, not a hidden success.
- `torchcodec_ready=false` is not the same as `abi_ready=false`; the current
  WSL worker can still complete by passing preloaded audio into the model stack.
- `pyannote_warned_torchcodec_decoder_unavailable` records that pyannote saw
  the decoder warning during the existing diarization probe.
- These fields are observer truth only. They must not trigger package changes,
  healing, or reruns without a separate operator decision.

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

## Current Cost / Scheduling Doctrine

WSL audio health and WSL audio cost are separate operator questions.

Recent controlled witnesses from 2026-05-01 through 2026-05-03 show the
unified WSL path is stable and truthful, but expensive enough to drive
full-run scheduling:

- evidence window: `234` `audio_unified_wsl2` step rows across four fresh
  witnesses
- status: all observed `audio_unified_wsl2` rows completed `ok`
- WSL audio timing: about `58.2s` p50 and `62.1s` p95 per scene
- WSL audio share: about `61.6%` to `63.9%` of summed step duration in the
  recent one- and two-episode witnesses
- typical one-episode cost: about `36` to `39` summed WSL-audio minutes for
  `38` to `40` scenes
- typical two-episode cost: about `75` to `77` summed WSL-audio minutes for
  `78` scenes

The recent data only weakly correlates WSL worker duration with scene-audio
duration. Treat the current path as a mostly per-scene fixed-cost lane.

Black-box witness on 2026-05-04:

- run root: `reports/fresh_ingest_runs/20260504_074335_wsl_black_box_02x02_witness/`
- runtime run id: `8a093042-6d8d-461e-81d6-5061e6d5d08b`
- source episode: `02x02 - The Pony Remark`
- scenes: `38`
- `audio_unified_wsl2`: `38 / 38` ok
- `bridge_runtime_probe`: present in all `38` scene results and all `38`
  canonical scene-manifest scenes
- observed worker lane: `torch==2.8.0+cu128`,
  `torchvision==0.23.0+cu128`, `torchaudio==2.8.0+cu128`
- recorder status: `torch_lane_status=differs_from_expected`,
  `torchcodec_ready=false`, `torchcodec_detail` includes
  `ffmpeg_shared_library_unavailable` and `torch_abi_symbol_mismatch`
- Phase 6 and Qdrant: healthy
- recurrence readout: one recovered optional native retry in `object_detect`,
  one expected `audio_silent` CLAP skip on the final short scene, and no
  unrecovered failures

Operator meaning: this witness proves the recorder reaches scene-level truth
surfaces and exposes the active WSL lane precisely. It does not approve a
package promotion or downgrade by itself.

Same-scene timing probes on 2026-05-04 used three existing `02x02` scene
chunks from `reports/fresh_ingest_runs/20260503_135503_native_retry_attribution_02x02_witness/`.
They compared the canonical unified WSL worker against a diagnostic forced-CPU
Windows transcript-only path:

- scenes sampled: `9`, `22`, and `33`
- WSL unified timing: about `49.4s` to `59.1s`
- Windows forced-CPU transcript-only timing: about `28.9s` to `31.4s`
- transcript overlap stayed high: word-set overlap about `0.882` to `1.000`
- WSL produced extra persisted surfaces that the transcript-only probe did not:
  diarization, speaker counts, emotion, and speaker voice signature inputs

Operator meaning: the current WSL lane is not just "transcription on Linux".
It is the unified audio intelligence bundle. A cheaper transcript-only path is
real evidence for future scheduling work, but it is not an equivalent
replacement for unified WSL audio.

Operator implications:

- healthy WSL audio means usable and truthful, not automatically cheap
- schedule multi-episode and full-season witnesses around the WSL audio budget
- use `step_runs.jsonl` and the read-only control recurrence latency summary
  for current timing truth
- do not use historical projected GPU speedup tables as the current scheduling
  contract without a fresh same-scene comparison for the specific audio surface
  being considered

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

Current operator proof:

- the repaired WSL path is validated on fresh Season 5 material, not just on
  direct single-scene repros
- the current projection smoke proves these fields persist through:
  - `scene_ingest_results.json`
  - `scene_manifest.json`
  - `temporal_index.json`
- speaker continuity is therefore no longer limited to raw processor payloads
  or live logs

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
- `diarization_status` / `emotion_status` are part of the active persisted truth
  surface, not debug-only side channels.

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
