# Public Baseline Installer v2.5.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, independently validate, and attach a fresh Windows baseline installer to the existing public `v2.5.8` release without shipping private source, signing material, user data, WSL audio, or local LLM runtime payloads.

**Architecture:** Private `dev` remains the only implementation authority. The private release workspace supplies the NSIS compiler, Go compiler, staged third-party inputs, and manifest-signing key; the public candidate contains only portable source and receives only the finished installer, launcher, checksum, and non-sensitive release manifest. A disposable clean-install target proves the baseline application before any GitHub asset upload.

**Tech Stack:** Python 3.10 embedded runtime, NSIS 3.09, Go launcher, PowerShell validation scripts, Qdrant, GitHub Releases.

## Global Constraints

- Version authority is `goodq_version.py`: `2.5.8`.
- Keep `BASELINE` CPU-safe; WSL audio and local LLM serving are deferred optional lanes.
- Never package `.env.local`, local config, signing keys, compiler directories, staged caches, raw media, corpus data, logs, runtime databases, or witness artifacts.
- Every uploaded asset needs a SHA-256 checksum and a non-sensitive manifest that resolves to public commit `12f577e9`.
- Functional fixes land in private `dev` first, then flow through the sanitized public candidate.
- A fresh installer must be validated in a disposable install/data root; do not reuse or alter the active GOOD-CUBE runtime.

---

## File Structure

- Modify: `scripts/install/sync_nsi_version.py` — add a non-mutating verification mode for installer metadata.
- Modify: `scripts/install/build_installer.bat` — make the builder fail clearly when private build prerequisites are absent and write release outputs only to the build output root.
- Modify: `tests/unit/test_installer_paths.py` — prove canonical version propagation and baseline-only payload boundaries.
- Create: `tests/unit/test_installer_release_contract.py` — prevent prerelease labels, private inputs, and untracked artifact names from becoming public-release outputs.
- Create: `scripts/install/verify_release_asset.ps1` — verify installer, launcher, manifest, checksum, and source-tag linkage before upload.
- Modify: `docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md` — record the v2.5.8 baseline installer asset contract and explicit exclusions.
- Modify: `README.md` and `CHANGELOG.md` — describe the downloadable baseline installer only after the asset is attached.

### Task 1: Freeze the public baseline artifact contract

**Files:**
- Create: `tests/unit/test_installer_release_contract.py`
- Modify: `tests/unit/test_installer_paths.py`
- Modify: `scripts/install/sync_nsi_version.py`

**Interfaces:**
- Consumes: `GOODQ_VERSION` from `goodq_version.py`.
- Produces: `python scripts/install/sync_nsi_version.py --check` returning zero only when NSIS and launcher version metadata match the canonical version.

- [ ] **Step 1: Write failing contract tests**

```python
def test_release_metadata_uses_canonical_stable_version(repo_root: Path) -> None:
    assert '2.5.8-rc' not in (repo_root / 'scripts/install/goodq4all_installer.nsi').read_text()
    assert 'GoodQ4All_Setup_2.5.8.exe' in (repo_root / 'scripts/install/goodq4all_installer.nsi').read_text()

def test_public_installer_source_excludes_private_build_inputs(repo_root: Path) -> None:
    tracked = subprocess.check_output(['git', 'ls-files', 'scripts/install'], text=True)
    assert 'dev_private_key.hex' not in tracked
    assert 'staged_cache/' not in tracked
```

- [ ] **Step 2: Run the tests to prove current drift**

Run: `conda run -n goodq_core python -m pytest -q tests/unit/test_installer_paths.py tests/unit/test_installer_release_contract.py`

Expected: the stable-version assertion fails because the checked-in NSIS template still names an RC output.

- [ ] **Step 3: Add `--check` to version synchronization**

Implement `--check` so it calculates the expected NSIS and JSON values from `GOODQ_VERSION`, reports every mismatch, and exits nonzero without writing files. Keep the existing write mode for the private builder only.

- [ ] **Step 4: Synchronize only canonical installer metadata**

Run the existing synchronization command on private `dev`, review the diff, and ensure it changes only the installer filename, welcome title, Windows display version, and `versioninfo.json` from `2.5.8-rc5` to `2.5.8`.

- [ ] **Step 5: Verify and commit the contract repair**

Run: `conda run -n goodq_core python -m pytest -q tests/unit/test_installer_paths.py tests/unit/test_installer_release_contract.py`

Run: `python scripts/install/sync_nsi_version.py --check`

Commit only the four named files with message: `fix(installer): align baseline release metadata`.

### Task 2: Make the private builder observable and baseline-only

**Files:**
- Modify: `scripts/install/build_installer.bat`
- Create: `scripts/install/verify_release_asset.ps1`
- Modify: `tests/unit/test_installer_release_contract.py`

**Interfaces:**
- Consumes: private build inputs located outside tracked public source and a clean private `dev` checkout at the release commit.
- Produces: `GoodQ4All_Setup_2.5.8.exe`, `LAUNCH_GOODQ.exe`, `GoodQ4All_Setup_2.5.8.release_manifest.json`, and `GoodQ4All_Setup_2.5.8.sha256` under one explicit output directory.

- [ ] **Step 1: Write failing builder-boundary tests**

```python
def test_builder_requires_private_inputs_without_leaking_them(repo_root: Path) -> None:
    source = (repo_root / 'scripts/install/build_installer.bat').read_text()
    assert 'GOODQ_INSTALLER_BUILD_ROOT' in source
    assert 'Missing private build input' in source

def test_release_asset_verifier_requires_stable_asset_set(repo_root: Path) -> None:
    source = (repo_root / 'scripts/install/verify_release_asset.ps1').read_text()
    assert 'GoodQ4All_Setup_2.5.8.exe' in source
    assert 'LAUNCH_GOODQ.exe' in source
    assert 'goodq_audio_wsl' not in source
```

- [ ] **Step 2: Run the targeted test to confirm the missing observability contract**

Run: `conda run -n goodq_core python -m pytest -q tests/unit/test_installer_release_contract.py`

Expected: FAIL because the builder currently assumes local private inputs without a declared build root or release asset verifier.

- [ ] **Step 3: Add private builder preflight and bounded output**

Make `build_installer.bat` require `GOODQ_INSTALLER_BUILD_ROOT`, verify compiler, staging, and key availability there, and fail with one named reason per missing input. Keep those inputs outside Git. Write all generated binaries and manifests to `%GOODQ_INSTALLER_BUILD_ROOT%\\out\\v2.5.8`; do not write generated executables into the repository root.

- [ ] **Step 4: Add release-asset verification**

Implement `verify_release_asset.ps1 -AssetRoot <path> -ExpectedCommit <sha> -ExpectedVersion 2.5.8` to check the exact four-asset set, SHA-256 file, manifest hashes, manifest version/commit, absence of WSL/model/corpus payloads, and absence of private path fragments.

- [ ] **Step 5: Run targeted checks and commit**

Run the targeted unit test and a negative PowerShell probe against an empty temporary directory; it must fail before compiling. Commit only installer-builder code and tests with message: `feat(installer): add reproducible baseline build gate`.

### Task 3: Produce and validate a fresh private build

**Files:**
- No tracked-source change required unless Task 2 exposes a defect.

**Interfaces:**
- Consumes: private `dev` at the committed Task 2 revision and the private release workspace inputs.
- Produces: a sealed asset directory outside both repositories.

- [ ] **Step 1: Verify private source and release inputs read-only**

Confirm private `dev` is clean and all current release inputs have source/license evidence. Explicitly exclude the historical 75 GB package’s WSL tar, model archives, optional payloads, and old installer binaries.

- [ ] **Step 2: Run the private builder once**

Set `GOODQ_INSTALLER_BUILD_ROOT` to a new explicit release-build directory and run `scripts/install/build_installer.bat`. Preserve console output and stop on its first failure; do not repair while the build is running.

- [ ] **Step 3: Seal the generated assets**

Run `verify_release_asset.ps1` against the generated directory. Record the four file hashes and source commit in the generated manifest and checksum file.

- [ ] **Step 4: Validate the installer in a disposable location**

Install once into a new disposable Windows install/data root. Run `verify_offline_suite.ps1`, `smoke_test_restore.ps1`, API root/status probes, Qdrant collection probe, and launcher startup/stop proof. Require baseline CPU-safe success only; do not claim WSL audio, local LLM, GPU enhancement, or corpus ingestion.

- [ ] **Step 5: Preserve the receipt and commit any code correction separately**

Keep the clean-install receipt and logs outside Git. If validation exposes a source defect, return to Task 1 or 2, repair on private `dev`, and rebuild from a new empty asset root. Do not upload a failed or superseded build.

### Task 4: Publish the verified baseline installer

**Files:**
- Modify: `docs/bootstrap/OFFLINE_RELEASE_ASSET_MODEL.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the sealed Task 3 asset directory and clean-install receipt.
- Produces: public `v2.5.8` assets and public documentation that accurately distinguishes baseline installation from optional upgrades.

- [ ] **Step 1: Update documentation in private `dev` first**

Add the exact v2.5.8 installer filename, launcher, manifest, checksum, baseline scope, and explicit exclusions. State that WSL audio and local LLM serving are optional post-install upgrades, not baseline claims.

- [ ] **Step 2: Run documentation and release contract checks**

Run the project documentation authority/drift checks and installer contract tests. Commit the documentation update on private `dev`.

- [ ] **Step 3: Flow verified private changes through the sanitized public candidate**

Rebuild the candidate from private `dev`, apply the established release exclusions, verify no private build root, receipt, source path, or asset staging material is tracked, and rerun public CI gates.

- [ ] **Step 4: Upload assets to the existing `v2.5.8` release**

Upload only `GoodQ4All_Setup_2.5.8.exe`, `LAUNCH_GOODQ.exe`, `GoodQ4All_Setup_2.5.8.release_manifest.json`, and `GoodQ4All_Setup_2.5.8.sha256`. Update release notes to identify this as the CPU-safe Windows baseline installer.

- [ ] **Step 5: Independently verify public delivery**

Download the four public assets into a fresh temporary directory, recompute SHA-256, compare it with the published checksum and manifest, and confirm the release page contains no unsupported WSL/audio/LLM claim. Record the public release URL and hashes in the authoritative release ledger.

## Self-Review

- Spec coverage: covers version drift, private build inputs, baseline payload boundary, fresh build, clean install, public delivery, and documentation truth.
- Placeholder scan: no deferred implementation placeholders remain; every mutating action has a verification command or observable pass condition.
- Type consistency: all build steps use `GOODQ_INSTALLER_BUILD_ROOT`, the four named release assets, version `2.5.8`, and source commit `12f577e9` for public delivery.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-03-public-baseline-installer-v2.5.8.md`.

Recommended execution is inline, one task at a time: first correct and test the public installer metadata contract, then build only after the private builder gates are proven. The clean-install and upload portions remain separate release gates.
