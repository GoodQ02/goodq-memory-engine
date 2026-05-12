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

Use `docs/bootstrap/CORPUS_PACK_MANIFEST.md` to classify optional corpus,
reference-bank, synthetic debug kit, foreign scaffold, and memory-snapshot
surfaces before any optional pack is copied or sealed.

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
- `%GOODQ_REFERENCE_BANK_ROOT%` - optional staged external reference bank root
- `%GOODQ_SYNTHETIC_DEBUG_KIT_ROOT%` - optional staged owned debug fixture root
- `%GOODQ_DATASET_CORPUS_ROOT%` - optional staged dataset corpus root
- `%GOODQ_MEMORY_SNAPSHOT_ROOT%` - optional staged memory snapshot root

Do not write tokens, passwords, local `.env` files, raw config dumps, generated
reports, or machine-specific absolute paths into the bundle.

## Lean Base Rule

The base installer is "lean" by authority, not necessarily tiny by byte count.
It may include required source, environments, host tools, WSL runtime payloads,
and runtime model caches. It must not include optional reference banks, optional
dataset corpora, synthetic debug media, private home media, Seinfeld/test-run
memory, generated witnesses, or unselected memory snapshots.

## Pack Overview

| Pack | Status | Purpose |
| --- | --- | --- |
| `base_source_pack` | Required | Clean source payload, docs, configs, tests, vendor helpers, and bootstrap entrypoints. |
| `windows_env_pack` | Required, partial seal | Offline-restorable Windows Conda/pip environments for core and supported step envs. |
| `wsl_audio_pack` | Required for full desktop parity, partial seal | Offline WSL audio runtime payload on the canonical cu121 lane. |
| `model_cache_pack` | Required | Runtime model cache, YOLO weight, lexicons, and HF snapshot structure. |
| `host_tools_pack` | Required | External tools needed by the Windows host: Qdrant, service helpers, FFmpeg, Tesseract, Poppler, Piper. |
| `optional_reference_bank_pack` | Optional | Licensed external reference substrate for contextual lookup, separate from GoodQ personal memory. |
| `optional_synthetic_debug_kit_pack` | Optional | Owned, deterministic debug/preflight fixture media and expected outputs, separate from user memory. |
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
- Approximate size: staged Windows env payload is 9,796,661,595 bytes.
- Hash strategy: hash packed env archives and package cache files; keep lock
  file hashes beside the payload.
- Validation command:
  - `python scripts/bootstrap_verify.py --json --profile ci`
  - `python -m pytest tests/unit/test_bootstrap_install_wsl.py`
  - targeted import checks from each restored env
- Known gaps:
  - Conda tarballs referenced by the current GoodQ envs are staged and
    hash-computed: 209 tarballs, zero missing Conda tarballs.
  - Windows pip wheelhouse is staged and hash-computed: 152 wheel/archive files,
    155 exact PyPI requirements verified with a Python 3.10 no-index download
    probe, and one source-owned package covered by the source pack.
  - the staged env evidence intentionally uses sanitized `pip list` exports
    instead of `pip freeze`, because freeze output can include non-portable
    build-origin paths.
  - restore rehearsal on a disposable target is still pending.
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
  - `%GOODQ_WSL_DISTRO_EXPORT_ROOT%/goodq-audio-*.tar`
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
  - WSL distro export is 48,162,938,880 bytes.
- Hash strategy: use the wheelhouse manifest and hash any WSL distro export or
  system package bundle separately.
- Validation command:
  - `python scripts/wsl_audio_preflight.py --compact`
  - `python -m pytest tests/unit/test_wsl_audio_preflight.py`
- Known gaps:
  - WSL distro export is created and hash-sealed as a private restore payload;
    import/preflight restore rehearsal is still pending.
  - WSL apt archive cache is staged and hash-computed, but it is not a complete
    apt closure and is now supplemental evidence rather than the preferred
    restore path.
  - direct setup package archives are missing for `python3-pip`,
    `python3-venv`, `sox`, and `git`.
  - setup still has apt and direct pip install assumptions unless run against a
    prepared offline path or replaced by distro import.
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
  - total staged host tools pack: 741,766,692 bytes
  - Qdrant staged payload: 65,290,775 bytes
  - NSSM: 368,640 bytes
  - FFmpeg staged payload: 299,079,168 bytes
  - Tesseract staged payload: 249,434,472 bytes
  - Poppler staged payload: 55,859,662 bytes
  - Piper staged payload: 102,052,310 bytes
- Hash strategy: hash executables, model files, voice metadata, and tool
  directory trees after copying them into the final host tools pack.
- Validation command:
  - `python scripts/system_readiness_check.py --json`
  - `python scripts/bootstrap_verify.py --json`
- Known gaps:
  - host tools are copied into the staged portable pack and hash-sealed.
  - staged payload checks passed for FFmpeg, Tesseract, Poppler, Piper, Qdrant,
    and NSSM.
  - restore rehearsal through the offline installer is still pending.
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
  - optional HF dataset cache and download blobs selected by a dataset-corpus
    manifest
  - evaluation, research, synthetic-test, and future training corpora only
  - no runtime-required model snapshots, weights, lexicons, tool payloads, or
    memory databases
  - no general reference-bank payloads unless a selected manifest explicitly
    classifies them here rather than in `optional_reference_bank_pack`
- Approximate size: about 1.3 TB on the current workstation.
- Hash strategy: manifest by dataset namespace, split, cache file, size, and
  hash. Keep this pack separate from base runtime.
- Validation command:
  - optional corpus inventory and selected-dataset load checks after a corpus
    manifest is chosen
- Known gaps:
  - runtime-required assets are classified into `model_cache_pack`, not this
    pack.
  - optional dataset corpus is not inventoried or hash-sealed yet.
  - base installer must not include the optional dataset corpus by default.
- Exclusion rules:
  - exclude all runtime-required model/cache assets; those belong in
    `model_cache_pack`.
  - exclude home-movie targets, Seinfeld/test-run memory, generated ingestion
    outputs, and private user media unless an operator creates a separate
    private corpus pack.
  - exclude this pack from public artifacts unless the selected corpus manifest
    is explicitly public-safe.

### optional_reference_bank_pack

- Purpose: preserve licensed external knowledge references that can contextualize
  GoodQ outputs without becoming personal memory.
- Required: no.
- Source paths:
  - `%GOODQ_REFERENCE_BANK_ROOT%`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/optional/reference_bank`
- Expected contents:
  - selected Wikipedia/Wikidata dumps, map extracts, astronomy/solar data,
    public preparedness references, dictionaries, and similar references
  - source URL, source date, license, refresh cadence, size, and hash for each
    selected reference asset
  - explicit labels distinguishing "observed in user media" from "external
    reference context"
- Base installer behavior:
  - boot without this pack.
  - never treat reference-bank facts as GoodQ personal memory.
  - never say "I remember" for a fact that only came from this pack.
- Approximate size: pending selected reference-bank manifest.
- Hash strategy: manifest each selected reference asset by namespace, version or
  source date, size, and SHA-256.
- Validation command:
  - selected-reference load checks after a reference-bank manifest is chosen
- Known gaps:
  - no reference-bank manifest has been selected or hash-sealed yet.
  - licensing/redistribution review is required per selected source.
- Exclusion rules:
  - exclude Seinfeld/test-run material, private user media, generated witnesses,
    secrets, tokens, and any reference with unclear redistribution rights.
  - exclude this pack from public artifacts unless the selected manifest is
    explicitly public-safe.

### optional_synthetic_debug_kit_pack

- Purpose: provide owned, deterministic media fixtures for preflight,
  transparency demos, and repeatable pipeline-health checks.
- Required: no.
- Source paths:
  - `%GOODQ_SYNTHETIC_DEBUG_KIT_ROOT%`
- Destination paths:
  - `%GOODQ_OFFLINE_BUNDLE_ROOT%/optional/synthetic_debug_kit`
- Expected contents:
  - short owned video/audio/image/PDF fixtures
  - expected transcript, object, caption, OCR, audio, vector, scene, and Phase 6
    assertions
  - fixture license/ownership note and hash manifest
- Base installer behavior:
  - may validate without this pack when other smoke fixtures are available.
  - must not use copyrighted scaffold media as a replacement for this pack.
  - must not install fixture outputs into GoodQ personal memory unless an
    operator deliberately runs a smoke ingest.
- Approximate size: pending created fixture.
- Hash strategy: hash source fixtures and expected-output contracts.
- Validation command:
  - owned-fixture smoke test after the kit is created and selected
- Known gaps:
  - no owned synthetic debug kit has been produced or selected yet.
- Exclusion rules:
  - exclude Seinfeld/test-run media, private home media, generated witness
    outputs, and any non-owned fixture media.

### optional_memory_snapshot_pack

- Purpose: preserve an existing GoodQ memory state for migration, rollback, or
  a deliberately selected private/witness memory install.
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
- Base installer behavior:
  - boot cleanly with no preloaded GoodQ memory.
  - create new SQLite, KG, and Qdrant memory state through normal runtime.
  - never inherit witness/test-run memory unless an operator explicitly installs
    a separate memory snapshot pack.
- Approximate size: pending selected snapshot.
- Hash strategy: snapshot database files and Qdrant collection files after
  services are stopped or a safe export is produced.
- Validation command:
  - `python scripts/bootstrap_verify.py --json`
  - Qdrant collection health check after restore
- Known gaps:
  - no clean memory snapshot pack has been selected; this is intentional and
    not a base-installer blocker.
- Exclusion rules:
  - do not include Seinfeld/test-run memory in the base installer.
  - do not include personal home-movie memory unless this is an explicitly
    private operator snapshot.
  - do not include live Qdrant/SQLite files unless services are stopped or a
    safe export/snapshot procedure is used.

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

The current scratch manifest includes source evidence plus staged, hash-sealed
core payloads. It is still not a final offline archive. Restore rehearsal and
final packaging remain separate gates.

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
8. Base installer does not include optional datasets, reference banks,
   synthetic debug kits, or memory snapshots.
