<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# GoodQ4All Laptop Guide

This profile keeps laptop operation deterministic and portable.

## Recommended Defaults

```powershell
$env:GOODQ_HOST_PROFILE = "BASELINE"
$env:GOODQ_REQUIRE_GPU = "0"
$env:GOODQ_REQUIRE_WSL_AUDIO = "0"
```

## Optional Acceleration

Use `GPU_ENHANCED` only when laptop CUDA/WSL paths are validated:

```powershell
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

## Optional Host Overrides

```powershell
$env:GOODQ_DATA_ROOT = "<path_to_data_root>"
$env:GOODQ_CONDA_ENV = "goodq_core"
$env:GOODQ_WSL_DISTRO = "<wsl_distro>"
$env:GOODQ_WSL_USER = "<wsl_user>"
$env:GOODQ_WSL_WORKSPACE = "/home/<wsl_user>/goodq_audio"
```

Leave `GOODQ_WSL_DISTRO` unset unless you need a deterministic distro binding.
Bootstrap and validation prefer the first Ubuntu-like distro detected on the
host when no explicit value is provided.

## Validation

```powershell
.\scripts\bootstrap_validate.bat
python scripts/smoke_phase_a.py
```

Logs are written to `logs/bootstrap_smoke/`.

For full setup flow, use [`docs/guides/install/INSTALL.md`](INSTALL.md).
