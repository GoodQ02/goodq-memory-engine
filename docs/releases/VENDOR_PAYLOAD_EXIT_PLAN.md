<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_PLAN -->
<!-- DOC_LAST_VERIFIED: 2026-05-13 -->

# Vendor Payload Exit Plan

## Purpose

This plan defines how GoodQ4All should migrate vendored binaries and package
trees out of tracked source control without breaking bootstrap, offline
restore, or the current release sanity checks.

This is release-engineering groundwork only. It does not authorize deleting
`vendor/qdrant/qdrant.exe`, deleting `vendor/nssm.exe`, changing bootstrap
paths, changing runtime dependency resolution, rebuilding installers, or moving
payloads into release artifacts.

Large payloads should eventually be published as GitHub Release assets with
manifests and hashes, not as ordinary VCS files.

## Current Vendor Inventory

| Item | Current evidence | Current role | License and notice state | Exit recommendation |
| --- | --- | --- | --- | --- |
| `vendor/qdrant/qdrant.exe` | Tracked executable, about 65 MB | Runtime-required under current Windows Qdrant bootstrap and service scripts | `vendor/qdrant/LICENSE` is present; `THIRD_PARTY_NOTICES.md` references it | Do not remove yet. Move later into a host tools release asset only after bootstrap can resolve that asset path and sanity checks accept it. |
| `vendor/qdrant/config.yaml` and `.qdrant-initialized` | Tracked Qdrant support files | Runtime/bootstrap support for current local vector store layout | Covered by Qdrant component context | Keep until host tools asset install path is implemented and verified. |
| `vendor/nssm.exe` | Tracked executable, about 360 KB | Runtime/bootstrap helper for Windows service install and uninstall scripts | No adjacent license file was found in `vendor/`; upstream source, public-domain license evidence, ZIP checksum, internal binary checksum, and local checksum match are recorded in `THIRD_PARTY_NOTICES.md` | Do not remove yet. Before repackaging, record the host-tools release-asset checksum and restore validation result. |
| `vendor/bin/*.exe` | Tracked Python console launcher executables | Offline/bootstrap convenience for vendored Python packages; not the canonical Conda runtime | License follows underlying Python package metadata when applicable | Replace through a Windows wheelhouse or env pack after offline install validation proves the launchers are unnecessary. |
| Vendored Python package trees under `vendor/` | Tracked source trees for certifi, charset-normalizer, colorama, filelock, fsspec, huggingface-hub, idna, packaging, pyyaml, requests, tqdm, typing-extensions, urllib3 | Offline/bootstrap fallback and helper import surface; canonical runtime remains Conda-first | Most packages preserve `*.dist-info` metadata and license files; `THIRD_PARTY_NOTICES.md` references vendored Python packages generally | Move to wheelhouse/env release assets only after bootstrap no longer depends on repo-local `vendor/` imports. |
| Vendored `*.dist-info` metadata trees | Tracked package metadata and license evidence | License and provenance evidence for vendored Python package trees | License files are present for the observed Python packages | Preserve equivalent metadata in release manifests before removing from source. |

## Runtime Coupling Observed

The current release branch still has direct coupling to repo-local vendor
payloads:

- Qdrant bootstrap and verification scripts check `vendor/qdrant/qdrant.exe`.
- Qdrant service install and uninstall scripts use `vendor/nssm.exe`.
- `configs/paths.py` defines the default tools directory as repo-local
  `vendor/` unless overridden by configuration.
- Some readiness and model-lockdown scripts add `vendor/` to the Python import
  path for helper packages.
- `docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md` still lists Qdrant and NSSM as
  expected source-pack contents under the current contract.

Therefore, deleting vendored payloads before a resolver and release asset
restore path exist would break current bootstrap assumptions.

## Why VCS Should Not Carry Payloads Long Term

Tracked binaries and vendored wheel-style trees make the public repository
larger, harder to review, and harder to patch through normal dependency
tooling. They also blur the boundary between source code, redistributable host
tools, package caches, runtime model caches, and optional corpus material.

The desired long-term model is:

- source code and small templates remain in git;
- host tools, wheelhouses, Conda caches, model caches, and optional corpus packs
  are release assets;
- every release asset has a manifest, checksums, license evidence, and restore
  validation;
- no secrets, local config, generated reports, runtime databases, logs, raw
  media, or private memory snapshots are packaged.

## Staged Migration

### P0 - Freeze and document current exceptions

Status: this document is the P0/P1 groundwork.

- Keep `vendor/qdrant/qdrant.exe` and `vendor/nssm.exe` tracked for now.
- Keep vendored Python trees for now.
- Do not change bootstrap, Qdrant service scripts, or GOOD-SPEED sanity check
  assumptions.
- Record the current vendor inventory and current coupling.
- Keep NSSM provenance evidence current before future repackaging.

### P1 - Define release asset contracts

- Use `docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md` as the asset boundary.
- Define host tools, Windows wheelhouse, Linux/WSL wheelhouse, Conda package
  cache, required model cache, and optional reference/corpus packs as GitHub
  Release assets.
- Require a manifest plus SHA256 checksums before any asset is accepted by
  bootstrap or release validation.
- Keep optional corpus/eval packs separate from runtime-required installer
  assets.

## Next Host-Tools Asset Gate

The source repo should not become the cargo hold. The source repo should carry
source, docs, configs, manifests, and small examples; large binaries and host
tools should move to GitHub Release assets only after a manifest and validation
gate exists.

Very large model, corpus, WSL export, or environment payloads may need
external/object storage with release-manifest pointers instead of direct git
tracking. Personal archives, copyrighted media, private witness outputs, and
PHI/PII-like material remain local/private storage only.

Host-tool payload candidates include Qdrant, FFmpeg, Tesseract, Poppler,
Piper, and NSSM. Do not stage those payloads as part of this plan.

Each future host-tools release asset manifest must record:

- name
- version
- source URL
- license or terms evidence
- local SHA256
- upstream ZIP SHA256 when available
- internal binary SHA256 when available
- restore location
- validation command
- required or optional classification

NSSM remains currently required for the Windows Qdrant service install and
uninstall path. Current official source evidence indicates NSSM is likely
redistributable as public domain. The upstream ZIP checksum and internal
`win64/nssm.exe` checksum have been captured, and the internal binary matches
`vendor/nssm.exe`.

NSSM gate evidence:

1. Official ZIP URL recorded.
2. ZIP SHA256 recorded.
3. Internal `win64/nssm.exe` SHA256 recorded.
4. Internal binary checksum matches `vendor/nssm.exe`.
5. Host-tools release asset checksum recorded.
6. Host-tools restore validation command recorded.
7. Final packaging classification: sealed for the named asset and checksum
   below only.

Host-tools release asset seal:

- Asset name: `goodq4all-0.1.1-host-tools-windows-x86_64.zip`
- Asset class: `host_tools_payload`
- Asset path: `%GOODQ_RELEASE_ASSET_STAGING_ROOT%/goodq4all-0.1.1-host-tools-windows-x86_64.zip`
- Source staged payload path: `%GOODQ_OFFLINE_BUNDLE_ROOT%/tools`
- Source staged payload tree SHA256:
  `6e7845ba6b3aaa4bfeb49c85b0b010d63bd202850919df6b3cec04391e3ffe9c`
- Final asset SHA256:
  `FB764714AF96E3E8DCD64AF0603134AD60FD501B3E2DD70130EFEA897F0FE603`
- Final asset size: `741,956,588` bytes
- Included high-level payload groups: FFmpeg, NSSM, Piper, Poppler, Qdrant,
  and Tesseract
- Builder command:
  `python scripts/releases/host_tools_asset.py build --staging-root "%GOODQ_OFFLINE_BUNDLE_ROOT%/tools" --manifest "%GOODQ_OFFLINE_BUNDLE_ROOT%/manifests/host_tools_pack_manifest.json" --output-dir "%GOODQ_RELEASE_ASSET_STAGING_ROOT%" --force`
- Restore validation command:
  `python scripts/releases/host_tools_asset.py validate --asset "%GOODQ_RELEASE_ASSET_STAGING_ROOT%/goodq4all-0.1.1-host-tools-windows-x86_64.zip" --restore-root "%GOODQ_TEMP_RESTORE_ROOT%/host-tools-restore" --force`
- Restore validation result: passed; `550` archive members restored, required
  host-tool files and notices/manifests were present, and restored
  release docs/manifests scanned clean for local path roots and token-shaped
  text
- Restored NSSM SHA256:
  `EEE9C44C29C2BE011F1F1E43BB8C3FCA888CB81053022EC5A0060035DE16D848`
- Reproducibility posture: the builder uses sorted POSIX-relative member
  paths, fixed ZIP timestamps, and stored entries for stable rebuilds

This seal applies only to the named asset and SHA256 above. Any rebuilt,
renamed, recompressed, or repacked host-tools asset must be treated as unsealed
until the builder and restore validator are rerun and the new checksum is
recorded.

Required runtime model caches remain separate from optional dataset/eval
corpus. Optional corpora, reference packs, witness datasets, and
Seinfeld/test-run memory do not belong in the base installer. Hugging Face or
other access tokens must never be packaged.

### P2 - Add a resolver without changing default behavior

- Add a host tool resolver that can prefer an installed release-asset payload
  while retaining the current repo-local fallback.
- Add a Python dependency resolver path that prefers the Conda environment and
  release wheelhouse over repo-local vendored packages.
- Add clear warnings when a required release asset is absent.
- Preserve current defaults until a clean checkout and offline restore rehearsal
  prove parity.

### P3 - Validate asset restore in clean environments

- Verify online bootstrap from source without vendored Python package trees.
- Verify offline restore from release assets on a clean disposable target.
- Verify Qdrant service install, Qdrant startup, bootstrap verification, and the
  public first-run sanity path.
- Verify that GOOD-SPEED sanity checks either keep the current assumptions or
  are updated in the same bounded release-engineering change.

### P4 - Remove tracked payloads only after parity

- Remove vendored executables and Python package trees only after all P2/P3
  gates pass.
- Update `THIRD_PARTY_NOTICES.md`, source-pack manifests, bootstrap docs, and
  release notes in the same removal change.
- Keep a rollback branch or tag that still contains the current tracked vendor
  payloads until the first asset-based release is proven.

## Online Bootstrap Path

The online path should remain source-first and Conda-first:

1. Clone source.
2. Create the canonical Conda environment from `environment.yml` or
   `environment.gpu.yml`.
3. Resolve host tools through bootstrap-managed downloads or an operator
   supplied tools root.
4. Fetch required model cache assets through the model registry and upstream
   terms.
5. Run bootstrap verification.

Online bootstrap must not require pre-committed wheel trees or local package
caches once the migration is complete.

## Offline Release Asset Path

The offline path should use a release manifest:

1. Download the source archive and selected GitHub Release assets.
2. Verify the release manifest and SHA256 checksum files.
3. Install host tools into the configured host tools root.
4. Restore Windows and WSL package payloads into the expected environment roots.
5. Restore required model cache payloads into the configured model cache root.
6. Run bootstrap verification and targeted first-run checks.

Optional corpus, reference, eval, and memory snapshot packs are never base
installer requirements.

## Dependency Packaging Audit

| Surface | Finding | Recommendation |
| --- | --- | --- |
| `setup.py` | Present, but declares only minimal package metadata plus a small CLI/runtime dependency subset. It is misleading if treated as the full runtime dependency authority. | Treat as metadata and editable-install support only. Keep Conda-first dependency posture. |
| `pyproject.toml` | Not present at audit time. | Add modern project metadata and optional extras later, after dependency authority is reviewed. |
| `environment.yml` | Present and defines the public BASELINE `goodq_core` Conda environment. | Keep canonical for public CPU-safe bootstrap. |
| `environment.gpu.yml` | Present and defines the GPU-enhanced Conda environment with optional CUDA lane. | Keep optional; do not require GPU for public preview. |
| `envs/*/requirements.txt` | Present for specialized step environments. | Keep as step-env inputs until a lock/pack model replaces them. |
| `api/requirements.txt` | Present for API surface dependencies. | Review later for parity with Conda and API docs; do not promote as sole authority. |
| `wsl2_audio/requirements-locked.txt` and constraints | Present for WSL audio lane. | Keep lane-specific; do not run full WSL/GPU ingest in PR CI. |

## CI Recommendation

Do not broaden CI as part of this vendor-exit groundwork. Recommended future CI
shape:

- Linux pure-Python unit matrix for Python 3.10, 3.11, and 3.12.
- Windows BASELINE unit job using the canonical Conda environment.
- Manual integration workflow for Qdrant service, WSL audio, bootstrap restore,
  and first-run checks.
- No GPU, WSL full ingest, model download, or offline bundle build in ordinary
  pull-request CI.

## Documentation Sprawl Recommendation

The active docs tree still contains a stale `docs/ROADMAP.md` planning draft
from October 2025 and several point-in-time status, audit, and snapshot docs at
the docs root. Many historical reports already live under `docs/archive/`.

Recommended future cleanup:

- Mark stale point-in-time docs with `DOC_BADGE` and `DOC_STATUS` metadata.
- Move non-current reports into `docs/archive/` or `docs/diagnostics/history/`
  only through a separate docs-governance pass.
- Keep current release-facing docs narrow and indexed.
- Do not run a broad docs cleanup during the vendor payload migration.

## Rollback Plan

Until payload removal is complete, the rollback is simple: keep using the
current tracked `vendor/` layout and the current bootstrap scripts.

After asset-based bootstrap is implemented, rollback requires:

- a tag or branch that still contains the tracked vendor payloads;
- a manifest record showing which release assets were accepted;
- bootstrap fallback to the repo-local vendor path until a later release removes
  that fallback deliberately.

## Stop Conditions

Stop the vendor exit immediately if any of these are true:

- Qdrant cannot start from a clean checkout.
- Qdrant service install or uninstall cannot find its service helper.
- Bootstrap verification fails because a host tool path moved.
- GOOD-SPEED sanity checks expect repo-local payloads and have not been updated.
- Offline restore lacks a signed-off manifest and checksum set.
- Required model caches, package caches, wheelhouses, or host tools are missing
  from the selected release asset set.
- Any release asset contains secrets, local config, logs, runtime databases,
  private media, generated reports, or memory snapshots.
- NSSM source, license, checksum, and notice evidence are not recorded before it
  is repackaged as an external asset.

## Items Not To Remove Yet

Do not remove these from source control until the staged gates above are closed:

- `vendor/qdrant/qdrant.exe`
- `vendor/qdrant/config.yaml`
- `vendor/qdrant/.qdrant-initialized`
- `vendor/nssm.exe`
- `vendor/bin/*.exe`
- vendored Python package trees under `vendor/`
- vendored `*.dist-info` metadata and license files
