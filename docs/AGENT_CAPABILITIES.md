# GoodQ4All Agent Capabilities

This document defines practical boundaries for repo-scoped agents. It complements `docs/AGENTS.md`.

## Verified Runtime Entry Points (Discovered)

### Generated: Verified runtime entry points (static analysis snapshot)

This list is derived from static analysis of the repository (launch scripts + Python `__main__` guards). It is a snapshot, not a claim that any given component is enabled or complete.

- System launcher (Windows): `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat`
- Ingestion pipeline CLI: `cli/run_ingestion.py` (typically invoked via `python -m cli.run_ingestion ...`)
- Watchdog CLI: `cli/watchdog.py` (typically invoked via `python -m cli.watchdog ...`)
- API launchers: `scripts/start_api.ps1`, `api/server.py` (server wrapper for the FastAPI app)
- WSL2 audio services: `wsl2_audio/start_wsl2_service.bat`, `wsl2_audio/audio_service.py`, `wsl2_audio/process_audio.py`
- Control agents: `agents/control_agent.py`, `agents/config_healer.py`, `agents/self_healing_monitor.py`
- LLM server launchers: `scripts/start_vllm_servers.bat`, `scripts/start_llm_servers.bat`, `scripts/wsl/start_all_vllm.sh`

### Human-authored: How agents must rediscover runtime entry points (static analysis)

Agents must re-derive the entry-point list from the repo itself before making changes that could affect runtime behavior.

1. Start with launch surfaces: scan `*.ps1`, `*.bat`, and `*.sh` for `python`, `uvicorn`, `conda run`, and `wsl` invocations that start long-running services.
2. Enumerate Python entry points: scan for `if __name__ == "__main__"` / `if __name__ == '__main__'` and nearby `main()`/CLI wiring (argparse/typer/click/etc.).
3. Map indirection: if a launcher calls another file/module (e.g., a PowerShell script calling a Python wrapper), include both the launcher and the ultimate Python entry module.
4. Treat docs as hints only: a command shown in docs is not proof; confirm the referenced module/file exists and contains a real CLI/server startup path.
5. Lock scope before editing: unless explicitly instructed, agents must not modify files outside the discovered runtime entry points list above. If a change requires touching other files, pause and request explicit instruction (ideally with an explicit file allowlist).
Agents must treat documented audit resolutions as authoritative and must not reopen deferred items without explicit approval.
