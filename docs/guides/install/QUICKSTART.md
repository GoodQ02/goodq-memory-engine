<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-19 -->

# GoodQ4All Quickstart

Use this when you need the shortest clean path from clone to launch on Windows.

## 1. Clone and Open the Repo

```powershell
git clone <repo_url>
cd goodq4all
```

## 2. Run Bootstrap

```powershell
python scripts/bootstrap_install.py
```

This provisions `goodq_core` plus the supported specialized step-env pack for
full pipeline capability.

## 3. Validate and Launch

```powershell
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
```

## 4. Optional Runtime Overrides

```powershell
$env:GOODQ_HOST_PROFILE = "BASELINE"
# or
# $env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"

$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

Use strict flags only when you want fail-fast enforcement of optional
accelerators.

## 5. Deep Validation (Optional)

```powershell
python scripts/smoke_phase_a.py
```

- Matrix: [`docs/bootstrap/smoke_matrix_phase_a.md`](../../bootstrap/smoke_matrix_phase_a.md)
- Logs: `logs/bootstrap_smoke/`

For full setup detail or manual environment control, use
[`docs/guides/install/INSTALL.md`](INSTALL.md).
