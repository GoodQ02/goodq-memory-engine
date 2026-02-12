<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Bootstrap Phase A Runtime Smoke Matrix

## Purpose

This document defines a reproducible smoke matrix for Bootstrap Phase A semantics:

- Profile resolution (`UNSET`, `BASELINE`, `GPU_ENHANCED`)
- Path abstraction (`GOODQ_DATA_ROOT`)
- GPU/WSL auto-toggle behavior by profile
- CPU-safe fallback behavior in `BASELINE`
- Strict fail-fast flag behavior (`GOODQ_REQUIRE_GPU`, `GOODQ_REQUIRE_WSL_AUDIO`)

The companion runner is `scripts/smoke_phase_a.py`.

## Scope And Constraints

- No runtime code changes.
- No configuration default changes.
- No dependency installation.
- Uses current repository state only.
- Dry boot only (no full ingestion run).

## Profiles Under Test

- `UNSET`: legacy canonical behavior (`GOODQ_HOST_PROFILE` not set)
- `BASELINE`: CPU-safe mode
- `GPU_ENHANCED`: throughput mode

## Test Categories

1. Profile Semantics
- `profile_resolution`
- `profile_flags` (`is_baseline`, `is_gpu_enhanced`)
- `gpu_auto_toggle`
- `wsl_auto_toggle`

2. Path Abstraction
- `path_resolution_default_root`
- `path_resolution_env_override` (`GOODQ_DATA_ROOT=X:/BOOTSTRAP_SMOKE`)

3. Device Resolution And Fallback
- `wsl_gpu_profile_resolution` via `resolve_wsl_gpu_config(...)`
- `goodq_no_auto_gpu_state`
- `cpu_fallback_device_selection`

4. Strict Fail-Fast Validation
- `strict_flag_goodq_require_gpu`
- `strict_flag_goodq_require_wsl_audio`

5. Dry Boot Health
- `dry_boot_probe` (module import and probe status)

## Profile-Specific Expectations

### UNSET

- `profile=UNSET`
- `is_baseline=False`, `is_gpu_enhanced=False`
- `gpu_auto_config_enabled=True`
- `wsl_audio_auto_enabled=True`
- WSL GPU config remains CUDA-first defaults:
  - `device=cuda`
  - `compute_type=float16`
  - `mixed_precision=True`
- `GOODQ_NO_AUTO_GPU` is not profile-forced to `1`

### BASELINE

- `profile=BASELINE`
- `is_baseline=True`, `is_gpu_enhanced=False`
- `gpu_auto_config_enabled=False`
- `wsl_audio_auto_enabled=False`
- WSL GPU config is forced CPU-safe by default:
  - `device=cpu`
  - `compute_type=int8`
  - `mixed_precision=False`
- `GOODQ_NO_AUTO_GPU` is forced to `1` during GPU module import
- GPU module device resolves to CPU fallback by default

### GPU_ENHANCED

- `profile=GPU_ENHANCED`
- `is_baseline=False`, `is_gpu_enhanced=True`
- `gpu_auto_config_enabled=True`
- `wsl_audio_auto_enabled=True`
- WSL GPU config remains CUDA-first defaults:
  - `device=cuda`
  - `compute_type=float16`
  - `mixed_precision=True`
- `GOODQ_NO_AUTO_GPU` is not profile-forced to `1`

## Fail-Fast Flag Validation Cases

### GOODQ_REQUIRE_GPU=1

- `BASELINE`: must fail fast with explicit profile conflict (`GOODQ_NO_AUTO_GPU=1`).
- `UNSET` and `GPU_ENHANCED`:
  - If GPU is available: strict check may pass.
  - If GPU is unavailable: must fail fast with explicit GPU requirement error.

### GOODQ_REQUIRE_WSL_AUDIO=1

- `BASELINE`: must fail fast because WSL audio auto path is disabled by profile.
- `UNSET` and `GPU_ENHANCED`:
  - If WSL path is available and succeeds: pass.
  - Otherwise: must fail fast with explicit `GOODQ_REQUIRE_WSL_AUDIO=1` error.

## Pass/Fail Criteria

- **Pass**: actual outcome matches expected behavior for the profile and test case.
- **Fail**: mismatch, missing probe output, or implicit fallback where fail-fast is expected.
- **Overall pass**: all matrix rows pass.

## Execution

From repository root:

```powershell
python scripts/smoke_phase_a.py
```

Artifacts are written to:

- `logs/bootstrap_smoke/<timestamp>/smoke_matrix_results.json`
- `logs/bootstrap_smoke/<timestamp>/smoke_matrix_results.md`
- `logs/bootstrap_smoke/<timestamp>/smoke_matrix_console.txt`

## Expected Structured Output Example (JSON)

```json
{
  "run_timestamp": "20260212_220000",
  "totals": {
    "test_count": 36,
    "passed": 36,
    "failed": 0
  },
  "rows": [
    {
      "test_case": "profile_resolution",
      "profile": "BASELINE",
      "expected_result": "profile=BASELINE",
      "actual_result": "profile=BASELINE",
      "pass": true
    }
  ]
}
```

## Expected Summary Table Example

| Test Case | Profile | Expected Result | Actual Result | Pass/Fail |
| --- | --- | --- | --- | --- |
| profile_resolution | UNSET | profile=UNSET | profile=UNSET | PASS |
| wsl_gpu_profile_resolution | BASELINE | device=cpu, compute_type=int8, mixed_precision=False | device=cpu, compute_type=int8, mixed_precision=False | PASS |
| strict_flag_goodq_require_gpu | BASELINE | Fail-fast with explicit baseline/GOODQ_NO_AUTO_GPU conflict | status=error; error=GOODQ_REQUIRE_GPU=1 but GPU auto-config is disabled (GOODQ_NO_AUTO_GPU=1) | PASS |

## Final Summary Table Template

Populate from `smoke_matrix_results.md`:

| Test Case | Profile | Expected Result | Actual Result | Pass/Fail |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |

