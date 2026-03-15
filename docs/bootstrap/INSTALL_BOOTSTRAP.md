<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->

# GoodQ Bootstrap Installer

## Purpose

`scripts/bootstrap_install.py` is a thin bootstrap layer for new Windows machines.

It does not change GoodQ runtime architecture. It only:

- inspects host capabilities
- prepares the public baseline Conda environment from [`environment.yml`](../../environment.yml)
- creates local-only config files when missing
- runs lightweight verification
- launches [`LAUNCH_GOODQ.bat`](../../LAUNCH_GOODQ.bat)

## What It Uses

The bootstrap intentionally reuses existing project surfaces:

- [`environment.yml`](../../environment.yml)
- [`LAUNCH_GOODQ.bat`](../../LAUNCH_GOODQ.bat)
- [`scripts/bootstrap_verify.py`](../../scripts/bootstrap_verify.py)
- [`scripts/qdrant/START_QDRANT.bat`](../../scripts/qdrant/START_QDRANT.bat)
- [`configs/config.yaml`](../../configs/config.yaml)
- [`configs/config.local.example.yaml`](../../configs/config.local.example.yaml)
- [`.env.local.template`](../../.env.local.template)

## What It Prompts For

On a normal interactive run, the bootstrap prompts for:

- base data root directory
- whether to enable GPU acceleration
- whether to enable WSL audio acceleration

Default portable data root:

- a local Windows data root chosen by the bootstrap installer
- current default implementation: `GOODQ_DATA_ROOT` points at the base root on the
  system drive
- the runtime then derives:
  - `GoodQ_Data/`
  - `models/`
  - `qdrant_storage/`

Private machine configuration is written only to:

- `.env.local`
- `configs/config.local.yaml`

The public config is not modified.

## Manual Usage

Run from the repository root:

```powershell
python scripts/bootstrap_install.py
```

Useful flags:

```powershell
# Inspect only, no changes
python scripts/bootstrap_install.py --inspect-only

# Create/update the core env and local config, but do not launch
python scripts/bootstrap_install.py --yes --no-launch

# Verification only
python scripts/bootstrap_install.py --verify-only --no-launch

# Force CPU-safe profile
python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio
```

## Capability Model

The bootstrap classifies the machine into:

- `BASELINE`
- `GPU_ENHANCED`

It also reports:

- `GPU_AVAILABLE`
- `WSL_AVAILABLE`

`BASELINE` always remains CPU-safe.

## Lightweight Verification

The bootstrap performs only lightweight checks:

- Conda environment exists
- environment Python is available
- config loader works
- Qdrant reachability is checked
- launcher exists

It does not run ingestion or a full pipeline test.

## PyInstaller Packaging

The script is written to stay compatible with a later PyInstaller wrap.

Example:

```powershell
pyinstaller --onefile --name GoodQBootstrap scripts/bootstrap_install.py
```

Resulting executable flow:

- detects the repo root
- uses the same public environment/config surfaces
- launches [`LAUNCH_GOODQ.bat`](../../LAUNCH_GOODQ.bat) after setup

## Files Touched By The Bootstrap At Runtime

Created only if missing:

- `.env.local`
- `configs/config.local.yaml`
- the selected base data root directory and its derived GoodQ subpaths

No core pipeline files are modified by the installer.
