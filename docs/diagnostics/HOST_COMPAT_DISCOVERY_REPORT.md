<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GENERATED_SNAPSHOT -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Host Compatibility Discovery Report

Date: 2026-02-18
Mode: Static discovery only (no runtime execution, no imports of project modules)

## Intent
Identify host-specific assumptions in runtime/bootstrap surfaces and classify each as:
- `must-fix for portability`
- `allowed legacy (docs/archive)`

## Canonical Config Determination
Canonical config is `configs/config.yaml`.

Evidence:
- `AGENTS.md:47` mandates config loading via `config_loader`.
- `steps/common/config_loader.py:87-88` explicitly labels and loads `configs/config.yaml` as the unified primary config.
- `LAUNCH_GOODQ.ps1:53` calls `load_configs()` from `steps.common.config_loader`.
- `api/main.py:24` imports `load_configs`; `api/main.py:65` loads `_CFG = load_configs({})`.

Decision:
- `configs/config.yaml` is authoritative for runtime configuration indirection.

## Findings

### A) Drive letters / absolute paths in runtime entry surfaces

#### Must-fix for portability
- `LAUNCH_GOODQ.bat:5-6`
  - Hardcoded repo root: legacy fixed-drive repo-root literal
  - Classification: must-fix (runtime launcher portability blocker)
  - Resolution: use `%~dp0` / script-relative path indirection (out-of-scope in this mission's edit list).

- `LAUNCH_GOODQ.ps1:22`
  - Hardcoded data root: legacy fixed-drive `GoodQ_Data` root
  - Classification: must-fix (runtime bootstrap default host coupling)
  - Resolution: derive from `GOODQ_DATA_ROOT` / config paths.

- `api/main.py:306,537,668,720,747,749,801,964,1172,1173,1174,1384`
  - Hardcoded fixed-drive data-root and repo-root path families
  - Classification: must-fix (runtime API behavior tied to one host layout)
  - Resolution: derive from `_CFG['paths']`, repo-relative root, and `GOODQ_DATA_ROOT` fallback.

- `configs/paths.py:26,31,76`
  - Hardcoded fixed-drive repo root, `GoodQ_Data` root, and model-cache root
  - Classification: must-fix (shared path module host-bound)
  - Resolution: env-backed path construction (`GOODQ_DATA_ROOT`) + repo-relative root.

#### Must-fix but out-of-scope for this patch set (reported only)
- `configs/model_registry.yaml:123,129,135,151`
  - Hardcoded fixed-drive tool/snapshot paths
  - Classification: must-fix (portability), out-of-scope per allowed file list.
  - Resolution: host/config indirection in registry paths.

- `scripts/qdrant/*.bat`
  - Hardcoded fixed-drive repo/data roots and env name `goodq_core`:
    - `scripts/qdrant/INIT_QDRANT.bat:14`
    - `scripts/qdrant/START_QDRANT.bat:12,17`
    - `scripts/qdrant/INSTALL_QDRANT_SERVICE.bat:30,32,33,34,35,36,44,47,48,49,50,51,52,69,70,77`
    - `scripts/qdrant/UNINSTALL_QDRANT_SERVICE.bat:26,31,33,34`
  - Classification: must-fix (bootstrap/service portability), out-of-scope per allowed file list.
  - Resolution: `%~dp0` + env/config-driven data/log/conda resolution.

### B) Hardcoded WSL distro/user/workspace assumptions

#### Must-fix for portability
- `scripts/wsl2_audio_bridge.py:16-18`
  - Hardcoded user `joesdomingo`, workspace `/home/joesdomingo/goodq_audio`, distro `Ubuntu`
  - Classification: must-fix
  - Resolution: `GOODQ_WSL_USER`, `GOODQ_WSL_WORKSPACE`, `GOODQ_WSL_DISTRO` with dynamic user fallback when unset.

- `api/main.py:378,393,414,436,1075,1090,1100,1111`
  - Inline subprocess WSL calls hardcode `-d Ubuntu`
  - Classification: must-fix
  - Resolution: centralized WSL distro resolver with env/config fallback.

- `api/main.py:1065,1067,1075`
  - Hardcoded WSL UNC and Linux home path with fixed user `joesdomingo`
  - Classification: must-fix
  - Resolution: construct paths from resolved `wsl_user` + `wsl_workspace`.

### C) Conda env naming drift

#### Must-fix for portability
- `LAUNCH_GOODQ.ps1:37`
  - Hardcoded runtime env name `goodq_core`
  - Classification: must-fix (runtime launch path), but out-of-scope for this patch set due allowed-file lock.
  - Resolution: resolve via `GOODQ_CONDA_ENV` (default `goodq_core`).

- `configs/config.yaml:116,125`
  - Env identifiers fixed to `goodq_core`
  - Classification: must-fix for configurable portability
  - Resolution: make env names env-driven with default `goodq_core`.

- `scripts/qdrant/INIT_QDRANT.bat:14`
  - Hardcoded env name `goodq_core`
  - Classification: must-fix, out-of-scope per allowed file list.
  - Resolution: `GOODQ_CONDA_ENV`.

### D) Username-specific conda path assumptions

#### Must-fix for portability
- `configs/python_paths.py:95-96`
  - Hardcoded `/mnt/c/Users/jdben/miniconda3` and `/mnt/c/Users/Administrator/miniconda3`
  - Classification: must-fix
  - Resolution: user-agnostic `/mnt/c/Users/*/miniconda3` discovery.

## Allowed Legacy (docs/archive)
- None in this discovery pass. This mission scanned runtime/bootstrap/config surfaces only.

## Planned Surgical Patch Scope
In-scope files for this mission patch:
- `configs/config.yaml`
- `configs/paths.py`
- `configs/python_paths.py`
- `scripts/_lib/interpreter_bindings.ps1`
- `scripts/_lib/interpreter_bindings.bat`
- `scripts/wsl2_audio_bridge.py`
- `api/main.py`

Out-of-scope (reported, not modified):
- `LAUNCH_GOODQ.ps1`
- `LAUNCH_GOODQ.bat`
- `scripts/qdrant/*`
- `configs/model_registry.yaml`
