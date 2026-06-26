<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# GoodQ4All Installation

This is the canonical installation guide.

## 1. Standalone User Installation (Recommended)

GoodQ4All is packaged as a unified sandboxed Windows Installer. This is the simplest path and does not require pre-existing Git, Conda, or Python environments on the host.

<p align="left">
  <a href="https://github.com/GoodQ02/goodq4all/releases/download/v2.5.7/GoodQ4All_Setup_2.5.7.exe" style="display: inline-block; padding: 12px 24px; background-color: #ffb300; color: #110d1a; font-weight: bold; text-decoration: none; border-radius: 4px; box-shadow: 0 4px 10px rgba(255, 179, 0, 0.3); transition: all 0.2s ease; margin: 10px 0;">
    🚀 Download GoodQ4All Setup v2.5.7.exe
  </a>
</p>

> [!IMPORTANT]
> **Zero-Dependency Offline Architecture**
>
> GoodQ4All is a **100% local, zero-dependency, private offline alternative** to major cloud-based media intelligence services. By packaging the isolated Python runtime, Qdrant database, and perception libraries into a single sandboxed executable, we have made private video search and knowledge graph memory as easy to install as any desktop application. No cloud dependencies, no subscription fees, and no data leaks.

### Prerequisites
* **Operating System**: Windows 11
* **Disk Space**: At least 25 GB free space (to host local database, processing workspace, and model prefetch caches).
* **Optional**: An NVIDIA GPU and WSL2 Ubuntu for accelerated lanes.

### Installation Steps
1. Download and run the setup installer: `GoodQ4All_Setup_2.5.7.exe`.
2. Choose your installation path (defaults to `%PROGRAMFILES%\GoodQ4All`).
3. Complete the setup. This installs the binary files, configures registry keys (for Add/Remove Programs and shortcuts), and provisions the isolated python runtime, branding resources, and database.
4. Double-click the **GoodQ4All** Desktop or Start Menu shortcut to run the supervisor launcher (**LAUNCH_GOODQ.exe** located in `%PROGRAMFILES%\GoodQ4All\`).
5. The launcher will automatically perform preflight checks, verify the model signature, start local background services, and open your default browser to the **Retro Memory Explorer** (served at `http://127.0.0.1:30000/ui/retro_console_v1/`).
6. **Start Ingesting**: In the Retro Memory Explorer UI header, click the **Upload Pad** and drag-and-drop or select any media file onto the yellow-dotted helipad circle to start ingestion instantly!

---

## 2. Developer Workspace Setup (Advanced / Run From Source)

For developers or advanced operators who want to run the project from source code:

### Prerequisites
* Windows 11 with PowerShell
* Git
* Miniconda or Anaconda visible to the shell
* Python 3.10 or newer
* At least 25 GB free space (breakdown: ~4 GB conda environments, ~12 GB model cache prefetch, ~6 GB processing workspace, ~3 GB database storage).

macOS (Apple Silicon) and Linux are fully supported as native first-run hosts for direct local execution; see the specific setup guides in [`docs/guides/install/setup-macos.md`](setup-macos.md) and [`docs/guides/install/setup-linux.md`](setup-linux.md), and the platform reference [`docs/reference/PLATFORM_SUPPORT.md`](../../reference/PLATFORM_SUPPORT.md).

### Bootstrap Steps
```powershell
python scripts/bootstrap_install.py
```

This path creates or updates the `goodq_core` orchestration environment, provisions the supported specialized step-env pack required by the active pipeline from the pinned stable recipes under `envs/locks/`, writes local-only overrides when missing, performs lightweight verification, and launches the canonical launcher surface.

For local secrets or provider settings, copy `.env.local.template` to `.env.local` and edit `.env.local`. The broader `.env.template` is a contract reference for maintainers and advanced operators.

When `GPU_ENHANCED` / WSL audio is enabled, the bootstrap path stages the WSL audio constraints from `wsl2_audio/requirements-bootstrap-constraints.txt`. Do not repair WSL audio with unpinned package upgrades; use the bootstrap/setup path so the `pyannote.audio==3.3.2` / `huggingface-hub==0.35.3` pair remains intact.

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
# Safe-mode check (readiness only)
.\LAUNCH_GOODQ.ps1

# Launch with watchdog-driven Ingestion enabled
.\LAUNCH_GOODQ.ps1 -StartIngestion
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
