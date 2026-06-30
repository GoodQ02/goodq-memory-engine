# Project: GoodQ4All v2.5.8-rc4 Candidate — Version Sync & Model Prefetch Hardening

## Architecture
- **Version Sync**: `goodq_version.py` is the version source of truth. `sync_nsi_version.py` parses it and synchronizes the version string to `goodq4all_installer.nsi` (DisplayVersion) and `versioninfo.json` (prerelease strings). `build_installer.bat` runs the sync script and must fail the build pipeline if version synchronization fails.
- **Model Prefetch**: `configs/model_registry.yaml` lists model definitions. `scripts/bootstrap_models.py` downloads models using `steps/common/model_provisioner.py` and logs to writable logs path. It must exit non-zero if any `REQUIRED` model fails to prefetch. `LAUNCH_GOODQ.go` executes bootstrap and must fail startup if it exits non-zero.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Phase 0 Audit & Fix Plan | Audit version surfaces, model prefetch registries, and prepare Fix Plan | None | DONE |
| 2 | Version Sync Automation (R1, R5) | Regex fix in `sync_nsi_version.py`, build script error gating, and update version files to rc4 | M1 | PLANNED |
| 3 | Model Prefetch Hardening & Python Path Resolution (R2, R3, R4) | Pin `silero_vad` to tag `v4.0.2`, exit 1 in `bootstrap_models.py` on required failure, terminate startup in `LAUNCH_GOODQ.go`, and implement fallback Python path resolution | M1 | PLANNED |
| 4 | Testing & Build Gates | Verify unit tests, check mock failures, run stage check, and rebuild installer | M2, M3 | PLANNED |
| 5 | Sandbox & Release Verification | Verify DisplayVersion and bootstrap failure behavior in sandbox; generate release manifest and tags | M4 | PLANNED |

## Interface Contracts
### `sync_nsi_version.py` ↔ `build_installer.bat`
- Exit Code: `0` on successful update of all fields. Non-zero if regex replacement fails or file cannot be written.
- Error Handling: Batch script checks `%ERRORLEVEL%` and exits immediately, halting installer compilation.

### `bootstrap_models.py` ↔ `LAUNCH_GOODQ.go`
- Exit Code: `0` on success or only optional model failures. `1` if any required model (e.g. `silero_vad`) fails.
- Output Report: Writes progress and report JSON.
- Launcher Handling: Launcher checks command execution exit error and aborts with fatal error box instead of continuing.

## Code Layout
- `goodq_version.py` - package version source of truth.
- `scripts/install/sync_nsi_version.py` - version sync automation script.
- `scripts/install/goodq4all_installer.nsi` - NSIS installer configuration script.
- `scripts/install/versioninfo.json` - metadata for built executable.
- `configs/model_registry.yaml` - model definitions registry.
- `scripts/bootstrap_models.py` - model download orchestrator.
- `LAUNCH_GOODQ.go` - Go launcher and watchdog manager.
