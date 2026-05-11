<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_CONTRACT -->
<!-- DOC_LAST_VERIFIED: 2026-05-11 -->

# Offline Bundle Contract

## Status

Status: ACTIVE CONTRACT, SOURCE-EVIDENCE PARTIAL SEAL WITH ENV GAPS

This contract defines the packs required to turn a vanilla Windows machine into
a GoodQ-capable local pipeline runner without internet access. It does not
authorize copying large payloads, installing packages, mutating runtime config,
fetching from the internet, or changing ingestion behavior.

The base installer must be a wrapper over validated payloads. It must not be
the first artifact that discovers what belongs in the bundle.

## Path Tokens

Bundle manifests must use portable tokens instead of local drive roots:

- `%GOODQ_REPO_ROOT%` - clean GoodQ source checkout or source archive root
- `%GOODQ_OFFLINE_BUNDLE_ROOT%` - generated offline bundle root
- `%GOODQ_DATA_ROOT%` - target data root chosen during install
- `%GOODQ_MODEL_CACHE_ROOT%` - staged runtime model cache root
- `%GOODQ_HOST_TOOLS_ROOT%` - staged host tool payload root
- `%GOODQ_WINDOWS_ENV_PACK_ROOT%` - staged Windows Conda/pip env payload root
- `%GOODQ_WSL_AUDIO_PACK_ROOT%` - staged WSL audio payload root
- `%GOODQ_DATASET_CORPUS_ROOT%` - optional staged dataset corpus root
- `%GOODQ_MEMORY_SNAPSHOT_ROOT%` - optional staged memory snapshot root

Do not write tokens, passwords, local `.env` files, raw config dumps, generated
reports, or machine-specific absolute paths into the bundle.

## Pack Overview

| Pack | Status | Purpose |
| --- | --- | --- |
| `base_source_pack` | Required | Clean source payload, docs, configs, tests, vendor helpers, and bootstrap entrypoints. |
| `windows_env_pack` | Required, partial seal | Offline-restorable Windows Conda/pip environments for core and supported step envs. |
| `wsl_audio_pack` | Required for full desktop parity, partial seal | Offline WSL audio runtime payload on the canonical cu121 lane. |
| `model_cache_pack` | Required | Runtime model cache, YOLO weight, lexicons, and HF snapshot structure. |
| `host_tools_pack` | Required | External tools needed by the Windows host: Qdrant, service helpers, FFmpeg, Tesseract, Poppler, Piper. |
| `optional_dataset_corpus_pack` | Optional | Large HF dataset/eval/training corpus, separate from base runtime. |
| `optional_memory_snapshot_pack` | Optional | Existing SQLite/Qdrant/epoch memory state, separate from clean bootstrap. |

## Pack Contracts

### base_source_pack

- Purpose: provide the current GoodQ source tree and bootstrap doctrine.
- Required: yes.
- Source paths:
  - `%GOODQ_REPO_ROOT%`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/source/goodq4all`
- Expected contents:
  - tracked source files from the selected git commit
  - `environment.yml`
  - `environment.gpu.yml`
  - `envs/locks/`
  - `configs/*.yaml` public templates and defaults
  - `.env` templates only
  - `vendor/qdrant/qdrant.exe`
  - `vendor/nssm.exe`
  - bootstrap, validation, and WSL scripts
- Approximate size: pending source archive generation.
- Hash strategy: hash every included file and record the source commit.
- Validation command:
  - `git status --short --branch`
  - `git archive --format=tar HEAD` dry-run or equivalent source export check
  - `python scripts/bootstrap_verify.py --json --profile ci`
- Known gaps:
  - current source payload has not yet been staged with a bundle manifest.
- Exclusion rules:
  - exclude `.git/`, `.env.local`, `.env.agents`, `.env.model_cache`,
    `configs/config.local.yaml`, reports, runtime logs, caches, generated
    witnesses, private scratch files, and token-like files.

### windows_env_pack

- Purpose: restore the Windows `goodq_core` env and supported specialized
  step environments without solving or downloading.
- Required: yes.
- Source paths:
  - `%GOODQ_REPO_ROOT%/environment.yml`
  - `%GOODQ_REPO_ROOT%/environment.gpu.yml`
  - `%GOODQ_REPO_ROOT%/envs/locks`
  - `%GOODQ_WINDOWS_ENV_PACK_ROOT%/conda-pkgs`
  - `%GOODQ_WINDOWS_ENV_PACK_ROOT%/env-exports`
  - `%GOODQ_WINDOWS_ENV_PACK_ROOT%/pip-wheels`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/env/windows`
- Expected contents:
  - packed `goodq_core` environment or equivalent offline Conda package cache
  - packed supported step envs or equivalent offline Conda/pip closure
  - package manifests and hashes
- Approximate size: staged Conda/package evidence is 4,159,075,625 bytes.
- Hash strategy: hash packed env archives and package cache files; keep lock
  file hashes beside the payload.
- Validation command:
  - `python scripts/bootstrap_verify.py --json --profile ci`
  - `python -m pytest tests/unit/test_bootstrap_install_wsl.py`
  - targeted import checks from each restored env
- Known gaps:
  - Conda tarballs referenced by the current GoodQ envs are staged and
    hash-computed: 209 tarballs, zero missing Conda tarballs.
  - Windows pip wheelhouse is not sealed: 123 unique pip package wheels are not
    available in the local wheel cache.
  - the staged env evidence intentionally uses sanitized `pip list` exports
    instead of `pip freeze`, because freeze output can include non-portable
    build-origin paths.
  - old installer helpers with network package lanes must not be treated as
    authoritative env closure.
- Exclusion rules:
  - exclude live Conda directories unless packed intentionally.
  - exclude package caches not referenced by the selected manifest.

### wsl_audio_pack

- Purpose: restore WSL audio transcription, diarization, and Wav2Vec enrichment
  on the canonical WSL audio lane.
- Required: yes for full desktop parity; optional for CPU-only baseline.
- Source paths:
  - `%GOODQ_REPO_ROOT%/wsl2_audio`
  - `%GOODQ_REPO_ROOT%/scripts/wsl`
  - `%GOODQ_REPO_ROOT%/scripts/wsl_audio_preflight.py`
  - `%GOODQ_WSL_AUDIO_PACK_ROOT%/linux_wheels_cp310_cu121`
  - `%GOODQ_WSL_AUDIO_PACK_ROOT%/linux_wheels_cp310_cu121_manifest.json`
  - `%GOODQ_WSL_DISTRO_EXPORT_ROOT%/goodq-audio-*.tar` once created
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/env/wsl_audio`
- Expected contents:
  - WSL runtime scripts
  - canonical Linux wheelhouse for Python 3.10 and cu121
  - `torch==2.5.1+cu121`
  - `torchvision==0.20.1+cu121`
  - `torchaudio==2.5.1+cu121`
  - `transformers==4.43.3`, `tokenizers==0.19.1`, `safetensors==0.7.0`
  - offline install probe report
  - preferred near-term restore strategy: a validated WSL distro export
  - staged apt archive evidence only as supplemental package-level evidence
- Approximate size:
  - sealed wheelhouse evidence is 3,153,798,893 bytes.
  - staged apt archive evidence is 185,684,393 bytes.
  - WSL distro export size is not known yet because no export is sealed.
- Hash strategy: use the wheelhouse manifest and hash any WSL distro export or
  system package bundle separately.
- Validation command:
  - `python scripts/wsl_audio_preflight.py --compact`
  - `python -m pytest tests/unit/test_wsl_audio_preflight.py`
- Known gaps:
  - no exported WSL distro tar is created or hash-sealed yet.
  - WSL apt archive cache is staged and hash-computed, but it is not a complete
    apt closure yet.
  - direct setup package archives are missing for `python3-pip`,
    `python3-venv`, `sox`, and `git`.
  - setup still has apt and direct pip install assumptions unless run against a
    prepared offline path.
  - exact script parity may require `psutil` and `watchdog` wheels, or a script
    correction proving those utilities are unnecessary.
- Exclusion rules:
  - exclude observed cu128 drift wheels.
  - exclude WSL user secrets and shell history.
  - do not store a sudo password.

### model_cache_pack

- Purpose: provide all required runtime model assets without internet.
- Required: yes.
- Source paths:
  - `%GOODQ_MODEL_CACHE_ROOT%/hub`
  - `%GOODQ_MODEL_CACHE_ROOT%/whisper`
  - `%GOODQ_MODEL_CACHE_ROOT%/yolo`
  - `%GOODQ_MODEL_CACHE_ROOT%/lexicons`
  - `%GOODQ_MODEL_CACHE_ROOT%/transformers`
  - `%GOODQ_MODEL_CACHE_ROOT%/modules`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/models`
  - installed target `%GOODQ_DATA_ROOT%/models`
- Expected contents:
  - Hugging Face snapshots, blobs, and refs exactly as cached
  - BLIP, CLIP, DINOv2, MiniLM, CLAP, PyAnnote, Faster-Whisper, Wav2Vec,
    HuBERT emotion, BERT NER, YOLO, Whisper, and lexicon assets referenced by
    `configs/model_registry.yaml`
- Approximate size: runtime HF hub cache is tens of GB; optional dataset cache
  is not part of this pack.
- Hash strategy: hash every file and preserve HF repository directory layout.
- Validation command:
  - `python scripts/cache_readiness_check.py --json`
  - `python scripts/bootstrap_models.py --check-only --json` when available
- Known gaps:
  - required model cache is present locally but not copied or hash-staged into
    the bundle.
  - gated HF models require prior license acceptance and online auth only at
    cache creation time; packaged local snapshots must not include tokens.
  - 2026-05-11 cache drift audit found that the legacy root-level model cache
    has no unique material model payloads beyond the canonical model cache;
    unmatched files were non-runtime cache logs only.
- Exclusion rules:
  - exclude token files and raw config dumps.
  - exclude optional HF datasets from this pack.
  - exclude duplicate or legacy model roots unless referenced by the registry.
  - exclude standalone legacy root-level model cache copies from the base
    bundle unless a future manifest explicitly proves they are required.

### host_tools_pack

- Purpose: package non-Python host executables used by GoodQ.
- Required: yes.
- Source paths:
  - `%GOODQ_REPO_ROOT%/vendor/qdrant/qdrant.exe`
  - `%GOODQ_REPO_ROOT%/vendor/nssm.exe`
  - `%GOODQ_HOST_TOOLS_ROOT%/ffmpeg`
  - `%GOODQ_HOST_TOOLS_ROOT%/tesseract`
  - `%GOODQ_HOST_TOOLS_ROOT%/poppler`
  - `%GOODQ_HOST_TOOLS_ROOT%/piper`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/tools`
  - installed target `%GOODQ_DATA_ROOT%/_TOOLS`
- Expected contents:
  - Qdrant executable
  - NSSM service helper
  - FFmpeg binary distribution
  - Tesseract executable and language data
  - Poppler utilities
  - Piper executable and `en_US-joe-medium` voice plus voice sidecar JSON
- Approximate size:
  - Qdrant: 65,280,000 bytes
  - NSSM: 368,640 bytes
  - FFmpeg source evidence: 299,079,168 bytes
  - Tesseract source evidence: 249,434,472 bytes
  - Poppler source evidence: 55,859,662 bytes
  - Piper source evidence: 102,052,310 bytes
- Hash strategy: hash executables, model files, voice metadata, and tool
  directory trees after copying them into the final host tools pack. Source
  evidence hashes are useful for planning, but they do not by themselves seal a
  portable installer payload.
- Validation command:
  - `python scripts/system_readiness_check.py --json`
  - `python scripts/bootstrap_verify.py --json`
- Known gaps:
  - host tools are installed locally and source-evidence hashes exist, but they
    are not staged as a portable pack.
  - Qdrant and NSSM payloads are present in the source tree, but the final
    host tools pack still needs a copy-and-hash manifest.
  - FFmpeg, Tesseract, and Poppler are source-discovered only until copied into
    `%GOODQ_OFFLINE_BUNDLE_ROOT%/tools`.
  - Piper is located through configured environment variables, but is not yet
    staged or hash-sealed; do not call Piper sealed yet.
- Exclusion rules:
  - exclude installer download caches unless explicitly chosen.
  - exclude mutable service logs and local service state.

### optional_dataset_corpus_pack

- Purpose: preserve large optional HF datasets for offline eval, research,
  testing, and future training lanes.
- Required: no.
- Source paths:
  - `%GOODQ_DATASET_CORPUS_ROOT%`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/optional/datasets`
- Expected contents:
  - optional HF dataset cache and download blobs selected by manifest
- Approximate size: about 1.3 TB on the current workstation.
- Hash strategy: manifest by dataset namespace, split, cache file, size, and
  hash. Keep this pack separate from base runtime.
- Validation command:
  - `python scripts/system_readiness_check.py --json`
- Known gaps:
  - dataset cache has not been classified into runtime-required vs eval-only
    subsets.
- Exclusion rules:
  - exclude home-movie targets, Seinfeld/test-run memory, generated ingestion
    outputs, and private user media unless an operator creates a separate
    private corpus pack.

### optional_memory_snapshot_pack

- Purpose: preserve an existing GoodQ memory state for migration or rollback.
- Required: no.
- Source paths:
  - `%GOODQ_DATA_ROOT%/GoodQ_Data`
  - `%GOODQ_DATA_ROOT%/qdrant_storage`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/optional/memory_snapshot`
- Expected contents:
  - SQLite memory databases
  - Qdrant storage snapshot
  - epoch metadata
  - snapshot manifest
- Approximate size: pending selected snapshot.
- Hash strategy: snapshot database files and Qdrant collection files after
  services are stopped or a safe export is produced.
- Validation command:
  - `python scripts/bootstrap_verify.py --json`
  - Qdrant collection health check after restore
- Known gaps:
  - no clean memory snapshot pack has been selected.
- Exclusion rules:
  - do not include Seinfeld/test-run memory in the base installer.
  - do not include personal home-movie memory unless this is an explicitly
    private operator snapshot.

## Legacy Helper Quarantine Rules

The offline bootstrap must not route through helpers that are marked
`Unclear/Obsolete`, archived, retired, or network-installing in
`docs/bootstrap/SCRIPT_REGISTRY.md`.

Known surfaces needing exclusion or explicit review before packaging:

- `scripts/INSTALL_AUDIO_DIARIZE_ENV.bat`
- `scripts/SETUP_WEB_DEPENDENCIES.bat`
- `scripts/install_audio_deps_retry.bat`
- `scripts/install_pipeline_windows.ps1`
- `scripts/install_pipeline_wsl.py`
- `scripts/install_vad.bat`
- `scripts/install_vision_gpu.py`
- `scripts/setup_wsl2_audio.py`
- `scripts/setup_wsl2_audio_fast.py`
- `scripts/setup_wsl2_audio_userspace.py`
- `scripts/setup/INSTALL_WEB_DEPS.ps1`
- `scripts/setup/setup_agents.ps1`
- `scripts/setup/start_agents.ps1`
- `scripts/init_qdrant_collections.py`
- `scripts/qdrant/CHECK_QDRANT.bat`
- `scripts/qdrant/INIT_QDRANT.bat`

These files may remain useful as historical intel. They are not offline bundle
authority unless a separate audit promotes them.

## Dry-Run / Source-Evidence Manifest Contract

The dry-run or source-evidence manifest must include one object per planned
artifact:

- `pack_id`
- `artifact_id`
- `source_path`
- `destination_path`
- `required`
- `size_bytes`
- `sha256_status`
- `sha256` when the referenced source exists and is hash-computed
- `verification_method`
- `notes`

For existing sources, `sha256_status` must be `computed` and `size_bytes` must
be populated. Directory or aggregate artifacts may use a deterministic tree hash
over sorted relative path, file size, and file SHA-256 records.

For sources that are not yet staged, `sha256_status` must explicitly say why,
for example `not_available_not_staged`. Optional packs that are intentionally
excluded from the base installer must use an explicit deferred status rather
than a silent `pending`.

The current scratch manifest is a source-evidence partial seal, not a final
offline archive. It proves the current referenced sources where they exist and
keeps the remaining closure gaps visible.

## Closure Gates

Before building any final archive or installer:

1. Current source payload is staged from a clean git commit.
2. Required model cache pack is copied and hash-sealed.
3. Windows env closure is either packed or fully backed by offline Conda/pip
   package caches.
4. WSL audio has a validated, hash-sealed WSL distro export, or an explicitly
   validated complete offline system package strategy.
5. Host tools pack includes copied and hash-sealed FFmpeg, Tesseract, Poppler,
   Piper, Qdrant, and NSSM payloads.
6. Token/path hygiene scan passes.
7. Legacy helper quarantine list is enforced.
8. Base installer does not include optional datasets or memory snapshots.
