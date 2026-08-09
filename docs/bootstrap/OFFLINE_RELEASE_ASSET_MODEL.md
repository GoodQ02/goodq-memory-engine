<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_CONTRACT -->
<!-- DOC_LAST_VERIFIED: 2026-08-09 -->

# Offline Release Asset Model

## Purpose

This model defines how GoodQ4All release payloads should be represented outside
git. It is subordinate to `OFFLINE_BUNDLE_CONTRACT.md`,
`OFFLINE_BUNDLE_REBUILD_PLAN.md`, `CORPUS_PACK_MANIFEST.md`, and the release
ship profile.

The target rule is simple: source stays in VCS; heavy runtime, package, model,
tool, and optional corpus payloads are GitHub Release assets with manifests and
checksums.

This document does not authorize packaging a final installer, deleting current
`vendor/` payloads, moving runtime paths, or changing bootstrap behavior.

## Non-Negotiable Boundaries

- Do not commit generated archives, wheelhouses, Conda packages, model caches,
  runtime databases, logs, raw media, or binary payloads as new source files.
- Do not package authentication tokens, local `.env` files, local config,
  machine-specific paths, shell history, or raw config dumps.
- Do not ship Seinfeld/test-run memory, private home media, witness outputs, or
  memory snapshots as base memory.
- Keep required runtime model cache separate from optional dataset, eval,
  reference, and corpus material.
- Keep optional corpus and eval packs outside the base installer unless a later
  authority document explicitly selects and clears them.
- Every release asset must have source evidence, license evidence, a manifest,
  SHA256 checksums, and restore validation before it becomes installer input.

## Release Asset Naming

Use stable names that include project, release, payload class, platform, and
variant:

| Asset class | Example name | Expected extension |
| --- | --- | --- |
| Release manifest | `goodq4all-0.1.1-release-assets.manifest.json` | `.json` |
| Manifest checksums | `goodq4all-0.1.1-release-assets.sha256` | `.sha256` |
| Host tools payload | `goodq4all-0.1.1-host-tools-windows-x86_64.zip` | `.zip` |
| Windows wheelhouse | `goodq4all-0.1.1-wheelhouse-windows-py310.zip` | `.zip` |
| Linux/WSL wheelhouse | `goodq4all-0.1.1-wheelhouse-wsl-linux-py310-cu121.tar.zst` | `.tar.zst` |
| Conda package cache | `goodq4all-0.1.1-conda-cache-windows-py310.tar.zst` | `.tar.zst` |
| Required model cache | `goodq4all-0.1.1-model-cache-required.tar.zst` | `.tar.zst` |
| Optional reference pack | `goodq4all-0.1.1-reference-pack-v0-<slug>.tar.zst` | `.tar.zst` |
| Optional corpus or eval pack | `goodq4all-0.1.1-corpus-pack-<slug>.tar.zst` | `.tar.zst` |

Do not encode local drive names, machine names, user names, branch scratch
paths, or private dataset names into release asset names.

## Manifest Requirements

The release manifest must record:

- GoodQ source commit and tag.
- Asset name, class, platform, variant, size, and SHA256.
- Source URL or local build input for each payload.
- License or terms URL for third-party payloads.
- Destination root token for restore.
- Whether the base installer requires the asset.
- Whether the asset is optional, deferred, or review-needed.
- Build command or export process used to create the asset.
- Validation command and validation result.
- Exclusion confirmation for secrets, local config, runtime state, reports, and
  private media.

SHA256 files must be generated from the exact uploaded asset bytes. A manifest
without matching checksum evidence is not installer input.

## Payload Classes

| Class | Purpose | Source | Destination | Base installer required |
| --- | --- | --- | --- | --- |
| `host_tools_payload` | Non-Python host executables such as Qdrant, service helpers, FFmpeg, OCR tools, PDF tools, and TTS tools | Accepted host tool staging root plus license evidence | `%GOODQ_HOST_TOOLS_ROOT%` or installer-selected tools root | Yes for full local runtime; profile-specific tools may be optional |
| `windows_wheelhouse` | No-index pip restore payload for Windows Python 3.10 environments | Sealed wheelhouse from canonical dependency inputs | `%GOODQ_WINDOWS_ENV_PACK_ROOT%/pip-wheels` | Yes when offline Windows restore is required |
| `linux_wsl_wheelhouse` | No-index pip restore payload for WSL audio lane | Sealed Linux wheelhouse for the selected WSL Python and CUDA lane | `%GOODQ_WSL_AUDIO_PACK_ROOT%/linux-wheels` | Yes only for full WSL audio parity; not required for CPU-only public preview |
| `conda_package_cache` | Offline Conda package closure for `goodq_core` and supported envs | Sealed Conda package cache from current env specs | `%GOODQ_WINDOWS_ENV_PACK_ROOT%/conda-pkgs` | Yes when offline Conda restore is required |
| `required_model_cache` | Runtime-required local model cache referenced by the model registry | Accepted model cache staging root with upstream source evidence | `%GOODQ_MODEL_CACHE_ROOT%` | Yes for offline-ready ingest; never include auth tokens |
| `optional_reference_pack` | Licensed external reference material for contextual lookup | Reviewed reference-pack source evidence | `%GOODQ_REFERENCE_BANK_ROOT%` | No |
| `optional_corpus_eval_pack` | Large dataset, eval, or research corpus material | Reviewed corpus manifest and license evidence | `%GOODQ_DATASET_CORPUS_ROOT%` | No |
| `optional_synthetic_debug_kit` | Owned deterministic debug fixtures and expected outputs | Source-owned fixture pack | `%GOODQ_SYNTHETIC_DEBUG_KIT_ROOT%` | No |
| `optional_memory_snapshot` | Deliberately selected private or witness memory state | Operator-approved snapshot manifest | `%GOODQ_MEMORY_SNAPSHOT_ROOT%` | No; never base memory |

## Host Tools Payload

Purpose: provide external executables without requiring them to be tracked in
git.

Expected contents may include Qdrant, service helpers, FFmpeg, Tesseract, and
Poppler only after license evidence and hashes are recorded. Piper is a
deprecated external TTS integration and is not acquired or shipped by the
baseline installer.

The browser is not a host-tools payload. The launcher opens the loopback UI
through the user's existing URL handler and prints the exact local URL if that
operation fails. A dedicated browser can be considered only as a separately
versioned UI-host pack with its own update and distribution contract; it must
not silently change a default browser or become an untracked prerequisite.

Current source still tracks Qdrant and NSSM for bootstrap compatibility. Future
host-tools assets must preserve their source URL, license URL, version, SHA256,
destination path, and validation smoke result before those source files are
removed.

Supported builder and validator:

- Build command:
  `python scripts/releases/host_tools_asset.py build --staging-root "%GOODQ_OFFLINE_BUNDLE_ROOT%/tools" --manifest "%GOODQ_OFFLINE_BUNDLE_ROOT%/manifests/host_tools_pack_manifest.json" --output-dir "%GOODQ_RELEASE_ASSET_STAGING_ROOT%" --force`
- Validate command:
  `python scripts/releases/host_tools_asset.py validate --asset "%GOODQ_RELEASE_ASSET_STAGING_ROOT%/goodq4all-0.1.1-host-tools-windows-x86_64.zip" --restore-root "%GOODQ_TEMP_RESTORE_ROOT%/host-tools-restore" --force`
- The current sealed host-tools asset is
  `goodq4all-0.1.1-host-tools-windows-x86_64.zip` with SHA256
  `FB764714AF96E3E8DCD64AF0603134AD60FD501B3E2DD70130EFEA897F0FE603`
  and size `741,956,588` bytes.
- The seal applies only to that exact asset name and checksum. Rebuilt or
  recompressed assets must be validated and recorded again.
- Optional corpus, eval, witness, private media, memory snapshots, and local
  authentication material remain outside the host-tools payload and base
  installer.

## Windows Wheelhouse

Purpose: restore pip-installed packages without network access.

The wheelhouse is derived from the canonical Conda and step-env dependency
inputs, not from an ad hoc copy of `vendor/`. The release manifest must identify
the Python ABI, platform tag, exact package set, and no-index install probe
result.

Externally released wheels that are not available from the standard package
index, such as `goodq-mini-agent`, are acquired once while online from their
manifest-pinned source URL, verified against the manifest SHA256, and placed in
the wheelhouse. The requirements lock then uses its normal version pin, so the
offline resolver uses only the verified local wheel. Do not leave a direct URL
requirement in the baseline lock: pip would attempt to fetch it during an
offline build.

## Linux / WSL Wheelhouse

Purpose: restore the WSL audio lane without substituting a drift lane.

The manifest must identify Python version, platform tags, selected Torch family,
CUDA lane when applicable, and offline install probe result. A functional local
WSL lane is not enough; the wheelhouse must match the selected bootstrap lane.

## Conda Package Cache Payload

Purpose: restore Conda packages without solving or downloading.

The cache must be produced from accepted environment specs or locks. It must not
include unrelated package caches, global environment directories, or live user
state.

## Required Model Cache Payload

Purpose: provide runtime-required models for offline-ready ingest.

The payload must be built from the model registry and validated against cache
readiness checks. Gated or auth-required models may be packaged only after the
operator has accepted upstream terms during cache creation. Authentication
material must never be included.

## Optional Corpus and Reference Packs

Purpose: provide optional external knowledge, eval, research, or reference
material without mixing it into the base runtime.

These packs are governed by `CORPUS_PACK_MANIFEST.md`,
`CORPUS_PACK_INVENTORY_LEDGER.md`, and the Reference Pack v0 source-evidence
appendix. A candidate being useful is not enough. Redistribution, attribution,
modification, commercial-use, cloud-bank, offline-bundle, and installer
eligibility must be explicit before payload movement.

## Installer Interpretation

The base installer may require source, bootstrap scripts, required host tools,
required environment payloads, and required runtime model cache. It must not
silently include optional corpus, eval, reference, synthetic debug, private
media, or memory snapshot packs.

Installer inclusion is a separate decision from NAS storage, cloud-bank storage,
offline bundle staging, and local operator cache placement.

## Stop Conditions

Stop packaging or asset publication if:

- any asset lacks a manifest entry or SHA256 checksum;
- any source or license evidence is missing for a third-party payload;
- any asset contains secrets, local config, raw logs, reports, runtime
  databases, private media, or memory snapshots;
- optional corpus/eval material is mixed into the base installer;
- Seinfeld/test-run memory is included as base memory;
- a bootstrap path depends on a payload that is no longer available;
- release validation has not run from a clean checkout or clean restore target.
