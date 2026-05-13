# Scripts Registry

This file classifies scripts that were previously ambiguous in audits so they are not deleted or moved accidentally.

## Canonical Runtime Script

- `wsl2_audio/test_pipeline.py` is canonical.
- Documentation must not duplicate the full script body.

## Status Table

| Script | Status | Purpose |
| --- | --- | --- |
| `scripts/generate_system_snapshot.py` | Active utility | Generates system snapshot docs from current runtime state. |
| `scripts/generate_goodq4all_agent_status.py` | Active utility | Regenerates agent status documentation artifacts. |
| `scripts/health/pull_health_export.py` | Active utility | Pulls and normalizes health export data for reporting. |
| `scripts/dev/run_pytest.ps1` | Active developer utility | Runs pytest through the canonical `goodq_core` conda environment with repo-local temp isolation to avoid shared Windows TEMP contention. |
| `scripts/vllm_control.bat` | Active utility | Manual control wrapper for local vLLM services on Windows. |
| `scripts/wsl/install_audio_service.sh` | Active utility | Installs and configures WSL audio service components. |
| `scripts/wsl/smoke_wsl_memory.sh` | Active utility | WSL smoke probe for memory/runtime readiness. |
| `scripts/test_all_endpoints.py` | Active validation | Quick endpoint availability validation across configured services. |

## Archive Rule

One-time, host-specific, or migration-only scripts are not part of the public
branch. Keep public scripts limited to supported runtime, bootstrap, diagnostic,
and developer utilities. Preserve private historical scripts on the development
line only when they still have forensic value.
