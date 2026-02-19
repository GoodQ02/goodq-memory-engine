<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-19 -->

# GoodQ4All Quickstart

Use this when you need the shortest clean path from clone to launch.

## 1. Choose Profile

```powershell
# Legacy canonical behavior
Remove-Item Env:GOODQ_HOST_PROFILE -ErrorAction SilentlyContinue

# CPU-safe portability
$env:GOODQ_HOST_PROFILE = "BASELINE"

# Throughput acceleration
# $env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

## 2. Optional Host Overrides

```powershell
$env:GOODQ_DATA_ROOT = "<path_to_data_root>"
$env:GOODQ_CONDA_ENV = "goodq_core"
$env:GOODQ_WSL_DISTRO = "Ubuntu"
$env:GOODQ_WSL_USER = "<wsl_user>"
$env:GOODQ_WSL_WORKSPACE = "/home/<wsl_user>/goodq_audio"
```

## 3. Optional Strict Flags

```powershell
$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

## 4. Validate and Launch

```powershell
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
```

## 5. Deep Validation (Optional)

```powershell
python scripts/smoke_phase_a.py
```

- Matrix: [`docs/bootstrap/smoke_matrix_phase_a.md`](../../bootstrap/smoke_matrix_phase_a.md)
- Logs: `logs/bootstrap_smoke/`

For full setup detail, use [`docs/guides/install/INSTALL.md`](INSTALL.md).
