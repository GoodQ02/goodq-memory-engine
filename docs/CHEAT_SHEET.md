<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All Cheat Sheet

Current command-first quick reference for the supported runtime surface.

## Bootstrap

```powershell
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
```

## Launch and Control

```powershell
# Safe launcher: health checks + path binding + live log monitor
.\LAUNCH_GOODQ.ps1

# Start ingestion intentionally
.\LAUNCH_GOODQ.ps1 -StartIngestion

# Start API explicitly
python -m api.server
# or
pwsh .\scripts\start_api.ps1

# Start watchdog explicitly
conda run -n goodq_core python -m cli.watchdog

# One-time watchdog status
python .\scripts\utils\check_watchdog_status.py
```

## Manual Ingestion

```powershell
conda run -n goodq_core python -m cli.run_ingestion --input-dir <path>
```

## Health Checks

```powershell
python scripts/system_readiness_check.py
python scripts/cache_readiness_check.py
python scripts/docs/doc_drift_lint.py
python -m pytest -q
```

## API Endpoints

Only valid when the API process is running:

- Root JSON: `http://127.0.0.1:30000/`
- OpenAPI docs: `http://127.0.0.1:30000/docs`
- Health summary: `http://127.0.0.1:30000/api/health/summary`
- Status: `http://127.0.0.1:30000/api/status`

## Key Paths

- Inbox: `<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\`
- Processing: `<GOODQ_DATA_ROOT>\GoodQ_Data\epochs\<epoch>\processing\`
- Logs: `<GOODQ_DATA_ROOT>\GoodQ_Data\logs\`

## Important Note

GoodQ4All does not currently ship a supported production UI. Use the API docs,
CLI, watchdog, manifests, and logs as the supported operational surface.

## Related Docs

- Launch:
  [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](guides/general/LAUNCH_INSTRUCTIONS.md)
- API:
  [`docs/reference/API.md`](reference/API.md)
- Quick index:
  [`docs/reference/indexes/QUICK_INDEX.md`](reference/indexes/QUICK_INDEX.md)
