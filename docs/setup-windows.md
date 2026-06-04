# Windows Environment & Path Configuration Guide

This guide details how to customize folder paths, system binaries, and execution overrides when running GoodQ4All on Windows 11.

---

## 1. Default Folder Conventions

By default, GoodQ4All writes data, configuration, cache, models, and logs under the system program data hierarchy:
* **Data & Processing Root**: `%ProgramData%\GoodQ4All`
* **Configuration File**: `%ProgramData%\GoodQ4All\config`
* **Cache**: `%ProgramData%\GoodQ4All\cache`
* **Models**: `%ProgramData%\GoodQ4All\models`
* **Logs**: `%ProgramData%\GoodQ4All\logs`

## 2. Environment Variables Overrides

You can redirect any of the default folders to other partitions or directories (e.g., fast NVMe SSD storage) by setting the following environment variables in your system settings or within `.env.local` at the repository root:

| Environment Variable | Description | Default Fallback Path |
|---|---|---|
| `GOODQ_DATA_ROOT` | Primary directory for processed data, database, index structures, and processing temp workspace. | `%ProgramData%\GoodQ4All` |
| `GOODQ_CONFIG_ROOT` | Path to load and store configuration definitions. | `GOODQ_DATA_ROOT\config` |
| `GOODQ_CACHE_ROOT` | Root cache folder for HuggingFace downloads and general cache tasks. | `GOODQ_DATA_ROOT\cache` |
| `GOODQ_LOGS_ROOT` | Target log output directory. | `GOODQ_DATA_ROOT\logs` |
| `GOODQ_MODELS_ROOT` | Model hub storage folder (HuggingFace transformers, diarization, Whisper checkpoints). | `GOODQ_DATA_ROOT\models` |
| `GOODQ_TEMP_ROOT` | Processing workspace folder for incoming files. | `GOODQ_DATA_ROOT\processing` |

### Setting Environment Variables in Windows (PowerShell)
To set an environment variable temporarily in PowerShell:
```powershell
$env:GOODQ_DATA_ROOT = "<Drive>:\GoodQ_Data"
```

To set it persistently for the current user:
```powershell
[Environment]::SetEnvironmentVariable("GOODQ_DATA_ROOT", "<Drive>:\GoodQ_Data", "User")
```

## 3. Custom Binary Resolvers

The `ToolResolver` automatically scans your environment paths, bundled vendor folders, and system program files. If you have custom or pre-existing binary installations, you can bypass the scan by declaring specific binary overrides:

* **FFmpeg**: Set `GOODQ_FFMPEG_EXE` pointing to `ffmpeg.exe` or its containing folder:
  ```powershell
  $env:GOODQ_FFMPEG_EXE = "<ToolsDrive>:\Tools\ffmpeg\bin\ffmpeg.exe"
  ```
* **Poppler (pdftotext)**: Set `GOODQ_POPPLER_BIN` to point to the containing bin directory of `pdftotext.exe`:
  ```powershell
  $env:GOODQ_POPPLER_BIN = "<ToolsDrive>:\Tools\poppler\Library\bin"
  ```

## 4. Verification

To verify that your custom environment overrides are recognized and resolved correctly by the runtime, run:

```powershell
conda run -n goodq_core python scripts/bootstrap_verify.py
```
Check the output block under `env:` to confirm the resolved paths.
