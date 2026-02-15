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
| `scripts/vllm_control.bat` | Active utility | Manual control wrapper for local vLLM services on Windows. |
| `scripts/wsl/install_audio_service.sh` | Active utility | Installs and configures WSL audio service components. |
| `scripts/wsl/smoke_wsl_memory.sh` | Active utility | WSL smoke probe for memory/runtime readiness. |
| `scripts/test_all_endpoints.py` | Active validation | Quick endpoint availability validation across configured services. |
| `scripts/archive/migrations/CRITICAL_EMOJI_PURGE.py` | Historical | One-time emoji purge migration tool from early stabilization work. |
| `scripts/archive/migrations/Fix-SystemPaths.ps1` | Historical | One-time host PATH repair helper for legacy workstation setup. |
| `scripts/archive/migrations/migrate_data_paths.ps1` | Historical | One-time migration of legacy data roots to canonical data location. |

## Archive Rule

If a script is one-time, host-specific, or migration-only, place it under `scripts/archive/` and classify it here as `Historical`.
