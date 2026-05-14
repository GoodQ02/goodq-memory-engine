<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-09 -->

# First Run

Use this path when you want to prove GoodQ4All can turn one local media file
into persisted scene memory.

This guide is intentionally short. It is for the first success loop, not for
architecture, release proof, or broad tuning.

## What You Will Prove

- The repo can bootstrap on a Windows 11 host.
- The local runtime can validate itself.
- Watchdog can see one file in the configured inbox.
- Ingestion can create scene memory.
- The API can expose local inspection routes.

## Mental Model

- `LAUNCH_GOODQ.ps1` checks readiness and opens operator monitors.
- Watchdog watches the configured `import_inbox`.
- `cli.run_ingestion` owns actual ingestion.
- The API is a local read and inspection surface.
- Runtime artifacts are the durable proof.

GoodQ4All does not currently ship a polished production UI. The supported first
run surface is CLI plus Watchdog plus API docs plus persisted artifacts.

## 1. Bootstrap

Open PowerShell in the repo root:

```powershell
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
```

Expected result:

- bootstrap completes without blocking errors
- validation reports pass, possibly with documented warnings for optional
  components

## 2. Check Readiness

Run the safe launcher first:

```powershell
.\LAUNCH_GOODQ.ps1
```

This does not start ingestion. It checks configuration, Qdrant, runtime paths,
and logs. Ingestion starts only when explicitly requested.

## 3. Start Watchdog

In a terminal you can leave open:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```

Watchdog watches:

```text
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

## 4. Drop One File

Copy one small local media file into the inbox:

```powershell
Copy-Item .\path\to\sample.mp4 <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

Use a short file for the first run. Larger videos are normal later, but the
first success loop should be easy to inspect.

## 5. Start The API

In another terminal:

```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`

## 6. Confirm Success

For a successful first run, expect:

- the file leaves `import_inbox`
- the file appears under `processed` or the run output clearly explains why it
  did not
- the latest processing workspace contains `scene_ingest_results.json`
- scene outputs include `scene_manifest.json`
- scene outputs include `temporal_index.json`
- API health remains reachable

Optional enrichments can fail on individual scenes without invalidating the
entire run. Treat the manifest, temporal index, step logs, and API health as
the first truth surfaces.

If `pdftotext` / Poppler is missing, PDF ingestion is not ready yet. Video,
audio, image, and text first-run checks can still proceed; install Poppler and
set `GOODQ_POPPLER_BIN` or put `pdftotext` on `PATH` before testing PDFs.

## After First Success

- For install details, read [`docs/guides/install/INSTALL.md`](install/INSTALL.md).
- For the shorter setup path, read [`docs/guides/install/QUICKSTART.md`](install/QUICKSTART.md).
- For file-watcher operations, read [`docs/guides/watchdog/WATCHDOG_QUICKREF.md`](watchdog/WATCHDOG_QUICKREF.md).
- For local API routes, read [`docs/reference/API.md`](../reference/API.md).
- For architecture, read [`docs/architecture/README.md`](../architecture/README.md).
