<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-01 -->

# WSL Audio Runtime Reference

This is the current operator-facing truth surface for the WSL unified audio
path.

## Current Execution Model

**November 8 local validation checkpoint — not deployed:** the recording
adapter accepts optional `audio.recording_engine.native_scratch_root` with
`transport=wsl`. It must name a dedicated absolute directory on a persistent
Linux filesystem, for example `/home/<user>/.cache/goodq-recording`. The default
is unset; existing runtime configuration is unchanged. A Windows drive exposed
under `/mnt/<drive>` is rejected as the scratch root. Moving Windows folders
between drive letters does not remove this filesystem boundary.

The existing Windows recording caller remains the owner. Native scratch contains
one shared cache of hash-verified Windows-hosted model assets and small worker
source snapshots, plus one isolated resumable directory per job. Models already
on a native filesystem are read in place. The repository, original media,
saved-library stores and encoder package/environment are not duplicated or moved.
Original media is read in place for decoding and integrity checks; decoded PCM
and subsequent window/checkpoint work live in Linux scratch. No full input-video
copy is created for an audio job.

New evidence uses `config_identity_method=model_manifest_without_locations_v1`:
model locations are excluded from analysis configuration identity, while hashes,
revisions and analysis settings remain included. The same worker/input/settings
produce the same recording ID in mounted and staged execution. Old artifacts
retain their existing IDs and validation semantics; this does not rewrite them
or promise ID equality across different worker revisions.

Final evidence, scene JSON and referenced review media are hash-verified during
export. Windows checks the export manifest and existing scene/review bindings
before writing its reusable job receipt. Only that acknowledgement permits removal
of the owned native job directory, including PCM and checkpoints.
Failed/interrupted or incomplete jobs retain checkpoints. Completed job replay
uses the Windows handle; shared model/code caches remain reusable. Cleanup failure
is visible and retries on the next request without rerunning accepted inference.
Retirement intent is recorded outside the job tree before deletion, so partial
removal of its internal ownership marker does not prevent a verified retry.
There is no global cache eviction or cleanup of other worktrees/experiments.

Optional-model staging errors are exported in `native-staging.json` and passed to
the worker. Supported absence still applies to silence; attempted optional stages
report errors without loading unverified assets or silently changing models.

A Linux supervisor bounds the whole operation, including locks, staging and
export, and terminates its process group on timeout. The Windows caller holds a
pipe open for the invocation; disconnect closes it and cancels Linux work. The
worker is never launched after the shared deadline expires. Finalization uses
the same supervised transport.

Focused caller checks and short synthetic-silence WSL fault probes cover
path-neutral IDs, export recovery, partial retirement, optional-stage failure,
timeouts and caller cancellation. This is not speech-model or full-movie
qualification. After repairing the reproduced Windows receipt-discovery race,
the November 8 full isolated rerun passed 7,077 unit tests and seven subtests,
plus all 54 Windows startup tests, with zero failures and zero skips. All ten PDF
tests ran with the installed parser exposed through process-local configuration;
12 deprecation warnings remain. Source, the speech gate and retained evidence
were unchanged during testing. Receipts are in `tmp/fs-20261108-001/REPORT.md`;
the previous failed run remains retained.

The subsequent 301-second retained-audio comparison exercised both storage
layouts through the Windows recording caller. Staging, interruption/resume,
verified export, acceptance/retirement and completed-handle reuse passed. Both
layouts preserved 41 completed checkpoint files and produced exactly equal
evidence and scene outputs with stable recording IDs. Native resume added no
shared-cache copies; original source media stayed in place. Historical exports
also remained compatible through read-only consumers. Evidence is in
`tmp/native-long-20261108-001/REPORT.md`.

Native worker time was 3.85% lower in that single warm pair; export took 29.791
seconds. A post-acceptance benchmark lock-inspection failure prevents a clean
matched end-to-end caller timing. No end-to-end speedup, independent quality or
whole-movie acceptance is claimed. Deployment remains held.

The clean repeat with the corrected helper captured both full Windows caller
paths: native initial plus resume took 674.295 seconds versus mounted 638.376
seconds, 5.63% longer. Native worker time was 3.54% lower; staging took 17.871
seconds and export 30.163 seconds. This single warm pair ran native first with
a fresh shared cache. It confirms staging, checkpoint preservation, recognition
reuse, exact output/ID equality, 162-file Windows export and historical consumer
compatibility, without establishing a whole-movie speedup or migration benefit.
Source, gate, models and retained evidence were unchanged. Complete timings and
preservation receipts are in `tmp/native-clean-e2e-20261108-001/REPORT.md`;
the earlier helper failure remains retained. No product source or live
configuration changed, and deployment remains held.
The subsequent closure removes the duplicate target resolution in `_inside`
while retaining every containment, hash, acceptance and retirement check.
106 focused caller/fault tests, a real short WSL workflow and real symlink/byte
corruption checks passed. No new long-recording performance claim is made.
Git now pins audio worker Python files to LF because raw source bytes participate
in recording identity. Windows checkout previously converted some files to CRLF
and changed the fingerprint without changing Python behavior. Git checkout tests
with both autocrlf settings and real Windows/WSL worker hashes now agree;
existing artifact IDs remain readable and are not rewritten.
The repair is committed to private `dev`; secondary worktrees are retired and
historical artifacts remain at their recorded paths. The runtime is stopped,
with no deployment. See the `closure receipt` (omitted from public source)
and `PROJECT.md` for source disposition and evidence.

**November 4 source checkpoint:** private dev contains the opt-in recording
engine and shared worker transport repairs. Default configuration keeps
`audio.recording_engine.enabled=false`; publication is not live activation.
`wsl2_audio/recording_engine.py` owns the recording request and scene projection,
`recording_audio.py` owns bounded decoding, and `eligibility.py` owns admission.
Generic probing uses common protocol/format restrictions; MOV-only external-track
options are applied to decoding after container identification. Cached FFmpeg
4.3/8.1 caller checks and hosted CI pass. Independent audio quality remains
unqualified; see [PROJECT.md](../../PROJECT.md) and the
`dated evidence checkpoint` (omitted from public source).
The earlier notes below retain their original source/deployment scopes and do
not direct a fresh agent to activate or reinstall a worker.

**October 31 source candidate, isolated validation only:**
`audio.transcribe.temperature` defaults to the scalar `0.0`; allowed values are
finite numbers from zero to one. Sampling requires an explicit positive value;
temperature schedules are unsupported. Direct video, standalone and step dispatch
project this policy through `unified_transcription_options`. Both worker passes
receive the same temperature, including the vocabulary-free timing retry.
Direct worker invocation without a request uses `processing.temperature`, default
zero. Windows local Faster-Whisper also consumes the configured scalar.

The worker records `transcription_decoding` (policy `single_temperature_v1`,
temperature, source, sampling/fallback flags, beam size and resolved primary/retry
options). The unified bridge and retained transcription callers preserve it in
`transcript_meta`, including per-region receipts. An old worker that ignores an explicit policy is
reported as `transcription_policy_unconfirmed`, never as successful configured
transcription. Synchronize source/worker as a coordinated deployment after its
approval boundary. Historical results remain readable. This policy removes the
automatic temperature escalation; it does not guarantee accuracy, repeatability
across versions/hardware, or deterministic summaries. November 1 source now
shares the policy with retained Windows Faster-Whisper, the standalone WSL helper,
and the transcription-only compatibility caller. Their isolated qualification
scope is recorded in `tmp/audio-callers-contract-20261101-001/RESULT.md`.
The optional whisper.cpp adapter follows the same coverage/bounds rules but has
not been qualified against an installed CLI executable; it reports word alignment
as unavailable rather than treating segment/token times as aligned words.

The subsequent isolated quality comparison is recorded in
`tmp/audio-quality-modernization-20261101-001/RESULT.md`. Cached MOSS/large-v3 and
approved Qwen3-ASR run in the pinned candidate without package changes; none is
promoted by this comparison. VAD-cropped recognition can lose phrase edges, while
the tested context expansion introduces other omissions/hallucinations. Source
coverage and recognition accuracy remain distinct. The speech gate now preserves
exclusion of a phrase's remaining timed words when an outer edge is unavailable.
Such exclusions carry `boundary_status=unresolved` and
`exclusion_scope=observed_word_audio_only`; their bounds are never recovered
phrase timestamps or permission to admit audio. Whole-utterance qualification,
internal word alignment and emotion accuracy remain separate open checks.

The November 1 candidate records language provenance separately in
`transcription_decoding.language`. A configured language is
`configured_not_detected`, with no detection probability; the decoder's synthetic
1.0 must not be presented as measured confidence. Automatic language is an
uncalibrated, unreviewed model estimate. Confirmed zero VAD speech records
`not_applicable_no_detected_speech` and a null probability. Invalid/missing
probability records `language_evidence_unavailable`. The legacy reported language
code is retained; `language_probability` can now be null. This receipt survives
the bridge, persisted index, and scene/timeline APIs. Only the isolated candidate
uses `processing.language=auto`; code switching is not qualified.

Successful worker completion with an empty transcript does not by itself
establish absent or unintelligible speech. Without valid detection evidence the
bridge reports `skipped`, `transcript_outcome=unclassified` and reason
`worker_success_empty_transcript`. Completed Silero VAD with zero speech duration
supports absence. Positive VAD with no decoded words remains
`no_intelligible_speech`, unless the retained rejection evidence supports absence.
Runtime failure remains a separate outcome.

The worker reconciles Whisper's no-speech score with its configured decoder
confidence exception. For a candidate above the no-speech cutoff, both the
decoder log probability and geometric mean of its word probabilities must exceed
the existing decoder confidence cutoff (the latter compared with its exponential).
This word check prevents non-word decoder scores from accepting a weak-word
hallucination. It is a confidence heuristic, not a calibrated probability that
speech exists. No phrase blacklist or source-specific threshold is used.
Missing/invalid confidence evidence cannot establish absence. If any candidate
is retained, all words remain available under the existing mixed-speech policy.

`transcription_quality` retains decoded/accepted counts, rejected candidates,
retained disputed candidates and the confidence calculation/cutoff. Its
`confidence_override.segments` decisions describe individual confidence checks;
`accepted_segment_count` and `rejected_segments` describe the final outcome after
mixed-speech preservation. Only a completed all-candidate rejection can suppress
speech-dependent analysis. Legacy receipts remain readable. These rules qualify
neither exact recognition, true speaker identity nor model-estimated emotion.
Current evidence and remaining acceptance limits belong in `PROJECT.md`.

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

**November 1 isolated candidate:** a workspace may declare
`runtime_manifest.json` with exact Python, Torch CUDA and package versions,
required TorchCodec availability, a dependency-lock digest and SHA-256 digests
for its source, configuration and model files. Declared candidates fail preflight
on missing/mismatched evidence or unavailable required capabilities. The bridge
retains the manifest digest and comparison result in its runtime receipt.
An absent manifest preserves the existing bootstrap-lane classification; an
unreadable or failed declared-manifest probe must not silently become absent.

Preflight loads the diarization model selected by the worker's resolved
configuration through the worker's actual loader. Provisioned local pyannote 4
pipeline directories are supported; the real load checks their referenced assets.
The legacy pinned cache-chain check remains for the configured 3.1 model. Both
`torchaudio.load` and `faster_whisper.audio.decode_audio` decode and compare a
known PCM sample. A declared candidate requires both to pass. Package imports
and dependency-resolver success alone do not establish decoder compatibility.
The worker setup disables pyannote's optional usage telemetry.

The tested candidate's exact dependencies, isolated configuration, model revision
and results live in `tmp/audio-runtime-candidate-20261101-001/`. It uses Torch
2.14.1+cu126, TorchAudio 2.11.1+cpu, TorchCodec 0.17.0+cpu, Transformers 5.22.1,
pyannote.audio 4.0.7 with Community-1, Faster-Whisper 1.2.1, CTranslate2 4.8.4
and PyAV 18.1.0. The CPU audio packages decode audio; inference remains on CUDA.
Speaker inventories use sorted unique labels; the timeline retains the emitted
turn order. This closes observed hash-dependent list-order drift without
renaming speakers or changing their timestamps or scores.
This is an isolated candidate, not a promoted replacement for the live worker or
the bootstrap defaults below. Runtime compatibility does not qualify phrase
boundaries, speaker identity, emotion accuracy or determinism across hardware.

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
- The configured WSL diarization compatibility lane includes:
  - `pyannote.audio==3.3.2`
  - `huggingface-hub==0.35.3`
- The bootstrap installers now stage and honor `wsl2_audio/requirements-bootstrap-constraints.txt` to keep later dependency installs from drifting off that lane.
- `wsl2_audio/requirements-locked.txt` is historical until regenerated from a
  validated worker; it must not override the bootstrap constraints.
- The active sourced worker must still be inspected on the target machine. If the
  runtime recorder reports a different installed lane, that is environment truth
  to investigate, not a reason to pretend the target lane is installed.

## WSL Audio Torch Lane Doctrine

- Bootstrap target: `torch` / `torchvision` / `torchaudio` on `2.5.1+cu121`
- Active observed sourced worker lane: `2.5.1+cu121`
- Active `faster-whisper` lane: `1.2.1`
- Classification: `WSL_AUDIO_LANE_MATCHES_BOOTSTRAP_TARGET`
- Approval state: bootstrap-approved lane observed in the sourced worker

Decision notes:

- Runtime fallback validation on 2026-05-22 observed the active lane as
  functionally ready: GPU, transcription, ABI, and diarization checks passed.
- A fresh three-scene probe processed speech successfully through the unified
  WSL worker with strict WSL audio required.
- There is no ingestion blocker from the active lane based on current evidence.
- October 30: the active `torchaudio==2.5.1+cu121` / `pyannote.audio==3.3.2`
  lane does not require TorchCodec. The preflight decodes a temporary PCM WAV
  through the worker's `torchaudio.load` path and checks samples and sample rate.
  With that check passing on the exact expected lane, absence is explicitly
  `torchcodec_applicability=not_required_for_active_lane`; availability remains
  false. Other versions, failed decoding or a pyannote TorchCodec warning retain
  an unknown applicability and visible warning rather than inheriting this result.
- Bootstrap target must not change without a future explicit lane-promotion
  pass. The applicability above must not be extrapolated to a changed lane.

The emotion preflight imports the configured worker's strict trained checkpoint
loader and feature extractor. The former generic Transformers sequence classifier
used the wrong head and reported newly initialized weights even though the worker
already loaded the correct trained head. `wav2vec_model_load` now records strict
loading, revision, legacy-key mapping and missing inference keys. Readiness requires
strict loading with no missing inference tensors. This proves loading integrity,
not calibrated emotional-state accuracy; predictions remain model estimates.

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
- `wav2vec_enrichment_ready`
  - the sourced WSL runtime can import the pinned Wav2Vec dependency lane and
    resolve the configured Wav2Vec emotion model from the
    canonical cache
- `speaker_signature_ready`
  - the worker can load the pinned ECAPA assets offline with verified hashes;
    readiness is independent of emotion and diarization

Interpretation:

- transcription-ready but diarization-degraded is a valid warning state
- a single WSL warning does not automatically mean the whole audio worker is unusable
- `wav2vec_enrichment_ready=false` is not a base WSL audio failure by itself.
  It means optional emotion may be unavailable; surface it through `emotion_status`.
  ECAPA failure instead sets `speaker_signature_ready=false` and
  `speaker_voice_signature_meta.status=error` when inference is attempted.
  Whole-scene vector production was retired on October 11, 2026: explicit
  `embeddings_status=retired` / `whole_scene_vector_retired` is expected, not
  a readiness failure. Historical vectors remain readable; do not restore the
  retired full-scene inference or use unmarked Wav2Vec fallback for signatures.

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
- `runtime_black_box.audio_decode`
- `runtime_black_box.torchcodec`
- `runtime_black_box.ffmpeg`
- `runtime_black_box.ffmpeg_libraries`
- `torch_lane_status`
- `torchcodec_ready`
- `torchcodec_detail`
- `torchcodec_applicability`
- `audio_decode_ready`
- `wav2vec_enrichment_ready`
- `wav2vec_model_load`
- `runtime_warnings`

The bridge preserves a compact copy as `bridge_runtime_probe` on success and
error payloads so scene-level WSL audio outcomes can be audited without
guessing which runtime produced them.

Current interpretation rules:

- `torch_lane_status=differs_from_expected` means the sourced worker differs
  from the configured expected lane. It is an environment truth warning, not an
  ingestion failure by itself.
- `torchcodec_ready=false` means TorchCodec is unavailable. Check applicability
  separately: `not_required_for_active_lane` requires the exact supported lane
  and a successful active decoder probe. Missing an unused decoder is not a
  degradation of that path. Unknown applicability retains the warning.
- `torchcodec_ready=false` is not the same as `abi_ready=false`; the current
  WSL worker can still complete by passing preloaded audio into the model stack.
- `pyannote_warned_torchcodec_decoder_unavailable` records that pyannote saw
  the decoder warning during the existing diarization probe.
- These fields are observer truth only. They must not trigger package changes,
  healing, or reruns without a separate operator decision.

The API `/api/status` WSL probe must source the configured worker
`setup_cuda_env.sh` under `GOODQ_WSL_WORKSPACE` before checking
`faster_whisper`. A plain WSL `python3` import check is not authoritative for
GoodQ audio readiness.

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
- `pyannote.audio==3.3.2` must remain paired with
  `huggingface-hub==0.35.3`; newer hub API lanes can pass `pip check` while
  still breaking PyAnnote runtime loading
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

Historical note: the following worker lane describes that witness only. The
current 2026-05-22 sourced worker lane is recorded above and matches the
bootstrap target.

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

Current unified WSL payloads retain transcript, diarization and emotion, with
explicit whole-scene embedding retirement and no new whole-scene vector/dimension.
Historical vector payloads remain readable. Additional fields include:

- `audio_backend_selected`
- `audio_backend_effective`
- `audio_backend_downgraded`
- `speaker_transcript`
- `speaker_voice_signatures`
- `speaker_voice_signature_meta`
- `speaker_change_review` (additive source implementation; deployment state in `PROJECT.md`)
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
- `diarization_status=completed_no_speakers` means the diarization worker
  completed but emitted zero speaker tracks. It is neither a failure nor usable
  speaker evidence; it must not enter a signature-backfill candidate set.

Current runtime thresholds for signature emission are:

- minimum voiced audio: `4.0s`
- minimum usable segments: `2`
- minimum per-segment duration: `0.75s`

The ECAPA source integration pins `speechbrain/spkrec-ecapa-voxceleb` at
`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`. The existing model bootstrap provisions
it; inference resolves local assets only and verifies their hashes. A deliberate
`GOODQ_ECAPA_MODEL_DIR` override may point at the same sealed assets. No runtime
download or corpus migration is performed. Worker synchronization includes
`speaker_signature.py`. Source implementation does not imply deployment; see
`PROJECT.md` for current acceptance state.

Selected spans are joined and encoded once into a normalized, version-tagged 192D
signature. Diarization labels remain hypotheses: the same-scene guard may retain
false splits, and mixed voices can still contaminate a signature. Neither this
encoder change nor a high similarity score resolves diarization purity.

See:
- [`docs/architecture/IDENTITY_STITCHING_CONTRACT.md`](../architecture/IDENTITY_STITCHING_CONTRACT.md)

## Speaker-change review evidence

The conservative `collapsed_local_return_v1` observer adds review evidence during
the existing diarization call; it does not run another model or modify signatures,
admission, thresholds, clustering or emotion. It records an exclusive local A-B-A
return collapsed into one final cluster. It cannot certify speaker purity.

The full [field semantics and limits](../architecture/IDENTITY_STITCHING_CONTRACT.md#review-only-collapsed-speaker-change-evidence)
belong to the identity contract. `ok`, `unavailable`, `error` and absent historical
evidence must remain distinguishable. Do not interpret a missing/empty flag list
as verified single-speaker speech or add unmarked fallback inference.

`steps/audio/audio_wsl2_bridge.py` carries the field through the existing scene
payload; the identity ledger projects it onto scene properties independently of
signature eligibility. `/api/system/identity/speaker-reviews` is the read-only API
for `ui/stitching_workbench/`, including scenes without recurring voice patterns.
The separate face/identity workbench is not the review consumer.

October 11 worker/API deployment and one fresh isolated standalone-audio caller/
browser witness passed at `c97e229`. The review flag remained visible without an
eligible signature. Actual API startup required the new endpoint's passive-read
route registration; the repaired startup and HTTP readback passed. This bounded
witness does not qualify full-video orchestration or general accuracy.
Existing ECAPA and overlap-admission deployment witnesses stay completed. Resume
from [PROJECT.md](../../PROJECT.md#next-session-checkpoint) before any sync/restart;
do not reinstall dependencies, rerun prior comparisons or touch the corpus.

## Clear speech emotion input and sound events

The `clear_speech_only_v2` worker policy retains crying, screaming and other
detected vocal sounds separately from emotion estimates. Offline AST AudioSet
inference uses `MIT/ast-finetuned-audioset-10-10-0.4593` at revision
`f826b80d28226b62986cc218e5cec390b1096902`, registered as `acoustic_events_ast`.
The cache is checked by WSL preflight; inference does not download weights.
Worker synchronization includes `acoustic_events.py`.

Ten-second windows with five-second hops retain multi-label sound observations.
They are approximate event intervals, not precise onsets or speech veto masks.
Speaker-bound word runs are assessed separately over their exact sample bounds.
Eligible words still require probability at least 0.8. Selected audio uses the
continuous intersection of word and exclusive speaker support, without changing
either source timestamp. `timing_adjustments` discloses cropped boundaries as
unreviewed. Adjacent same-speaker tracks can jointly cover a word; missing support
or a competing speaker cannot bridge selected runs. When a producer declares
`diarization_timing.boundary_precision=phrase`, whole turns participating in an
overlap remain ineligible: generated phrase bounds are not precise overlap edges.

Speech presence requires either AudioSet Speech at least 0.5 or at least 80% of
the selected interval covered by one Silero speech region. Silero runs once on
the original waveform with threshold 0.5, 100 ms minimum silence and zero padding.
The sources have different false negatives; `speech_presence_basis` records which
supports a selection, without blending their scores. Detector failure is not a
fallback opportunity. Thresholds and resulting estimates remain uncalibrated.

Vocal-event scores at least 0.1 still exclude a run. A music-only disagreement may
receive one contextual check with the same loaded model, limited to 0.5 seconds
on each side. This requires strong target VAD coverage, no competing speaker in
context, and every detected context speech region covered by that same speaker.
Context must score speech at least 0.5 with no excluded labels. Raw target music
evidence remains in `speech_windows`; `acoustic_context` records the disagreement
and exact context bounds. Context audio is never appended to the emotion sample.
Unknown context or any vocal exclusion remains blocked; no waveform repetition,
silence-padding substitution or iterative crop search is used.

Contiguous 0.3-to-six-second runs remain the speech admission evidence used by
ECAPA, with its existing duration/diversity gates unchanged. Emotion scoring now
uses `emotion_input.phrase_selection` with `complete_observed_phrases_v1` instead
of these possibly clipped word runs. Native decoder envelopes and complete-word
alignment are separately identified timing bases, as detailed below. The word
path splits only at observed sentence punctuation or segment ends and requires
every phrase word's original valid, monotonic bounds. Neither rejected words nor
speaker intersections create a new phrase. The native path retains the whole
decoder phrase and its independent timing uncertainty. Overlapping speakers or
a whole phrase outside the existing duration range withhold either kind with an
explicit reason. Long phrases are not cut into arbitrary windows.

Both paths first apply `multi_speaker_phrase_veto_v1`, recorded under
`emotion_input.speaker_purity`. If an observed phrase intersects multiple speaker
labels, its entire interval is excluded before acoustic candidate assessment,
voice sampling or emotion scoring. Word-sized pieces cannot rescue the phrase,
even when diarization presents the speakers as adjacent turns with no detected
overlap. This check does not depend on token confidence or emotion duration limits;
separate phrases with exclusive speaker support remain eligible for the existing
gates. Original words, times, turns and sound events are preserved.
`excluded_phrases` records bounds, source segment, speaker candidates and whether
overlap was actually observed. A conservative refusal is not an overlap detection:
it can also withhold sequential speech merged into one transcript phrase, and
cannot detect a mixture consistently assigned to only one speaker. No speech-purity
or emotion-accuracy qualification follows from passing this gate.

The worker now retains local binary segmentation overlap before averaging frame
counts or combining speaker labels. `local_segmentation_overlap_v1` unions actual
two-or-more-active-slot frame intervals, clipped to source duration, and retains
each supporting window. It reuses the existing reconstruction observation once;
normal/exclusive diarization and the separate `collapsed_local_return_v1` review
rule remain unchanged. No second model, extra inference or tuned threshold is used.
`emotion_input.speaker_purity.local_overlap` carries status, source-time intervals,
supporting windows and explicit unreviewed/non-identity qualification. A local
positive withholds its containing phrase even when every global label agrees;
direct word samples also cannot intersect it. Failed/unavailable observation
withholds individual inference visibly; confirmed no-speech has its own
`not_applicable` state. Historical records without the observation remain readable.
Inspector and summary input show local candidates separately from speaker names.
The positive-window union can increase false positives; its absence is not proof
of clean single-speaker audio. Frozen-control recall and family accuracy remain
separate qualification requirements.

The isolated Nemotron candidate is an additional exclusion signal, configured
only by `diarization.additional_overlap_model` in that worker's local runtime
configuration. Absence of the key leaves the established path enabled without
loading Nemotron. The candidate accepts an existing local directory with the
evaluated weights, uses native Transformers loading without remote code, and
rejects inputs longer than 300 seconds; this is not a full-movie qualification.
Its native offline implementation carries a speaker cache through internal
chunks. The worker adds no slicing or label-stitching layer. The receipt records
`processing_mode=native_offline_chunked` and `max_input_seconds=300`.
The model runs once on the original audio after diarization and is released
before sound/individual analysis. It emits only two-or-more-voice frame intervals
at the fixed 0.5 activation threshold, not identities or replacement speaker turns.

`emotion_input.speaker_purity.additional_overlap` preserves its own status,
policy, model/revision, weight hash, timebase, interval list and unreviewed
qualification. Both detectors can withhold a whole intersecting phrase before
voice sampling or emotion inference. Word joining cannot bridge either detector's
positive interval in a gap. The existing speech/event gate must still accept any
remaining sample; an empty detector result never admits audio by itself. Enabled
but failed or malformed evidence withholds individual inference visibly. Confirmed
no-speech skips the additional model and records `not_applicable`; original sound
events remain available. Summary inputs and Inspector retain separate candidate
evidence. The user has localized mixed voices approximately in the existing
controls; precise interval edges and general detector accuracy remain unqualified.
Same-clip trial evidence: `tmp/audio-nemotron-exclusion-20261101-001/RESULT.md`.
The 180/300-second synthetic and 180-second natural-source follow-up is recorded
in `tmp/audio-plan-20261101-001/RESULT.md`. Stable channels in repeated clean
controls and a repeatable mixed run do not qualify cross-movie identity or
general overlap accuracy. Source-to-consumer completion also does not establish
long-form transcription quality: missing repeated utterances, suspicious repeated
text, and unresolved word boundaries are retained as failed quality evidence.

The current isolated source repair
(`tmp/audio-source-phrase-20261101-001/RESULT.md`) uses `source_audio_v2`.
VAD measures speech presence and supplies bounded language-detection context;
it no longer cuts recognition inputs. Provided whole-input VAD detects speech,
the partition preserves every nonzero original sample. Only literal zero runs
of at least 200 ms may split inputs, with half-gap context capped at 400 ms.
Short zero runs and quiet nonzero speech are preserved. Continuous audio uses
Whisper's native bounded decoder windows. Recognition inputs are never joined.
The receipt separates VAD observations, recognition regions, delivered sample
counts and model-quality warnings. A VAD-negative input is still skipped; this
guard does not establish objective speech absence or detector recall.
Historical `source_regions_v1` receipts remain readable but do not satisfy the
current worker policy admission check.

Recognition uses `word_timestamps=False`: native decoder envelopes are captured
before DTW can rewrite them or alter the decoder cursor. The same decoded tokens
are aligned afterward on the same original-region features, using the pinned
1.0.3/1.2.1 API shapes and padding rules. No second ASR or vocabulary-free timing
retry occurs. Valid paired native tokens verify the original feature origin;
the older runtime's advanced `Segment.seek` is never used as that origin.
Word alignment failure preserves recognized text and is explicit, including
partial alignment. Late internal-window decoder failure preserves already
yielded text while reporting incomplete coverage.

`transcription_decoding.source_regions` records attempted/completed regions and
explicit empty, rejected, unplaced, failed and unattempted outcomes. Unplaceable
segment text is retained with raw bounds and a warning, without fabricated timing.
Decoder compression/log-probability warnings use the installed model's thresholds.
These receipts establish processing coverage, not recognized-word completeness.
Whole-input absence requires every recognition region to be conclusively rejected
(or completed VAD to find no speech); unknown regions cannot establish absence.
Nonzero subprocess exits retain partial receipts only when both request UUID and
source path match, and remain errors. Completed text, segments and word alignment
survive a later region failure through both the worker receipt and bridge;
transcript metadata says `partial`, while transport failure remains `error`.

Coverage reaches persisted transcript metadata, Inspector and bounded summary
inputs. The November 1 host repair separates timing-only warnings
(`invalid_word_timing`, `word_alignment_unavailable`) from recognition uncertainty.
Those timing warnings preserve recognized words for semantic analysis and append
an explicit timing caution; they do not qualify the words or their source times.
Other warnings, unplaced text, failed/incomplete regions and contradictory absence
remain restricted. Restricted recognition and supported no-speech outcomes use
independent caption/OCR observations rather than generated spoken claims; OCR is
kept as written text. The same distinction survives unavailable, malformed and
truncated summary responses. Raw transcript, cues and acoustic evidence remain
retained. A summary with no supported topic cannot erase present dialogue.
Individual audio, text-sentiment and sound-event estimates do not qualify scene
mood: `emotion_qualification` remains explicit, alongside `transcription_evidence`
and the coverage warning through harmonizer storage and scene/timeline APIs.
`tmp/audio-evidence-retention-20261101-001/RESULT.md` records the bounded proof and
remaining accuracy limits. This does not alter the voice/emotion speech gate.
The shared transcription implementation is
`wsl2_audio/transcription_contract.py`; retained callers do not slice recognition
inputs by diarization turns or arbitrary caller chunks. Missing times remain
null, and empty decoding alone never establishes absent speech. Faster-Whisper
1.0.3 uses its immediate language metadata without consuming the concatenated
context's lazy decoder; newer versions use `detect_language`. Explicit VAD
settings prevent version-default drift, but different model/runtime versions
can still yield different words and boundaries.

The standalone helper, shared module and acoustic-event module are included in
worker sync, bootstrap assets and admission hashes. Preflight adds the selected
workspace to the import path before loading the worker. Local scene offsets
translate words and coverage once into video coordinates; Inspector uses the
explicit origin to seek scene audio and retains full-source coordinates for
standalone audio. Vocabulary hints keep their non-identity disclosure. No live
worker promotion is implied by these source and isolated-candidate changes.

November 1 correction: Whisper's word probability is an average token recognition
likelihood, not a timestamp confidence. The former 0.8 first/last-word timing gate
conflated these signals and is removed from emotion phrase selection. Recognition
uncertainty at every position, including phrase edges, remains disclosed in
`uncertain_transcript_words`, even when another check withholds the phrase.
Original timestamps are retained as unreviewed model estimates; no new temporal
accuracy qualification is implied. The independent word gate for voice signatures
is unchanged. Rejected multi-speaker phrases retain `speaker_candidates` and
model-estimated `overlap_intervals` so recognition uncertainty cannot conceal the
separate overlap blocker. The whole
phrase receives its own acoustic assessment using the same speech/event criteria.
All observed VAD speech inside it must have the same exclusive speaker support;
unobserved leading/trailing silence may remain without trimming the source word.
If VAD finds no speech but AudioSet supports it, the entire interval requires
exclusive speaker support. Missing speech evidence cannot clear a phrase.
Existing event/phrase assessments reuse one loaded model and cached identical
sample windows; no extra model, retries or orchestration layer is introduced.

`segments[].phrase_timing` retains native text, bounds, token-clock provenance,
20 ms timestamp resolution and an explicit boundary disposition. Resolution is
not accuracy. A native complete envelope may support a whole phrase despite
unavailable internal word timing. It cannot lend its bounds to punctuation
subphrases. Native blocks containing question/exclamation endings can be divided
before admission only when the entire recognized text matches the corresponding
word groups. Each resulting unit requires complete, monotonic word bounds inside
the native envelope; conflicting units are withheld. Periods and ellipses remain
inside the larger unit because punctuation alone cannot distinguish an ordinary
sentence ending from an abbreviation. This bounded subdivision is not general
semantic or multilingual sentence-boundary qualification. The original native
envelope remains context evidence, never a smaller unit's timing evidence.
No speaker/acoustic/overlap refusal triggers subdivision or a smaller crop retry.
Decoder-edge contact or missing native delimiters may retain the
existing fully timed, monotonic complete-word path, labeled
`timing_basis=complete_word_alignment`, with native uncertainty preserved.
Native text/clock contradictions, out-of-input bounds, or failed native acoustic,
speaker, overlap or duration checks cannot fall back to a smaller word fragment.
The timing-only missing-word-edge refusal may be superseded only by a validated
native envelope for the same complete text; the voice gate keeps that refusal.
The caller projection preserves these envelopes separately in
`transcript_meta.phrase_observations` before speaker merging replaces display
segments with word turns. Persistence, source offsets and Inspector retain the
whole observations; a smaller attributed turn never inherits their full bounds.
`boundary_status=model_estimated_complete_phrase` never certifies human-verified
sentence or phoneme boundaries. Each
scored phrase has `interpretation_status=uncertain`, explicit reasons and
`model_qualification=unqualified`. The current emotion model has not passed the
reviewed accuracy gate; even a large score is not promoted to qualified certainty.
`emotion_status=success` describes completed inference only. Withheld phrases
produce `no_complete_supported_phrase`, distinct from absent audible speech.
The bridge's capability outcome retains this distinction and separate quality
status. Inspector and summary inputs retain phrase text, bounds, withheld reasons
and uncertainty. Raw model scores/labels remain review evidence; scene mood stays
unset. Historical results without this phrase policy remain readable.

Consumers retain compatibility with saved `clear_speech_only_v1` evidence; neither
version may promote a segment estimate into a whole-scene emotion.

The November 1 utterance-admission diagnostic
(`tmp/audio-utterance-admission-20261101-001/RESULT.md`) separately confirms crop
sensitivity in the sound classifier: a fixed 32 ms earlier start, with the ending
unchanged, moves Speech from 0.537 to 0.491 across the existing 0.5 threshold.
Repeated identical crops match; this observation does not establish runtime
randomness or justify lowering the threshold. The current crop remains withheld
when neither acoustic speech nor VAD coverage satisfies admission. Sound-event
retention, overlap exclusions and voice-sampling rules are unchanged.

Invalid word timing remains explicit, with primary text and raw invalid times
retained. It does not trigger re-recognition. Historical recovered timing remains
explicitly unreviewed. Ambiguous words keep unavailable timing. Speaker merging
uses individual words and preserves unresolved overlapping-speaker attribution.
Unaligned words remain visible using their containing segment as coarse context.
The shared speaker merge applies the same exclusive-coverage rule to coarse
segments and flat word rows: greatest overlap cannot assign mixed speech to one
speaker. Adjacent tracks from the same speaker may jointly cover a word, while
unknown gaps and competing tracks prevent attribution or merging across them.
Unresolved rows retain `speaker_candidates`, `attribution_reason` and clipped
`overlap_intervals`; simultaneous overlap is distinct from sequential speaker
changes. These are model observations, not person identities or acoustic source
separation. Summary input preserves this evidence and Inspector labels overlapping
voices as unresolved while retaining their words. This does not repair overlap
that the upstream diarizer never detects or change individual emotion admission.

The unified worker accepts optional `audio.transcribe.vocabulary`: at most 32
nonempty printable terms, each at most 64 characters, stripped and deduplicated
without case sensitivity. Video, standalone and step-dispatch callers use one
configuration projection. The worker applies these as Faster-Whisper `hotwords`
to primary transcription only; the bounded timing retry remains unprompted.
`transcript_meta.transcription_context` records the applied terms and explicitly
disclaims identity. Hints may improve or bias recognition; they are not transcript
corrections or evidence of who is present. Vocabulary is explicit configuration,
not automatic roster/alias harvesting. It is supported by the unified worker
transport, not the separate Windows-safe local transcriber or legacy transcribe
wrapper. Default calls without vocabulary preserve unprompted recognition.

The opt-in recording replacement uses its pinned profile's optional `vocabulary`
list with the same bounds and normalization. The profile is authoritative: a
nonempty `audio.transcribe.vocabulary` must agree or preparation fails before any
worker runs. The source/configuration checkpoint includes the vocabulary, and
each observation records the actual decoder hotwords. No roster is loaded
automatically; absent/empty vocabulary preserves unhinted decoding. Fixed decoded
words are aligned once without a second recognition pass; admission is unchanged.
`provenance.transcription_context` carries the declared terms into review and
compatibility metadata. Inspector discloses their possible bias. Summary input
receives only the fact that vocabulary was supplied, not unused roster names;
configured spellings cannot become evidence of who is present. Candidate quality
and promotion remain governed by `PROJECT.md` and the unchanged acceptance suite.

Recording phrase placement preserves raw native timestamps even when they fall
outside the input. A complete, ordered, in-bounds alignment may locate the fixed
text independently; it does not certify phrase completeness. The versioned
`complete_phrase_outer_activity_v3` resolver may replace coarse empty
margins with an enclosure of every aligned word and independently observed phrase
and speaker activity. It cannot remove uncertain words, hide events/overlap, cross
neighboring phrases or use unassessed/source-censored bounds. Older envelope
records retain their original validation semantics. Word times remain estimates.
For a fully aligned split phrase, an outer parent edge may grow to contain
independently observed activity. Its internal pause stays fixed, and the child
cannot shrink to discard contamination. Support fractions use activity inside
the phrase; activity crossing an unresolved outer edge still prevents admission.

Window reconciliation still requires a unique occurrence on the same source
channel with the existing temporal agreement. `surface_equivalence_v1` compares
case/punctuation and conservative English spellings: zero through nineteen versus
digits, and numeric ordinal/cardinal date forms immediately after a month name.
English number rules require configured or observed English. Original renderings
and observation IDs are retained; the selected decoder text is never rewritten.
Different names, negation, quantities or ambiguous occurrences remain conflicts.
Neither resolution changes the shared speech gate or certifies recognition.

The isolated candidate also reconciles unique matching observations across
redundant source channels. Complete word alignments may establish the matching
occurrence when native envelopes have different padding; ambiguity checks and
PCM comparison still cover the original envelopes. It compares decoded PCM without mixing, gain fitting,
time shifting or polarity correction: whole-span residual RMS must be at most
0.001 of either channel, and every 20 ms frame at most 0.01. This is recording
redundancy evidence, not speaker identity or speech purity. The lowest channel
owns the retained text; original observations, channel membership, source/PCM
hashes and comparison spans remain in `channel_reconciliation`. Confidence is
conservative across members, invalid scores remain unsupported, and recognition
coverage is recomputed across every member channel on each resulting span.
An independently extended envelope needs a new PCM comparison on its added
samples. Only proven channel coincidence is removed; model overlap, vocal events,
missing support and boundary uncertainty still reach the unchanged speech gate.

`sound_events` and `sound_event_meta` retain candidates and detector provenance.
`emotion_input` records selection/rejection reasons; `emotion_segments` retains
speaker-bound, unreviewed predictions and exact sample bounds. This policy emits
no scene-wide emotion. No eligible speech yields `insufficient_evidence`; detector
failure yields an observable error and never falls back to scoring the whole
clip. No-speech remains distinct from failure. A model gate cannot guarantee
perfect speech isolation; false exclusions and missed events remain possible.

These fields survive standalone/video persistence, scene/timeline API responses,
and the Inspector's separate sound/estimate section. The summary caller now receives
distinct text emotion, sentiment provenance, sound candidates and attributed speech
estimates. Rich audio evidence bypasses the former generic monologue shortcut.
Cached sentiment runs in offline mode; model failure keeps visible fallback
provenance. Inspector displays recovered timing and the attributed context summary.
Full vocal score distributions now reach the summary, and Inspector shows the
three highest scores rather than only the winning label. Scores are uncalibrated
rankings, not probabilities of a person's feelings. Both consumers retain vocabulary
provenance; overlapping voices remain unresolved rather than assigned an identity.
Inspector and timeline sentiment chips label text analysis and expose available
scores, including near-even binary predictions. Historical movie labels are unchanged.
The unprompted repaired clip retained 3.54 seconds of speech; the vocabulary-enabled
follow-up retains 3.14 seconds, recovered Yay timing and crying candidates. The
tiny speech-only crop remains unreliable. Model disagreement, uncertain speakers and human review
remain explicit. `PROJECT.md` owns the qualification limit and Movie 3 launch hold.

## Related Contracts

- Platform contract:
  [`docs/reference/PLATFORM_SUPPORT.md`](PLATFORM_SUPPORT.md)
- Environment map:
  [`docs/reference/indexes/ENVIRONMENT_INDEX.md`](indexes/ENVIRONMENT_INDEX.md)
- GPU / LLM / WSL index:
  [`docs/guides/gpu/GPU_LLM_WSL_INDEX.md`](../guides/gpu/GPU_LLM_WSL_INDEX.md)
- Segmentation shadow contract:
  [`docs/technical/SEGMENTATION_ARTIFACT_CONTRACT.md`](../technical/SEGMENTATION_ARTIFACT_CONTRACT.md)
