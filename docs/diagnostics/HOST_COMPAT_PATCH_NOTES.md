# Host Compatibility Patch Notes

Date: 2026-02-18
Mission: Host-Compatibility Abstraction Layer (discovery-first, surgical changes)

## Scope Executed
Modified only these in-scope files:
- `configs/config.yaml`
- `configs/paths.py`
- `configs/python_paths.py`
- `scripts/_lib/interpreter_bindings.ps1`
- `scripts/_lib/interpreter_bindings.bat`
- `scripts/wsl2_audio_bridge.py`
- `api/main.py`

New reports:
- `docs/diagnostics/HOST_COMPAT_DISCOVERY_REPORT.md`
- `docs/diagnostics/HOST_COMPAT_PATCH_NOTES.md`

No changes under `vendor/`.
No file deletions.
No archive modifications.

## What Changed (Surgical)

### 1) Canonical host identity block in config
File: `configs/config.yaml`

Added:
- `host.profile: ${GOODQ_HOST_PROFILE:-UNSET}`
- `host.data_root`: env-backed canonical host data root
- `host.wsl_distro: ${GOODQ_WSL_DISTRO:-Ubuntu}`
- `host.wsl_user: ${GOODQ_WSL_USER:-auto}`
- `host.conda_env: ${GOODQ_CONDA_ENV:-goodq_core}`

Updated env naming indirection:
- `gpu.primary_env` now uses `${GOODQ_CONDA_ENV:-goodq_core}`
- `envs.core` now uses `${GOODQ_CONDA_ENV:-goodq_core}`

### 2) Data root and project path de-hardcoding
File: `configs/paths.py`

- `PROJECT_ROOT` now resolves from file location (`Path(__file__).resolve().parents[1]`)
- `DATA_ROOT` now derives from `GOODQ_DATA_ROOT` (fallback preserved)
- `MODELS_DIR` now derives from `GOODQ_DATA_ROOT`

### 3) WSL conda path discovery de-identitying
File: `configs/python_paths.py`

- Removed hardcoded WSL user paths (`/mnt/c/Users/jdben/...`, `/mnt/c/Users/Administrator/...`)
- Added user-agnostic discovery over `/mnt/c/Users/*/(mini|ana)conda3`

### 4) Interpreter bindings: conda env indirection
Files: `scripts/_lib/interpreter_bindings.ps1`, `scripts/_lib/interpreter_bindings.bat`

- Added `GOODQ_CONDA_ENV` default handling (`goodq_core`)
- Added `Get-GoodQCondaEnv` helper in PowerShell bindings

### 5) WSL bridge user/workspace abstraction
File: `scripts/wsl2_audio_bridge.py`

- Removed hardcoded user/workspace literals
- Resolution now:
  - user: `GOODQ_WSL_USER` -> `USER/USERNAME/LOGNAME` -> `user`
  - workspace: `GOODQ_WSL_WORKSPACE` -> `/home/<resolved-user>/goodq_audio`
  - distro: `GOODQ_WSL_DISTRO` default `Ubuntu`

### 6) API runtime host abstraction
File: `api/main.py`

- Added centralized host/path resolution from `_CFG.host`, `_CFG.paths`, and env overrides
- Replaced hardcoded fixed-drive data and repo-root paths with derived paths
- Replaced hardcoded WSL distro/user/workspace literals in subprocess path construction with resolved `_WSL_DISTRO`, `_WSL_USER`, `_WSL_WORKSPACE`

## Static Validation (No Runtime Execution)

Checks run:
- `joesdomingo` in patched runtime/config files
- literal fixed-drive data-root token in patched runtime code files
- hardcoded `"Ubuntu"` in WSL subprocess calls
- conda env naming references in launch/config bindings

Results:
- `joesdomingo`: **0 matches** in patched runtime/config files.
- fixed-drive data-root literals in runtime code (`api/main.py`, `configs/paths.py`, bridge/bindings): **0 matches**.
- `"Ubuntu"` remains only as allowed default-value declarations:
  - `api/main.py` host fallback default
  - `scripts/wsl2_audio_bridge.py` env default
  - interpreter bindings default
- `GOODQ_CONDA_ENV` wired in config + bindings.

Remaining hardcoded assumptions (known, out-of-scope in this mission):
- `LAUNCH_GOODQ.ps1:22` (legacy fixed-drive `GoodQ_Data` default)
- `LAUNCH_GOODQ.ps1:37` (`goodq_core`)
- `scripts/qdrant/*.bat` still contain fixed-drive path literals and one `goodq_core` invocation
- `configs/model_registry.yaml` contains fixed-drive tool/snapshot paths

## Why these out-of-scope remain
Per mission scope lock, launcher and qdrant service scripts were discovery targets but not in the allowed implementation file list.

## Desktop Checklist (minimal)
Set these before first desktop run (example values):
- `GOODQ_HOST_PROFILE=GPU_ENHANCED`
- `GOODQ_DATA_ROOT=<host_data_root>`
- `GOODQ_WSL_DISTRO=Ubuntu`
- `GOODQ_WSL_USER=<desktop_wsl_user>`
- `GOODQ_CONDA_ENV=goodq_core`

Optional strictness flags (already documented, unchanged behavior):
- `GOODQ_REQUIRE_GPU=1`
- `GOODQ_REQUIRE_WSL_AUDIO=1`

## Follow-up Candidates (separate commit)
- Move `LAUNCH_GOODQ.ps1` `DataRoot/CoreEnv` to env/config indirection.
- De-hardcode `scripts/qdrant/*.bat` for `%~dp0` + env/config path resolution.
- De-hardcode `configs/model_registry.yaml` tool/snapshot path literals.
