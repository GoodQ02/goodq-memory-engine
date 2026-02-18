# Launcher Portability Discovery

Date: 2026-02-18
Scope: `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat` only
Mode: Static/read-only discovery

## Findings

### 1) Repository root assumptions
- `LAUNCH_GOODQ.bat:5`
  - `cd /d L:\goodq4all`
  - Classification: **MUST replace**
  - Reason: hardcoded drive+path prevents portability.

- `LAUNCH_GOODQ.bat:6`
  - `-File "L:\goodq4all\LAUNCH_GOODQ.ps1"`
  - Classification: **MUST replace**
  - Reason: hardcoded absolute script path.

- `LAUNCH_GOODQ.ps1:21`
  - `$script:RootDir = $PSScriptRoot`
  - Classification: **Safe default fallback**
  - Reason: already dynamic and portable.

### 2) Data root assumptions
- `LAUNCH_GOODQ.ps1:22`
  - `$script:DataRoot = "L:\_DATA\GoodQ_Data"`
  - Classification: **MUST replace**
  - Reason: hardcoded drive-root path.

### 3) Conda env assumptions
- `LAUNCH_GOODQ.ps1:37`
  - `$script:CoreEnv = "goodq_core"`
  - Classification: **MUST replace** (to env-driven resolution)
  - Reason: runtime launcher should respect `GOODQ_CONDA_ENV` override.

## Existing dynamic resolution already present
- PowerShell launcher already uses `$PSScriptRoot` for repo root resolution.
- Batch launcher currently does **not** use `%~dp0`; must be normalized.

## Replacement Plan (launcher-only)
1. `.ps1`: resolve data root from `GOODQ_DATA_ROOT` with behavior-preserving fallback.
2. `.ps1`: resolve conda env from `GOODQ_CONDA_ENV` with fallback `goodq_core`.
3. `.bat`: replace absolute paths with `%~dp0` rooted invocation.

## Behavior Preservation Requirement
When env vars are unset, launcher behavior must remain functionally equivalent to current canonical desktop assumptions.
