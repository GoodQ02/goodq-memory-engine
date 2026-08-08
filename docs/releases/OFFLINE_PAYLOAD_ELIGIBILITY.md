<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_RELEASE_GATE -->
<!-- DOC_LAST_VERIFIED: 2026-08-08 -->

# Offline Payload Eligibility Ledger

## Purpose

This ledger separates what GoodQ4All may ship in the CPU-safe baseline from
what it must acquire only with user consent, and from what has not yet earned a
redistribution decision. A repository configuration claim is not license
evidence. A payload enters a release only after its exact artifact, revision,
license evidence, and SHA-256 receipt are verified.

## Build Gate

The installer builder now creates `wheelhouse-sbom.json` from the exact staged
wheel closure before NSIS compilation. It rejects an empty wheelhouse,
duplicate distributions, a direct lock mismatch, malformed wheel metadata, or
missing license evidence. The compiled installer carries that receipt beside
the lockfile and wheelhouse it installs.

This gate is verified by focused contract tests. A fresh acquisition on
2026-08-08 produced a 94-wheel, 496 MB closure with SHA-256
`a35ddf4cf54977ff0de13ebae36f9fdecc87bcf0e62bde8443557c1594d1a372`.
The stager's offline dry-run and compliance audit both passed. A managed
offline build must still record the SBOM in a final asset manifest before this
becomes a release artifact.

## 1. Eligible After Artifact Verification

These sources have a pinned revision and an explicit permissive upstream model
license. They are candidates for a future optional model payload; they are not
bundled by the baseline installer today.

| Component | Pinned source | License evidence | Scope |
|---|---|---|---|
| Silero VAD | `snakers4/silero-vad` tag `v4.0` (`7a176cc294a2c40615458e50895ed9703782638d`) | upstream MIT license | baseline VAD candidate |
| CLIP visual embedding | `laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K` (`84c9828e63dc9a9351d1fe637c346d4c1c4db341`) | model card MIT declaration | baseline candidate |
| Emotion classification | `cardiffnlp/twitter-roberta-base-emotion-latest` (`415620c4fbc8bd82b82b9fd46642fcec6519d537`) | model card MIT declaration | baseline candidate |
| Captioning | `Salesforce/blip-image-captioning-base` | model card BSD-3-Clause declaration | optional vision payload candidate |
| Captioning | `nlpconnect/vit-gpt2-image-captioning` | model card Apache-2.0 declaration | optional payload candidate; require loader compatibility proof |
| Visual embedding | `facebook/dinov2-base` and `facebook/dinov2-large` | model cards Apache-2.0 declarations | optional payload candidates |
| Text embedding | `sentence-transformers/all-MiniLM-L6-v2` | model card Apache-2.0 declaration | optional payload candidate |
| Audio embedding | `laion/clap-htsat-unfused` | model card Apache-2.0 declaration | optional payload candidate |
| Transcription | `openai/whisper-large-v3` | model card Apache-2.0 declaration | optional payload candidate |
| Transcription | `Systran/faster-whisper-{tiny,small,medium,large-v3}` | model cards MIT declarations | optional payload candidates |
| Audio enrichment | `superb/hubert-large-superb-er`, `facebook/wav2vec2-base-960h`, and `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` | model cards Apache-2.0 declarations | optional payload candidates |
| Text enrichment | `dslim/bert-base-NER` and `distilbert-base-uncased-finetuned-sst-2-english` | model cards MIT and Apache-2.0 declarations | optional payload candidates |
| Local multimodal service | `Qwen/Qwen2.5-VL-7B-Instruct` | model card Apache-2.0 declaration | optional service payload candidate |
| Local reasoning service | `deepseek-ai/DeepSeek-R1-Distill-Qwen-{7B,14B}` | model cards MIT declarations | optional service payload candidates |

Every Python wheel remains eligible only per-build: its actual file hash and
wheel metadata license evidence must appear in the generated SBOM.

## 2. Excluded From a Redistributable Baseline

| Component | Reason | Disposition |
|---|---|---|
| Pyannote diarization, segmentation, and speaker models | token-gated and license acceptance required | user-provisioned optional feature only |
| Gemma-family runtime | the active configuration's access policy conflicts with the current upstream card metadata; no exact artifact decision has been sealed | user-provisioned optional feature only until reconciled |
| OpenAI CLIP host weights | the repository code license does not establish redistribution terms for the model weights | replaced; do not bundle |
| YOLOv8 weights | AGPL or commercial-license boundary | do not bundle without an explicit licensing decision |
| `Qwen/Qwen2.5-VL-3B-Instruct` | current source metadata has no explicit model license field | do not bundle without an explicit source license |
| FaceNet pretrained weights | package source is permissive, but the inherited pretrained-weight provenance is not yet sealed as redistributable | user-provisioned optional feature only |
| Whisper GGML executable and converted weights | code and source-weight terms do not by themselves prove a redistributable converted artifact | user-provisioned optional feature only |
| NRC Emotion Lexicon | research-use terms are not a baseline redistribution grant | do not bundle |
| VADER lexicon | runtime dependency is small, but its exact artifact and notice have not been sealed into the release contract | acquire on demand until that proof exists |
| Historical release suites and old wheel caches | stale evidence and potential duplication | preserved outside active release inputs |

## 3. Disposition Closure

There are no implicit model-payload approvals left. Every formerly pending
component is now either an artifact-verification candidate or excluded from
the current baseline. “Eligible” is not a shipping decision: the payload
designer must still record the upstream owner, exact revision and files,
license notice, access state, checksum, package size, and clean-install proof.
No model may enter the baseline merely because runtime configuration marks it
`allowed`.

## Re-entry Gate for Full Offline Model Payload Design

1. Resolve every pending component into either Eligible or Excluded.
2. Generate a manifest of exact files, sizes, hashes, licenses, and notices.
3. Build the optional payload independently from the CPU-safe baseline.
4. Verify clean install and one isolated scene with no model download.
