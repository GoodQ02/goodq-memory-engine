<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

# First Run

Use this guide to verify that GoodQ4All can turn a local media file into persisted scene memory on your Windows 11 machine.

---

## Mental Model

GoodQ4All runs as a set of coordinated local services:
1. **Database Service**: Qdrant running locally to index vector embeddings.
2. **API & Engine Process**: A FastAPI backend performing scene perception, audio transcription, speaker diarization, and Phase 6 memory harmonization.
3. **Control Plane**: The Control Agent supervising execution and generating health reports.
4. **Visual Cockpit**: The **Retro Memory Explorer** (and Classic Operator Console), served locally to let you browse your media, view transcripts, and inspect the knowledge graph.

---

## Method A: Installer Onboarding (Recommended)

If you are running the packaged release of GoodQ4All, this is the quickest and easiest way to verify the system.

### 1. Launch the Application
Double-click the **GoodQ4All** shortcut on your Desktop or Start Menu.
* **What happens behind the scenes**: This executes [LAUNCH_GOODQ.exe](file:///C:/Program%20Files/GoodQ4All/LAUNCH_GOODQ.exe) which performs native VC++ checks, verifies the model manifest signature, launches Qdrant, starts the Python API/Control processes, and automatically launches your browser.
* **Expected Result**: Your default web browser will open automatically to the **Retro Memory Explorer** served at:
  ```text
  http://127.0.0.1:30000/ui/retro_console_v1/?token=<secure_session_token>
  ```

### 2. Ingest a Media File
Once the Retro Memory Explorer UI loads, locate the **Upload Pad** in the header. Drag-and-drop a small audio (`.mp3`/`.wav`) or video (`.mp4`) file directly onto the yellow-dotted helipad area (or click to browse your computer).
* **What happens behind the scenes**: The UI streams the file directly to the local sandbox import inbox drop zone, triggering the watchdog ingestion sequence automatically.

### 3. Observe Ingestion
The background watchdog service detects the uploaded file and starts processing immediately. You can:
* Inspect real-time status/logs in the UI, or check the **Classic Operator Console** served at `http://127.0.0.1:30000/ui/operator_console_v1/`.
* Watch the **Retro Memory Explorer** automatically update its timeline checklist, co-occurrence graph, and keyframe inspector once ingestion completes.

---

## Method B: Developer Source Onboarding (Advanced)

If you are developing or running GoodQ4All directly from the source repository:

### Prerequisites
* Windows 11 with PowerShell
* Git
* Miniconda or Anaconda visible to the shell
* Python 3.10 or newer
* At least 25 GB free disk space (baseline path with model prefetch)

### 1. Bootstrap the Environment
Open PowerShell in your cloned repository root:
```powershell
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
```
*(If you want a CPU-safe run without GPU or model prefetch: `python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio --skip-model-prefetch`)*

### 2. Check Readiness
Run the PowerShell launcher script:
```powershell
.\LAUNCH_GOODQ.ps1
```
This performs a dry-run check of Conda, Qdrant, environment configurations, and writes the `GOODQ_DATA_ROOT` parameters.

### 3. Start Watchdog
Open a PowerShell window, ensure you are in the project root, and start the Watchdog:
```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```
*Leave this terminal open. It monitors the inbox drop zone:*
```text
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

### 4. Start the API Server
Open a second PowerShell window, change to the project root, and run the API:
```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```
*Leave this terminal open as well. It serves the UI consoles.*

### 5. Drop a Media File
Copy a small media file into:
```text
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

### 6. Open UI Dashboard
Open your web browser and navigate to:
* **Retro Memory Explorer**: `http://127.0.0.1:30000/ui/retro_console_v1/`
* **Classic Operator Console**: `http://127.0.0.1:30000/ui/operator_console_v1/`

---

## 3. Confirming Success

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
  "video_path": "<USERPROFILE>\\GoodQ_Data\\import_inbox\\sample.mp4",
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
