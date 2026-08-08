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

Every Python wheel remains eligible only per-build: its actual file hash and
wheel metadata license evidence must appear in the generated SBOM.

## 2. Excluded From a Redistributable Baseline

| Component | Reason | Disposition |
|---|---|---|
| Pyannote diarization, segmentation, and speaker models | token-gated and license acceptance required | user-provisioned optional feature only |
| Gemma-family gated runtime | token-gated and restricted terms | user-provisioned optional feature only |
| OpenAI CLIP host weights | the repository code license does not establish redistribution terms for the model weights | replaced; do not bundle |
| YOLOv8 weights | AGPL or commercial-license boundary | do not bundle without an explicit licensing decision |
| Historical release suites and old wheel caches | stale evidence and potential duplication | preserved outside active release inputs |

## 3. Pending Individual Disposition

The following are intentionally **not** implicitly approved for a full offline
model payload. They need a source-and-artifact review before being added to a
future optional package: BLIP, ViT-GPT2, DINOv2, MiniLM, CLAP, Whisper and
faster-whisper variants, HuBERT, Wav2Vec2, BERT NER, DistilBERT sentiment,
Qwen, DeepSeek, FaceNet, Whisper GGML, NRC, and VADER.

For each, the required decision record is: upstream owner, exact revision and
files, model-weight license and notices, access/gating status, checksum,
redistribution conclusion, package size, and baseline-versus-optional scope.
No model from this list may be folded into the baseline merely because its
runtime configuration currently marks it `allowed`.

## Re-entry Gate for Full Offline Model Payload Design

1. Resolve every pending component into either Eligible or Excluded.
2. Generate a manifest of exact files, sizes, hashes, licenses, and notices.
3. Build the optional payload independently from the CPU-safe baseline.
4. Verify clean install and one isolated scene with no model download.
