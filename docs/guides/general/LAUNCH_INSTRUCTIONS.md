<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All Launch Instructions

This is the current launch/control runbook for the Windows host.

## Current Launch Model

- `LAUNCH_GOODQ.ps1` is the canonical Windows launcher.
- `LAUNCH_GOODQ.bat` is a batch wrapper around `LAUNCH_GOODQ.ps1`.
- The launcher is safe by default: it performs readiness checks, binds
  canonical runtime paths, checks Qdrant, and opens the live log monitor.
- The launcher does **not** start the API server or watchdog automatically.
- Ingestion starts only when `-StartIngestion` is explicitly passed.

## Recommended Flows

### 1. Readiness / Safe Launch

```powershell
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
```

Use this when you want health checks, current path bindings, and the live log
window without starting ingestion.

### 2. Start Ingestion Intentionally

```powershell
.\LAUNCH_GOODQ.ps1 -StartIngestion
```

Optional:

```powershell
.\LAUNCH_GOODQ.ps1 -StartIngestion -ForceReprocess
```

### 3. Start the API Explicitly

```powershell
python -m api.server
```

Windows helper:

```powershell
pwsh .\scripts\start_api.ps1
```

Use the API docs only after the API process is running:

- `http://127.0.0.1:30000/docs`

### 4. Start Watchdog Explicitly

```powershell
conda run -n goodq_core python -m cli.watchdog
```

One-time status snapshot:

```powershell
python .\scripts\utils\check_watchdog_status.py
```

## What To Verify

- `LAUNCH_GOODQ.ps1` reports healthy config and Qdrant readiness.
- The live log monitor opens in a separate window.
- If you started ingestion, an ingestion monitor window opens.
- If you started the API, `GET /` returns JSON and `/docs` loads.
- If you started watchdog, `check_watchdog_status.py` reports it as running.

## Truth Boundary

- No supported browser UI is currently launched from this flow.
- Historical dashboard, scene explorer, and chat-interface rollout notes were
  part of an earlier scaffold and are not current operator guidance.

## Related Docs

- Install:
  [`docs/guides/install/INSTALL.md`](../install/INSTALL.md)
- Quickstart:
  [`docs/guides/install/QUICKSTART.md`](../install/QUICKSTART.md)
- API reference:
  [`docs/reference/API.md`](../../reference/API.md)
- UI status:
  [`docs/guides/ui/JUSTIFICATION_UI.md`](../ui/JUSTIFICATION_UI.md)
- Watchdog:
  [`docs/guides/watchdog/WATCHDOG_INDEX.md`](../watchdog/WATCHDOG_INDEX.md)
