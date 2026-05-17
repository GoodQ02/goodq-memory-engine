<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# GoodQ4All Quickstart

Use this when you need the shortest clean path from clone to launch on Windows.
If this is your first time with the repo, run the full first-success loop in
[`docs/guides/FIRST_RUN.md`](../FIRST_RUN.md) after bootstrap validation.

Supported quickstart host: Windows 11 with Git, Conda, Python 3.10+, and enough
local disk space for the selected install path.

## 1. Clone and Open the Repo

```powershell
git clone <repo_url>
cd goodq4all
```

## 2. Run Bootstrap

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
.\LAUNCH_GOODQ.ps1
```

The launcher is safe by default. It checks readiness and opens operator
monitors; it does not start ingestion unless you explicitly request it.

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
