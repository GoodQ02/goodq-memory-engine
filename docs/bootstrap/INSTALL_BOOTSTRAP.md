<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->

# GoodQ Bootstrap Installer

## Purpose

`scripts/bootstrap_install.py` is a thin bootstrap layer for new Windows machines.

It does not change GoodQ runtime architecture. It only:

- inspects host capabilities
- prepares the core Conda environment for the selected runtime profile
- provisions the supported specialized step-env pack required by the active pipeline
- creates local-only config files when missing
- assists with external runtime prerequisites when they are missing
- runs lightweight verification
- launches [`LAUNCH_GOODQ.bat`](../../LAUNCH_GOODQ.bat)

## What It Uses

The bootstrap intentionally reuses existing project surfaces:

- [`environment.yml`](../../environment.yml)
- [`environment.gpu.yml`](../../environment.gpu.yml)
- [`LAUNCH_GOODQ.bat`](../../LAUNCH_GOODQ.bat)
- [`scripts/bootstrap_verify.py`](../../scripts/bootstrap_verify.py)
- [`scripts/bootstrap_models.py`](../../scripts/bootstrap_models.py)
- [`scripts/qdrant/INSTALL_QDRANT_SERVICE.bat`](../../scripts/qdrant/INSTALL_QDRANT_SERVICE.bat)
- [`scripts/qdrant/START_QDRANT.bat`](../../scripts/qdrant/START_QDRANT.bat) for foreground testing fallback only
- [`configs/config.yaml`](../../configs/config.yaml)
- [`configs/config.local.example.yaml`](../../configs/config.local.example.yaml)
- [`.env.local.template`](../../.env.local.template)

## What It Prompts For

On a normal interactive run, the bootstrap prompts for:

- base data root directory
- whether to enable GPU acceleration
- whether to enable WSL audio acceleration
- whether to provision the supported specialized step-env pack for full pipeline capability
- whether to prefetch the required local model cache for offline-ready ingest
- whether to accept Conda channel Terms of Service when the local Conda installation requires it
- whether to install missing external tools such as FFmpeg when a supported package manager is available
- whether to install or repair the Windows `GoodQ_Qdrant` service when Qdrant is unavailable

When model prefetch is enabled, bootstrap now streams live progress to the console and retries transient download failures automatically instead of leaving a silent cursor wait.
It also reports whether Hugging Face / PyAnnote auth was detected from `.env.local` or the current environment without printing any secret values. Accepted Hugging Face aliases are `HF_TOKEN`, `HF_HUB_TOKEN`, `HUGGINGFACE_HUB_TOKEN`, and `HUGGINGFACE_TOKEN`.

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

# Skip model-cache downloads during bootstrap
python scripts/bootstrap_install.py --skip-model-prefetch
```

## Bootstrap Hygiene For Repeated Test Runs

If a first install has been retried several times, use the hygiene helper before
declaring success. It does not delete anything. It records the current
install-relevant state and prints a reviewed manual reset plan.

```powershell
# Snapshot current GoodQ bootstrap state.
python scripts/bootstrap_hygiene.py snapshot --output .tmp_bootstrap_hygiene\before.json

# Print a clean Windows-only reset plan using a fresh data root.
python scripts/bootstrap_hygiene.py plan-reset --fresh-data-root "%USERPROFILE%\GoodQ_Bootstrap_Test"
```

For a practical laptop retest, the clean baseline is:

- archive `.env.local` and `configs/config.local.yaml`
- remove only GoodQ Conda envs: `goodq_core` and the supported `goodq_*` step
  env pack
- keep existing user media and old data roots untouched
- rerun bootstrap with a new `--data-root`
- keep WSL audio disabled when narrowing the Windows-only path
- run bootstrap validation and the dry-run launcher before starting ingestion

This avoids a false positive from partial Conda envs or old local config while
preserving package caches, model caches, and user data unless the operator
chooses to test those separately.

## Capability Model

The bootstrap classifies the machine into:

- `BASELINE`
- `GPU_ENHANCED`

It also reports:

- `GPU_AVAILABLE`
- `WSL_AVAILABLE`

`BASELINE` always remains CPU-safe.

WSL distro selection:

- if `GOODQ_WSL_DISTRO` is already set, the bootstrap preserves it
- otherwise it prefers the first Ubuntu-like distro detected on the host
- if no Ubuntu-like distro is present, it falls back to the existing default behavior

Environment selection:

- `BASELINE` uses [`environment.yml`](../../environment.yml)
- `GPU_ENHANCED` uses [`environment.gpu.yml`](../../environment.gpu.yml)
- both profiles target the same `goodq_core` orchestration environment name
- bootstrap also provisions the supported specialized step-env pack for image, audio, and video steps that still require isolated dependency boundaries
- bootstrap can prefetch the required non-gated model cache into the local models root so first ingest stays offline-ready
- model prefetch now follows `configs/model_registry.yaml` directly, so pinned repo ids and revisions stay aligned without separate hardcoded bootstrap lists
- the step-env pack is installed from the pinned lock recipes in `envs/locks/` instead of a fresh dependency solve
- `goodq_face_embed` additionally installs Conda `dlib` first so Windows hosts do not need to compile it from source during bootstrap
- the bootstrap defaults to `BASELINE`; GPU throughput remains explicit opt-in

## Lightweight Verification

The bootstrap performs only lightweight checks:

- Conda environment exists
- supported specialized step environments exist
- required non-gated model caches are visible when they have already been prefetched
- environment Python is available
- config loader works
- FFmpeg status is clear
- `pdftotext` / Poppler status is clear for PDF ingestion
- Qdrant reachability is checked
- Qdrant Windows service status is surfaced when Qdrant is unavailable
- launcher exists

If Qdrant is unavailable, the bootstrap recommends repairing or installing the
Windows `GoodQ_Qdrant` service first, attempts the existing service installer
when the operator consents, and mentions the foreground start helper only as a
manual testing fallback.

GitHub Actions uses `scripts/bootstrap_verify.py --json --profile ci` as a
baseline repo/environment sanity contract. The CI profile requires tracked lock
recipes and core repo checks, but it does not prove desktop Qdrant service
readiness or provision the specialized step environment pack. The default
desktop verifier profile remains the operator-facing bootstrap/runtime check,
and ingestion witnesses still require Qdrant to be reachable. CI also binds
`GOODQ_DATA_ROOT` to a runner-local workspace directory so import-time unit tests
do not assume the desktop data drive exists. CodeQL is gated off while the
repository is private unless code scanning is enabled for the repository.

When the installer must cross a UAC elevation boundary, bootstrap now passes the
already-resolved canonical storage/log paths into the service installer so the
admin hop does not have to rediscover the Python/Conda runtime before creating
the service.

If FFmpeg is unavailable, the bootstrap keeps going but prints explicit
installation guidance:

- preferred: `winget`
- fallback: `choco`
- otherwise: manual install or `GOODQ_FFMPEG_EXE`

If `pdftotext` is unavailable, the bootstrap keeps going but reports that PDF
ingestion still needs Poppler and points at:

- `GOODQ_POPPLER_BIN`
- `pdftotext` on `PATH`

If Conda environment creation is blocked by unaccepted channel Terms of
Service, the bootstrap now detects that condition explicitly and prints or
executes the required `conda tos accept ...` commands only with operator
consent.

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
