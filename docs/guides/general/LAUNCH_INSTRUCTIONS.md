<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-19 -->

# GoodQ4All Launch Instructions

This is the current launch/control runbook for the Windows host.

## 1. Standalone Setup Installer Flow (Recommended)

If you installed GoodQ4All via the packaged Setup Installer (`GoodQ4All_Setup_2.4.0.exe`):

* **Launch**: Double-click the **GoodQ4All** Desktop or Start Menu shortcut.
* **What happens**: This runs the native supervisor launcher (`LAUNCH_GOODQ.exe`). It verifies model signatures, starts the local Qdrant database, spins up the background API and Watchdog services, and automatically opens your browser to the **Retro Memory Explorer** UI (served at `http://127.0.0.1:30000/ui/retro_console_v1/`).
* **Ingestion**: Use the **Upload Pad** directly in the UI header to drop files and start ingestion immediately. No command line is needed.

---

## 2. Developer Source & CLI Flow (Alternative Route)

For developers and advanced operators running from the source code repository:

### Current Launch Model

- `LAUNCH_GOODQ.ps1` is the canonical Windows launcher script for the source code environment.
- `LAUNCH_GOODQ.bat` is a batch wrapper around `LAUNCH_GOODQ.ps1`.
- The launcher script is safe by default: it performs readiness checks, binds canonical runtime paths, checks Qdrant, and opens the live log monitor.
- The launcher script does **not** start the API server or watchdog automatically.
- Ingestion starts only when `-StartIngestion` is explicitly passed.

### Recommended CLI Flows

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

- The Standalone Setup Installer flow (`LAUNCH_GOODQ.exe`) automatically launches the browser to serve the **Retro Memory Explorer** (and Classic Operator Console).
- The Developer Source CLI flow (`LAUNCH_GOODQ.ps1`) does not launch a browser by default; operators must navigate to `http://127.0.0.1:30000/ui/retro_console_v1/` manually after starting the API server.

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
