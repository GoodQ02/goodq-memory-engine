<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# GoodQ4All Laptop Profile Guide (Canonical)

Laptop targets should default to portability-first behavior.

## Recommended Profile

```powershell
$env:GOODQ_HOST_PROFILE = "BASELINE"
```

This keeps runtime CPU-safe and avoids GPU/WSL acceleration as correctness dependencies.

## Optional Enhancements

If the laptop has supported acceleration available:

```powershell
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

## Path and WSL Identity Overrides

```powershell
$env:GOODQ_DATA_ROOT = "<path_to_data_root>"  # optional
$env:GOODQ_WSL_USER = "your_user"      # optional
$env:GOODQ_WSL_WORKSPACE = "/home/your_user/goodq4all"  # optional
$env:GOODQ_WSL_DISTRO = "Ubuntu"       # optional
```

## Strict Mode (Optional)

```powershell
$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

Enable strict flags only when that capability must exist for the run.

## Validation

Run the same Phase A smoke matrix as desktop:

```powershell
python scripts/smoke_phase_a.py
```

Logs are written to `logs/bootstrap_smoke/`.
