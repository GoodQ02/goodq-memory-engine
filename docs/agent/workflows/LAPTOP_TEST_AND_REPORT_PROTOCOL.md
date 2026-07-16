<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Laptop Setup Test & Report Protocol

This document defines the operational protocol for the agent executing on the target Windows 11 laptop (`GOOD-SPEED-32` / `GOOD-SPEED-16` / `GOOD-RECON-16`) to install, verify, and document the offline sandboxed ingestion system.

---

## Mission
Run a clean install of the v2.5.7 setup executable, verify that the offline model packages are successfully auto-detected and extracted, run an E2E video ingestion test with fallback CPU-based speech transcription, and write a verification report back to the OneDrive package folder.

---

## Execution Steps

### Step 1: Pre-install Clean State
Before running the installer, ensure all old services and processes are terminated:
1. Stop the supervising launcher if active (close `LAUNCH_GOODQ.exe` console).
2. Open PowerShell and force-kill any orphan backend processes:
   ```powershell
   Stop-Process -Name "qdrant" -Force -ErrorAction SilentlyContinue
   Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
   ```

### Step 2: Run the Installer (Offline Pack Mode)
Locate the synced setup executable in the OneDrive directory:
*   Path: `%USERPROFILE%\OneDrive\One_Domingo\test_v2.5.7_package\GoodQ4All_Setup_2.5.7.exe`

Execute the installer. To test a clean offline installation, you can run a silent install which defaults to wiping historic user databases:
```powershell
Start-Process -FilePath "$env:USERPROFILE\OneDrive\One_Domingo\test_v2.5.7_package\GoodQ4All_Setup_2.5.7.exe" -ArgumentList "/S" -Wait
```
*Note: Verify that the setup installer auto-detects and extracts the `.zip` packages or chunk files present in the OneDrive folder without showing warning boxes.*

### Step 3: Verify Offline Model Staging
Inspect the model packs verification ledger inside the ProgramData directory:
*   File: `%PROGRAMDATA%\GoodQ4All\.model_packs_installed.json`

Confirm that the following packages are registered with `"status": "verified"`:
- `core_memory`
- `vision_pack`
- `audio_standard`

Verify that the model hub directories exist under `%PROGRAMDATA%\GoodQ4All\models\hub\`.

### Step 4: Boot and Run Ingestion Smoke Test
1. Launch the application supervisor:
   ```powershell
   Start-Process -FilePath "$env:ProgramFiles\GoodQ4All\LAUNCH_GOODQ.exe"
   ```
2. Verify that Qdrant (port 6333) and the API server (port 30000) bind cleanly.
3. Copy the testing video to the import inbox:
   *   Source: `%USERPROFILE%\OneDrive\One_Domingo\test_v2.5.7_package\GOODQ4ALL_DEMO_FINAL (1).mp4`
   *   Destination: `%PROGRAMDATA%\GoodQ4All\GoodQ_Data\import_inbox\GOODQ4ALL_DEMO_FINAL (1).mp4`
4. Monitor the watchdog log file `%PROGRAMDATA%\GoodQ4All\GoodQ_Data\epochs\epoch_2025_12_22\logs\watchdog.log` (or `watchdog_startup.log` copied to OneDrive) for completion.

### Step 5: Verify Transcription Performance
Open the latest run log and search for the `[TRANSCRIBE]` and `[AUDIO]` segments. Verify:
1. No `ModuleNotFoundError` for `faster_whisper` is thrown.
2. The log contains `[TRANSCRIBE] Starting on CPU` followed by successful segment extraction and transcript writing.

---

## Reporting Results
After verifying ingestion, compile a verification summary report and save it to the OneDrive package folder:

*   Output Path: `%USERPROFILE%\OneDrive\One_Domingo\test_v2.5.7_package\success_07.txt`

The report must contain:
1. A **Status** heading confirming that the installer completed and transcription succeeded.
2. The exact hostname (`GOOD-SPEED-32`, `GOOD-SPEED-16`, or `GOOD-RECON-16`) and local time of the run.
3. The count of database embeddings in the SQLite store (`%PROGRAMDATA%\GoodQ4All\GoodQ_Data\epochs\epoch_2025_12_22\memory.db`) verifying that visual and audio features were written.
4. Raw log snippets from the successful `faster_whisper` transcription block.
