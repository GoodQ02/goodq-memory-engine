# Third-Party Notices

This repository includes, references, or can bootstrap third-party software,
models, and datasets. GoodQ4All is local-first, but some optional capabilities
depend on upstream projects with their own licenses, access terms, or download
requirements.

This notice is a public-facing summary, not legal advice.

## Repository-Distributed Components

### Vendored Qdrant Binary

- Path: [`vendor/qdrant/qdrant.exe`](vendor/qdrant/qdrant.exe)
- Purpose: local vector database runtime for the canonical Windows host
- Note: this repository ships the Qdrant executable as a convenience for local
  operation. The Apache 2.0 license text is bundled at
  [`vendor/qdrant/LICENSE`](vendor/qdrant/LICENSE). Public consumers should
  still review Qdrant's upstream project licensing and notices when
  redistributing or repackaging builds.

### Vendored NSSM Service Helper

- Path: [`vendor/nssm.exe`](vendor/nssm.exe)
- Purpose: Windows service wrapper used by the Qdrant service install and
  uninstall scripts
- Local artifact: NSSM 64-bit `2.24-101-g897c7ad`; SHA256
  `EEE9C44C29C2BE011F1F1E43BB8C3FCA888CB81053022EC5A0060035DE16D848`
- Upstream source: [`https://nssm.cc/`](https://nssm.cc/),
  [`https://nssm.cc/download`](https://nssm.cc/download), and
  [`https://git.nssm.cc/nssm/nssm`](https://git.nssm.cc/nssm/nssm)
- Upstream artifact check: `https://nssm.cc/ci/nssm-2.24-101-g897c7ad.zip`
  has SHA256
  `99F5045FFFBFFB745D67FE3A065A953C4A3D9C253B868892D9B685B0EE7D07B8`;
  its internal `win64/nssm.exe` has SHA256
  `EEE9C44C29C2BE011F1F1E43BB8C3FCA888CB81053022EC5A0060035DE16D848`,
  matching the tracked local artifact.
- License note: the upstream NSSM download page and source README identify
  NSSM as public domain. Future host-tools release assets should still record
  the restore validation result before repackaging.

### Vendored Python Packages

- Path: [`vendor/`](vendor/)
- Purpose: selected Python packages and license metadata used by the local-first
  runtime and bootstrap surfaces
- Note: vendored Python packages retain their upstream licenses. Where available,
  license metadata is preserved in the corresponding `*.dist-info/licenses/` or
  `LICENSE` files under [`vendor/`](vendor/).

## Model and Asset Downloads

Canonical model and asset references live in
[`configs/model_registry.yaml`](configs/model_registry.yaml).

GoodQ4All does **not** redistribute ML model weights through the public branch.
Weights and optional assets are downloaded from upstream providers into the local
model cache at install/bootstrap time.

Representative upstream model families referenced by the registry include:

- Salesforce BLIP image captioning
- OpenAI CLIP and Whisper
- Meta/Facebook DINOv2
- sentence-transformers MiniLM embeddings
- LAION CLAP audio embeddings
- pyannote diarization and segmentation
- Systran faster-whisper variants
- SUPERB / HuBERT emotion models
- Wav2Vec2 emotion recognition
- dslim BERT NER

## Gated or Auth-Required Models

Some optional or required audio models require separate upstream acceptance or
authentication before download.

Current examples in [`configs/model_registry.yaml`](configs/model_registry.yaml):

- `pyannote/speaker-diarization`
- `pyannote/segmentation`

These require the operator to supply their own token (for example
`PYANNOTE_TOKEN`) and accept upstream access terms directly with the provider.

## Research-Only or Restricted Assets

Some optional assets are not suitable for unrestricted commercial redistribution
or use.

Current example:

- NRC Emotion Lexicon (`Research Use Only`) as declared in
  [`configs/model_registry.yaml`](configs/model_registry.yaml)

If you enable these assets, review the upstream terms before use in commercial
or redistributed products.

## System Tools

GoodQ4All expects local system tools such as:

- FFmpeg
- Tesseract OCR
- Poppler PDF utilities

These are referenced via canonical config and bootstrap flows, but are not
repackaged by the public branch unless explicitly present in the tree. Operators
remain responsible for complying with each upstream tool's license.

## Publication Boundary

The sanitized public branch is intended to ship:

- source code
- documentation
- templates/examples
- bootstrap/install orchestration

It is **not** intended to ship:

- private runtime snapshots
- copyrighted transcript/dialogue artifacts
- locally cached model weights
- machine-local secrets or tokens

## Related References

- [`README.md`](README.md)
- [`configs/model_registry.yaml`](configs/model_registry.yaml)
- [`docs/bootstrap/OPEN_SOURCE_READINESS_STATUS.md`](docs/bootstrap/OPEN_SOURCE_READINESS_STATUS.md)
- [`docs/releases/SHIP_PROFILE.md`](docs/releases/SHIP_PROFILE.md)
