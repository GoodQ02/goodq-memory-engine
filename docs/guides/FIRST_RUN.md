<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

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

## Before You Start

Supported first-run host: Windows 11 with PowerShell.

Have these available before running the installer:

- Git
- Miniconda or Anaconda visible to the shell
- Python 3.10 or newer
- at least 25 GB free for the baseline path (breakdown: ~4 GB conda environments, ~12 GB model cache prefetch, ~6 GB processing workspace, ~3 GB database storage; space required is lower if model prefetch is skipped)
- optional: NVIDIA GPU and WSL2 Ubuntu for accelerated lanes

macOS and Linux are not supported first-run hosts for this repository today.
Use [`docs/reference/PLATFORM_SUPPORT.md`](../reference/PLATFORM_SUPPORT.md) for
the current platform contract.

> [!TIP]
> **Start with video or audio:** For the cleanest first success loop, use a small video (`.mp4`) or audio (`.mp3`/`.wav`) file. Text extraction from documents (`.pdf`, `.doc`, `.docx`) requires additional local extraction utilities (like Poppler) or desktop office tools.

## Mental Model

- `LAUNCH_GOODQ.ps1` checks readiness and opens operator monitors.
- Watchdog watches the configured `import_inbox`.
- `cli.run_ingestion` owns actual ingestion.
- The API is a local read and inspection surface.
- The operator console is a read-only cockpit over the API and persisted
  artifacts.
- Runtime artifacts are the durable proof.

GoodQ4All does not currently ship a polished consumer memory browser. The
supported first-run surface is CLI plus Watchdog plus API docs, the read-only
operator console, and persisted artifacts.

## 1. Bootstrap

*(Expect roughly 10–30 minutes on first install, depending on network speed and whether model prefetching is enabled)*

Open PowerShell in the repo root:

```powershell
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
```

If you want a CPU-safe installer pass without GPU, WSL audio, or model prefetch:

```powershell
python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio --skip-model-prefetch
```

Expected result:

- bootstrap completes without blocking errors
- validation reports pass, possibly with documented warnings for optional
  components

During an interactive run, the installer may ask for:

- the base data root directory
- whether to enable GPU acceleration
- whether to enable WSL audio acceleration
- whether to install the supported step environment pack
- whether to prefetch local model caches
- Conda Terms of Service acceptance when Conda requires it
- FFmpeg and Qdrant service installation or repair when missing

For local secrets or provider settings, copy `.env.local.template` to
`.env.local` and edit `.env.local` only. `.env.template` is a broad environment
contract reference, not the first file new users should edit.

## 2. Check Readiness

Run the safe launcher first:

```powershell

## 2. Check Readiness

Run the safe launcher first:

```powershell
.\LAUNCH_GOODQ.ps1
```

This does not start ingestion. It checks configuration, Qdrant, runtime paths,
and logs. Ingestion starts only when explicitly requested.

## 3. Start Watchdog

In a terminal you can leave open:

> [!IMPORTANT]
> **Leave this terminal open.** Watchdog must remain running in the background to monitor the inbox.

```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```

Watchdog watches:

```text
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

`GOODQ_DATA_ROOT` is the base root selected by bootstrap or `.env.local`. The
runtime derives `GoodQ_Data` beneath it, so the first-run drop zone is always
the path shape shown above.
If bootstrap reports a selected data root that already ends in `GoodQ_Data`,
use that folder directly; do not append a second `GoodQ_Data` segment.

## 4. Drop One File

Copy one small local media file into the inbox:

```powershell
Copy-Item .\path\to\sample.mp4 <GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

Use a short file for the first run. Larger videos are normal later, but the
first success loop should be easy to inspect.

PDF ingestion requires Poppler / `pdftotext`. `.doc` and `.docx` extraction
depends on the local document extraction tools available on the host, so use a
small video, audio, image, text, or known-supported PDF file for the cleanest
first run.

## 5. Start The API

In another terminal:

> [!IMPORTANT]
> **Open a second, separate terminal window/session.** Do not close the Watchdog terminal. Run the API server here.

```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`
- `http://127.0.0.1:30000/ui/operator_console_v1/`

These default to `GOODQ_API_HOST=127.0.0.1` and `GOODQ_API_PORT=30000`. Override
them in `.env.local` only when you intentionally change the local API binding.

## 6. Confirm Success

For a successful first run, expect:


## 6. Confirm Success

For a successful first run, expect:

- the file leaves `import_inbox`
- the file appears under `processed` or the run output clearly explains why it
  did not
- the latest processing workspace contains `scene_ingest_results.json`
- scene outputs include `scene_manifest.json`
- scene outputs include `temporal_index.json`
- API health remains reachable

### Successful Manifest Example

A successful scene-level ingestion produces a `scene_manifest.json` structured like this:

```json
{
  "video_id": "7215a98e...",
  "video_path": "C:\\Users\\username\\GoodQ_Data\\import_inbox\\sample.mp4",
  "phase6_status": "complete",
  "phase6_complete": true,
  "scenes": [
    {
      "scene_id": "7fde117a...",
      "index": 0,
      "start": 0.0,
      "end": 4.17,
      "duration": 4.17,
      "qdrant_ok": true,
      "speaker_ids": ["SPEAKER_00"]
    }
  ]
}
```

Optional enrichments can fail on individual scenes without invalidating the
entire run. Treat the manifest, temporal index, step logs, and API health as
the first truth surfaces.

If you skipped Qdrant service installation during bootstrap, the launcher health check will display:
```text
  [!] Qdrant: Not responding
      Attempting to start Qdrant service...
  [!!] Qdrant: Failed to start - manual intervention required
```
- **When is it safe to ignore?** During your first install verify or when running purely CPU-safe dry runs where vector index lookups are not required.
- **When must it be fixed?** Before running active ingestion (`-StartIngestion` or Watchdog importing files) that updates vector stores, or when executing retrieval queries. Fix it by running:
  ```powershell
  .\scripts\qdrant\INSTALL_QDRANT_SERVICE.bat
  ```
  (Requires Administrator shell).

## After First Success

- For install details, read [`docs/guides/install/INSTALL.md`](install/INSTALL.md).
- For the shorter setup path, read [`docs/guides/install/QUICKSTART.md`](install/QUICKSTART.md).
- For file-watcher operations, read [`docs/guides/watchdog/WATCHDOG_QUICKREF.md`](watchdog/WATCHDOG_QUICKREF.md).
- For local API routes, read [`docs/reference/API.md`](../reference/API.md).
- For architecture, read [`docs/architecture/README.md`](../architecture/README.md).
