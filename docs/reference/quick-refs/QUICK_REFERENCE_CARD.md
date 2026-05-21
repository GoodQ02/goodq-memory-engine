<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# GoodQ4All Quick Reference Card

Compact operational quick reference for the current release surface.

## Entry Points

| Surface | Command | Purpose |
| --- | --- | --- |
| Safe launcher | `.\LAUNCH_GOODQ.ps1` | Health checks, runtime path binding, live log monitor |
| Intentional ingestion | `.\LAUNCH_GOODQ.ps1 -StartIngestion` | Start direct ingestion from the configured inbox |
| API | `python -m api.server` | Start the local API explicitly |
| API helper | `pwsh .\scripts\start_api.ps1` | Windows wrapper for the local API |
| Operator console | `http://127.0.0.1:30000/ui/operator_console_v1/` | Read-only local inspection cockpit with Current Scope preflight |
| Watchdog | `conda run -n goodq_core python -m cli.watchdog` | Start inbox monitoring explicitly |
| Watchdog status | `python .\scripts\utils\check_watchdog_status.py` | One-time watchdog snapshot |

## Most Useful Checks

| Check | Command |
| --- | --- |
| Bootstrap validation | `.\scripts\bootstrap_validate.bat` |
| System readiness | `python scripts/system_readiness_check.py` |
| Cache readiness | `python scripts/cache_readiness_check.py` |
| Docs governance | `python scripts/docs/doc_drift_lint.py` |
| Test suite | `python -m pytest -q` |

## API Notes

- API root: `http://127.0.0.1:30000/`
- API docs: `http://127.0.0.1:30000/docs`
- Status: `http://127.0.0.1:30000/api/status`
- Operator console: `http://127.0.0.1:30000/ui/operator_console_v1/`
- The operator console is read-only. It does not trigger ingestion, mutate
  memory, heal configs, generate reports, or activate ControlAgent.

## Core Paths

- Inbox: `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`
- Processing: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\`
- Logs: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\logs\`
- Memory DB: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\memory.db`

## Follow-Up Docs

- Docs landing page: [`docs/README.md`](../../README.md)
- Launch runbook: [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](../../guides/general/LAUNCH_INSTRUCTIONS.md)
- API reference: [`docs/reference/API.md`](../API.md)
- UI status: [`docs/guides/ui/JUSTIFICATION_UI.md`](../../guides/ui/JUSTIFICATION_UI.md)
