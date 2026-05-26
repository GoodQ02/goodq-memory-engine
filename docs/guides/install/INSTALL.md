<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# GoodQ4All Install

This is the canonical install and bootstrap guide.

## Preferred Fresh-Machine Path

For a fresh Windows 11 machine, use the bootstrap installer first. macOS and
Linux are not supported first-run hosts for this repository today; see
[`docs/reference/PLATFORM_SUPPORT.md`](../../reference/PLATFORM_SUPPORT.md).

Prerequisites:

- Git
- Miniconda or Anaconda visible to the shell
- Python 3.10 or newer
- at least 25 GB free for the baseline path (breakdown: ~4 GB conda environments, ~12 GB model cache prefetch, ~6 GB processing workspace, ~3 GB database storage; space required is lower if model prefetch is skipped)
- optional: NVIDIA GPU and WSL2 Ubuntu for accelerated lanes

```powershell
python scripts/bootstrap_install.py
```

That path creates or updates the `goodq_core` orchestration environment,
provisions the supported specialized step-env pack required by the active
pipeline from the pinned stable recipes under `envs/locks/`, writes local-only
overrides when missing, performs lightweight verification, and launches the
canonical launcher surface.

For local secrets or provider settings, copy `.env.local.template` to
`.env.local` and edit `.env.local`. The broader `.env.template` is a contract
reference for maintainers and advanced operators.

When `GPU_ENHANCED` / WSL audio is enabled, the bootstrap path stages the WSL
audio constraints from `wsl2_audio/requirements-bootstrap-constraints.txt`.
Do not repair WSL audio with unpinned package upgrades; use the bootstrap/setup
path so the `pyannote.audio==3.3.2` / `huggingface-hub==0.35.3` pair remains
intact.

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
- `GOODQ_WSL_DISTRO`: optional WSL distro override; leave unset to auto-select an Ubuntu-like distro.
- `GOODQ_WSL_USER`: optional explicit WSL user.
- `GOODQ_WSL_WORKSPACE`: optional explicit WSL workspace.

Example:

```powershell
$env:GOODQ_DATA_ROOT = "<path_to_data_root>"
$env:GOODQ_CONDA_ENV = "goodq_core"
# Optional: set GOODQ_WSL_DISTRO only when auto-detection should not choose.
# $env:GOODQ_WSL_DISTRO = "<wsl_distro>"
$env:GOODQ_WSL_USER = "<wsl_user>"
$env:GOODQ_WSL_WORKSPACE = "/home/<wsl_user>/goodq_audio"
```

`GOODQ_DATA_ROOT` is the base root. Runtime paths derive `GoodQ_Data` beneath
that base, including `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`.
If the bootstrap summary shows a selected path that already ends in
`GoodQ_Data`, use that folder directly as the runtime data root; do not append
another `GoodQ_Data` segment.

When `GOODQ_WSL_DISTRO` is not set, bootstrap preserves an explicit local
setting, otherwise it prefers the first Ubuntu-like distro detected and falls
back to the installer default (`Ubuntu`).

## Manual Setup (Advanced / Existing Environment)

Use this path when you need deterministic manual control instead of the bootstrap
installer.

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
