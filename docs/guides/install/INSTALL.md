<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-19 -->

# GoodQ4All Install

This is the canonical install and bootstrap guide.

## Performance Profiles

GoodQ4All supports three profile semantics:

- `UNSET`: legacy canonical behavior (default when `GOODQ_HOST_PROFILE` is not set).
- `BASELINE`: CPU-safe portability mode.
- `GPU_ENHANCED`: additive acceleration mode (CUDA/WSL when available).

Profile selection:

```powershell
$env:GOODQ_HOST_PROFILE = "BASELINE"
# or
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

Strict fail-fast controls:

```powershell
$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

- Keep strict flags off for permissive/dev flows.
- Enable strict flags for deterministic desktop enforcement.

## Host and Path Abstraction

Canonical portability variables:

- `GOODQ_DATA_ROOT`: data root override (default fallback remains platform contract).
- `GOODQ_CONDA_ENV`: interpreter env override (default: `goodq_core`).
- `GOODQ_WSL_DISTRO`: WSL distro override (default: `Ubuntu`).
- `GOODQ_WSL_USER`: optional explicit WSL user.
- `GOODQ_WSL_WORKSPACE`: optional explicit WSL workspace.

Example:

```powershell
$env:GOODQ_DATA_ROOT = "<path_to_data_root>"
$env:GOODQ_CONDA_ENV = "goodq_core"
$env:GOODQ_WSL_DISTRO = "Ubuntu"
$env:GOODQ_WSL_USER = "<wsl_user>"
$env:GOODQ_WSL_WORKSPACE = "/home/<wsl_user>/goodq_audio"
```

## Install Steps

1. Clone and open `<project_root>`.
2. Configure `.env.local` with required tokens/secrets.
3. Select runtime profile (`BASELINE` or `GPU_ENHANCED`).
4. Run bootstrap validation:

```powershell
.\scripts\bootstrap_validate.bat
```

5. Launch:

```powershell
.\LAUNCH_GOODQ.ps1
```

## Smoke Matrix

Use the Phase A smoke matrix when validating profile and fail-fast behavior:

- Guide: [`docs/bootstrap/smoke_matrix_phase_a.md`](../../bootstrap/smoke_matrix_phase_a.md)
- Runner: [`scripts/smoke_phase_a.py`](../../../scripts/smoke_phase_a.py)
- Logs: `logs/bootstrap_smoke/`

## Related Canonical Docs

- Quickstart: [`docs/guides/install/QUICKSTART.md`](QUICKSTART.md)
- Laptop profile guide: [`docs/guides/install/LAPTOP.md`](LAPTOP.md)
- Path contract: [`docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md`](../../bootstrap/PATH_ABSTRACTION_CONTRACT.md)
