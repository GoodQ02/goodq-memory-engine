# vLLM WSL Reference Package

## Status

This directory is a historical reference package for an older direct-start WSL vLLM toolkit.

The tracked direct-start scripts under `vllm_wsl/scripts/` have been retired from the repository because they no longer matched the supported operator path.

## Current Operator Path

Use the current systemd-backed flow instead:
- `scripts/wsl/install_vllm_service.sh`
- `scripts/start_vllm_servers.bat`
- `scripts/status_vllm_servers.bat`
- `docs/guides/llm/VLLM_SYSTEMD_SETUP.md`

## What Remains Here

The remaining files in `vllm_wsl/` are kept as historical reports, notes, and reference configuration artifacts from the earlier WSL bring-up phase.

They should not be treated as the canonical runtime contract.
