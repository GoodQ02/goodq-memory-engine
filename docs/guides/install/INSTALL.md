<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# GoodQ4All Install (Canonical)

This is the canonical installation and bootstrap guide for active environments.

## Runtime Profiles

- `UNSET`: legacy canonical behavior (current defaults preserved).
- `BASELINE`: CPU-safe, GPU-optional portability mode.
- `GPU_ENHANCED`: additive throughput mode (CUDA/WSL acceleration allowed).

Use PowerShell:

```powershell
# CPU-safe baseline
$env:GOODQ_HOST_PROFILE = "BASELINE"

# Throughput profile
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

Strict fail-fast controls:

```powershell
# Require GPU capability or fail fast
$env:GOODQ_REQUIRE_GPU = "1"

# Require WSL audio availability or fail fast
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

## Path and Host Identity Abstraction

- `GOODQ_DATA_ROOT`: data root override.
  - if unset, default data root is `<GOODQ_DATA_ROOT>`.
- `GOODQ_WSL_USER`: optional WSL user override.
- `GOODQ_WSL_WORKSPACE`: optional WSL workspace override.
- `GOODQ_WSL_DISTRO`: optional distro override (default `Ubuntu`).

Examples:

```powershell
$env:GOODQ_DATA_ROOT = "D:/GoodQData"
$env:GOODQ_WSL_USER = "<user>"
$env:GOODQ_WSL_WORKSPACE = "/home/<user>/goodq4all"
$env:GOODQ_WSL_DISTRO = "Ubuntu"
```

## Install Steps

1. Clone repo and open `<project_root>` in PowerShell.
2. Ensure the project interpreter/environment is available.
3. Configure `.env.local` with required credentials.
4. Validate config resolution:
   - `python -c "from steps.common.config_loader import load_configs; print(load_configs().get('paths',{}))"`
5. Run profile smoke matrix:
   - `python scripts/smoke_phase_a.py`

## Smoke Matrix Validation

Phase A smoke output:

- script: `scripts/smoke_phase_a.py`
- guide: `docs/bootstrap/smoke_matrix_phase_a.md`
- logs: `logs/bootstrap_smoke/`

Use smoke results to verify:

- profile resolution (`UNSET` / `BASELINE` / `GPU_ENHANCED`)
- GPU auto-config behavior
- WSL audio enablement behavior
- path resolution via `GOODQ_DATA_ROOT`
- strict fail-fast flags (`GOODQ_REQUIRE_GPU`, `GOODQ_REQUIRE_WSL_AUDIO`)
