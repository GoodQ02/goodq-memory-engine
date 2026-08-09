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

The signed baseline model manifest intentionally declares no downloadable model
packs. It is not a deferred catalog: an optional pack may replace it only with
a complete release artifact manifest.

## Personal Source Vault

The complete non-code runtime inventory is tracked in
`configs/offline_asset_catalog.yaml`. It covers every active model-registry
and installer payload reference, including optional lexicons and system tools.
Its status records source-disposition intent only; no record becomes a pack
input until its exact source snapshot, terms, hashes, and compatibility manifest
are sealed.

The first sealed source snapshot is the `nrc_lexicon_collection` personal
archive, revision `downloaded-20260808`, source-manifest SHA-256
`55a75f624d513d97933b87cfc08807aed11d09a0eeb13e6397f73bfc039b6487`.
It retains the complete acquired NRC collection and its official access-page
terms evidence, while deduplicating one byte-identical source archive. This is
preservation evidence only: its component-level terms still govern use, and it
cannot enter a public pack.

The second-pass cache reconciliation sealed `clap_audio` at revision
`8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`, with source-manifest contract
digest `45e415f43fd637523253e60714b3330fd2344e420566706ab44d0950f84796e0`.
All ten upstream members were present after the pinned model card and
`.gitattributes` were retrieved. This proves a preserved source snapshot, not
pack compatibility or a release decision.

The same second pass completed and verified the full `Qwen2.5-VL-7B-Instruct`
source snapshot at its upstream Apache-2.0 revision
`cc594898137f460bfe9f0759e9844b3ce807cfb5`. Its sealed source-manifest
contract digest is
`8957f7fa1d73158a57785676cf1b99aa4401bfdfe6cf8263b32b75608089dc5b`.

The third-pass reconciliation also sealed the exact upstream MIT source
snapshots for `DeepSeek-R1-Distill-Qwen-7B` and `DeepSeek-R1-Distill-Qwen-14B`.
Their source-manifest contract digests are respectively
`aafaefa746f8d70904314f89bf1503c47ba1f84f83118d71e6eacc0a7cad9762` and
`17274f99d607fd0775cf9bc9eac38b56e7e8c69a9d7cde4b0e640e4d9236fb54`.
They remain source-vault evidence only until independent pack compatibility
and clean-install gates are satisfied.

The same pass sealed Silero VAD at commit
`7a176cc294a2c40615458e50895ed9703782638d`
(`3da369f472e752fea0ba238e9f5777bc8674de751715f7f8fe31d77a03600c25`)
and the VADER 3.3.2 source distribution
(`49b76a8c4dab5c59e2a3406c50e8a0cc134f449b5fef2d1ca917afe32f877ad8`).
The former Faster-Whisper Turbo candidate was removed from the active catalog,
registry, provisioner fallback, and unused GPU profile fields after its upstream
repository was proven invalid. The supported pinned Faster-Whisper model records
remain the only selectable paths; no unverified substitute was introduced.

Authenticated source intake resolved all three pinned Pyannote references.
The diarization and segmentation sources are MIT but retain the upstream
contact gate, so they are sealed personal-only records. WeSpeaker is sealed
with its upstream CC-BY-4.0 attribution condition and remains a candidate for
a separately attributed optional pack. No access token or contact data is
stored in the catalog or vault.

### Third-Pass Closure Receipt

The reproducibility audit now reconciles the catalog, installer manifest,
staged cache, and sealed vault in one machine-readable receipt. At this
checkpoint it confirms 23 sealed model or data snapshots, a complete 94-package
wheelhouse closure, and no missing required installer artifact. The only held
model records are agreement-gated sources (Gemma, the three Pyannote models,
and Qwen2.5-VL-3B); their absence is intentional until an acceptance receipt
exists. `pytest` is not a baseline runtime dependency and is therefore optional
in the installer artifact manifest.

The vault admission preflight rejects any public pack that is not both eligible
and sealed. It rejects personal-only and agreement-gated sources from public
packs, and requires a local acceptance receipt before an agreement-gated source
may enter a personal target.

The pinned Qwen2.5-VL-3B source is now sealed under an explicit personal-use
acceptance receipt and the upstream Qwen Research License page. It remains
`personal_only`: no baseline, public, or sanitized pack may admit it. The vault
copy exists solely as an immutable source input for a later personal installer
whose compatibility contract matches the pinned revision.

The Gemma 4 12B snapshot is likewise sealed at its exact immutable revision.
Its pinned model card and Google's current license page identify Apache-2.0, so
the catalog now classifies it as eligible for a later compatible pack. This
does not mean it is already installed by the baseline: a model pack still
requires its own compatibility manifest, artifact receipt, and clean offline
install proof.

The primary vault goal is personal continuity: retain every source asset whose
upstream terms permit the user's acquisition, together with its exact revision,
terms record, and verified source bytes. A later personal installer may use a
sealed source only when its runtime and hardware contract match. Public packs
remain the stricter downstream subset; an upstream restriction is never erased
by retaining a personal copy.

### Reference-Audit Additions

The catalog is also checked against the runtime fallback registry and literal
production `from_pretrained` calls. That audit added `facebook/dinov2-base` as
an Apache-2.0 candidate pinned to `f9e44c814b77203eaa57a6bdbbd535f21ede1415`.
It also records two non-admissible legacy references: an unversioned Pyannote
alias from an obsolete WSL setup script, and a Cardiff multilabel development
utility whose upstream model card does not publish a license field. Both are
explicitly excluded from all packs until their owning paths and source terms
are reconciled.

The same reconciliation corrected a one-character Pyannote segmentation
revision transcription error in the catalog. The runtime registry already held
the valid immutable commit; the catalog now agrees with it.

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
| OpenAI CLIP host weights | the repository code license does not establish redistribution terms for the model weights | replaced; do not bundle |
| YOLOv8 weights | AGPL or commercial-license boundary | do not bundle without an explicit licensing decision |
| `Qwen/Qwen2.5-VL-3B-Instruct` | Qwen Research License; personal acceptance receipt and immutable source snapshot are recorded | personal source only; never baseline/public |
| FaceNet pretrained weights | package source is permissive, but the inherited pretrained-weight provenance is not yet sealed as redistributable | user-provisioned optional feature only |
| Whisper GGML executable and converted weights | code and source-weight terms do not by themselves prove a redistributable converted artifact | user-provisioned optional feature only |
| NRC Emotion Lexicon and acquired NRC collection | official terms prohibit redistribution | personal source archive only; do not bundle |
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
