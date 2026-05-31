<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# GoodQ4All Quickstart

This guide gets you up and running as quickly as possible on Windows 11.

## Method A: Packaged Setup Installer (Recommended)
Use this if you want the easiest, self-contained standalone installation.

<p align="left">
  <a href="https://github.com/GoodQ02/goodq4all/releases/download/v1.0.0/GoodQ4All_Setup_1.0.0.exe" style="display: inline-block; padding: 12px 24px; background-color: #ffb300; color: #110d1a; font-weight: bold; text-decoration: none; border-radius: 4px; box-shadow: 0 4px 10px rgba(255, 179, 0, 0.3); transition: all 0.2s ease; margin: 10px 0;">
    🚀 Download GoodQ4All Setup v1.0.0.exe
  </a>
</p>

> [!IMPORTANT]
> **Zero-Dependency Offline Architecture**
>
> GoodQ4All is a **100% local, zero-dependency, private offline alternative** to major cloud-based media intelligence services. By packaging the isolated Python runtime, Qdrant database, and perception libraries into a single sandboxed executable, we have made private video search and knowledge graph memory as easy to install as any desktop application. No cloud dependencies, no subscription fees, and no data leaks.

1. **Install**: Run `GoodQ4All_Setup_1.0.0.exe` and complete the installation wizard.
2. **Launch**: Double-click the **GoodQ4All** Desktop or Start Menu shortcut to run the supervisor launcher (`LAUNCH_GOODQ.exe`). This automatically boots the background database/API and opens the **Retro Memory Explorer** UI.
3. **Ingest**: Open the Retro Memory Explorer UI, click the **Upload Pad** in the header, and drag-and-drop or select any media file (`.mp4`, `.mp3`) onto the yellow-dotted helipad circle to start ingestion instantly!

---

## Method B: Developer Source Setup (Advanced)
Use this if you are running or developing directly from the source repository.

### 1. Clone and Open the Repo

```powershell
git clone <repo_url>
cd goodq4all
```

## 2. Run Bootstrap

*(Expect roughly 10–30 minutes on first install, depending on network speed and whether model prefetching is enabled)*

```powershell
python scripts/bootstrap_install.py
```

This provisions `goodq_core` plus the supported specialized step-env pack from
the pinned lock recipes in `envs/locks/` for full pipeline capability.

If WSL audio is enabled, bootstrap stages the WSL audio package constraints
from `wsl2_audio/requirements-bootstrap-constraints.txt`. Avoid unpinned WSL
audio package upgrades; they can pass `pip check` while breaking diarization
runtime compatibility.

## 3. Validate and Launch

```powershell
.\scripts\bootstrap_validate.bat
# Safe-mode check (readiness only)
.\LAUNCH_GOODQ.ps1

# Launch with active background watchdog ingestion
.\LAUNCH_GOODQ.ps1 -StartIngestion
```

The launcher is safe by default. It checks readiness and opens operator
monitors; it does not start ingestion unless you explicitly request it by passing `-StartIngestion`.

## 4. Process One File

Start Watchdog in a terminal you can leave open:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```

Drop one small media file into:

```text
<GOODQ_DATA_ROOT>\GoodQ_Data\import_inbox\
```

`GOODQ_DATA_ROOT` is the base root; the runtime derives `GoodQ_Data` beneath it.

Then start the local API in another terminal:

```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```

Open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`

Expected proof: the file leaves `import_inbox`, a processing workspace contains
`scene_ingest_results.json`, and scene outputs include `scene_manifest.json`
and `temporal_index.json`.

For the more guided version, use [`docs/guides/FIRST_RUN.md`](../FIRST_RUN.md).
For Watchdog details, use
[`docs/guides/watchdog/WATCHDOG_QUICKREF.md`](../watchdog/WATCHDOG_QUICKREF.md).

## 5. Optional Runtime Overrides

```powershell
$env:GOODQ_HOST_PROFILE = "BASELINE"
# or
# $env:GOODQ_HOST_PROFILE = "GPU_ENHANCED"

$env:GOODQ_REQUIRE_GPU = "1"
$env:GOODQ_REQUIRE_WSL_AUDIO = "1"
```

Use strict flags only when you want fail-fast enforcement of optional
accelerators.

## 6. Deep Validation (Optional)

```powershell
python scripts/smoke_phase_a.py
```

- Matrix: [`docs/bootstrap/smoke_matrix_phase_a.md`](../../bootstrap/smoke_matrix_phase_a.md)
- Logs: `logs/bootstrap_smoke/`

For full setup detail or manual environment control, use
[`docs/guides/install/INSTALL.md`](INSTALL.md).
