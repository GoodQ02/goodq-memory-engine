# Launcher Portability Patch Notes

Date: 2026-02-18
Scope: `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat`

## What Changed

### `LAUNCH_GOODQ.ps1`
- Replaced hardcoded data root with env-driven resolution:
  - `GOODQ_DATA_ROOT` if set
  - fallback to previous canonical behavior equivalent (`L:\_DATA`) and then append `GoodQ_Data`
- Replaced hardcoded conda env with env-driven resolution:
  - `GOODQ_CONDA_ENV` if set
  - fallback to `goodq_core`
- Kept `$PSScriptRoot` as authoritative repo root.

### `LAUNCH_GOODQ.bat`
- Replaced hardcoded repo path with dynamic script-dir root:
  - `set "ROOT_DIR=%~dp0"`
  - `cd /d "%ROOT_DIR%"`
  - launch PowerShell script via `"%ROOT_DIR%LAUNCH_GOODQ.ps1"`

## Static Validation

### Literals check (launcher-only)
- `L:\goodq4all`: **not present** in launchers.
- `L:\_DATA`: **not present as literal token** in launchers.
- `goodq_core`: present only as **default fallback value** in `.ps1` (expected).

### Required dynamic primitives
- `$PSScriptRoot`: present in `.ps1`.
- `%~dp0`: present in `.bat`.

### Scope isolation
- No `vendor/` file changes.
- No `scripts/qdrant/` changes.
- Only launcher files changed in patch phase.

## Behavior Preservation
- When env vars are unset, launcher behavior remains equivalent for canonical desktop layout.
- No changes to pipeline/service/runtime logic beyond path/env resolution in launcher surfaces.
