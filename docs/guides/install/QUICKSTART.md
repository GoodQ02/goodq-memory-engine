<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# GoodQ4All Quickstart (Canonical)

## 1. Select Profile

```powershell
# Legacy canonical behavior
Remove-Item Env:GOODQ_HOST_PROFILE -ErrorAction SilentlyContinue

# or CPU-safe baseline
$env:GOODQ_HOST_PROFILE = "BASELINE"

# or throughput mode
$env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"
```

## 2. Optional Overrides

```powershell
$env:GOODQ_DATA_ROOT = "D:/GoodQData"   # optional
$env:GOODQ_WSL_USER = "jdben"           # optional
$env:GOODQ_WSL_WORKSPACE = "/home/jdben/goodq4all"  # optional
$env:GOODQ_WSL_DISTRO = "Ubuntu"        # optional
```

## 3. Optional Strict Requirements

```powershell
$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

## 4. Verify Bootstrap Semantics

```powershell
python scripts/smoke_phase_a.py
```

Expected logs and report outputs:

- `logs/bootstrap_smoke/`
- `docs/bootstrap/smoke_matrix_phase_a.md` (expectation matrix)

## 5. Run Ingestion

Use your standard launcher/run entrypoint after smoke passes.
