<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Canonical Runtime Configuration Loading Contract

### 1) Single Source of Truth
- **Canonical runtime config:** `configs/config.yaml`
- **Canonical loader/API:** `steps/common/config_loader.py::load_configs()`
- **Secrets/config that must not live in YAML:** environment variables (optionally provisioned from `.env.local`)
- **Service-local runtime configs (allowed but non-canonical):** WSL2 audio JSON configs under `wsl2_audio/` (kept scoped to that subsystem)

### 2) How Runtime Code MUST Obtain Config
- Runtime **entry points** MUST call `load_configs()` exactly once at process start (optionally with explicit `overrides`) and then pass the resulting `cfg` dict downward.
- Non-entry-point modules MUST NOT call `load_configs()`; they MUST accept `cfg` (or specific config slices) as parameters.
- Runtime code MUST treat the returned config as read-only (no in-place mutation).

### 3) `load_configs()` Guarantees (Current + Normative)
`load_configs()` (as implemented today) guarantees:
- Loads `.env.local` from repo root **if present** and `python-dotenv` is available (best-effort; warns and continues on failure).
- Loads YAML from `configs/config.yaml` (raises `FileNotFoundError` if missing).
- Returns a `dict` (empty YAML becomes `{}`).
- Deep-merges `overrides` into the loaded config (nested dict merge).
- Normalizes Windows drive paths like `<project_root>/...` into `/mnt/l/...` when running on non-Windows hosts (recursive over dict/list/string values).
- Attempts schema validation via `config_schema.GoodQConfig` when importable; otherwise falls back to the raw dict (validation is not guaranteed).

### 4) Environment Variables + `.env.local`
- Runtime code MAY read environment variables directly (e.g., `os.getenv(...)`) for secrets and host-specific values.
- Runtime code MUST NOT parse `.env.local` itself; only `load_configs()` performs `.env.local` loading for runtime.
- `.env.local` is a **local developer convenience**, not an authoritative config file; externally-provided environment variables remain authoritative (consistent with default `python-dotenv` behavior).

### 5) Windows ↔ WSL2 Interop
- `configs/config.yaml` may contain Windows-style drive paths (`<drive>:/...`); `load_configs()` normalizes these automatically when executed under WSL/Linux.
- WSL2 audio services currently use JSON configs (`wsl2_audio/config.json`, `wsl2_audio/bridge_config.json`). These remain **subsystem-local**; core runtime code must not treat `~/goodq_audio/config.json` or direct WSL UNC-share reads as authoritative runtime configuration; those reads are diagnostics-only.

### 6) What’s Allowed (Runtime vs Tooling)
- **Runtime code (API/CLI/watchers/services):** may call `load_configs()` at entry points; may read env vars; may read subsystem-local JSON only inside that subsystem.
- **Tooling/scripts/tests:** may continue legacy direct config reads for now, but MUST NOT introduce new runtime dependencies on those patterns.
- **Agent safety rule:** agents must not modify files outside verified runtime entry points (and the canonical loader) unless explicitly instructed.

### 7) Transitional Allowances (Legacy Paths)
Tolerated temporarily (do not expand usage; migrate when touched):
- Direct reads of repo-root `config.yaml` in control-plane/agent code.
- `config/gpu_config.yaml` reads in `cli/step_runner.py`.
- Hardcoded absolute config paths in scripts (e.g., `<project_root>/...`) and references to older/nonexistent config filenames.

## Invariants Runtime Code May Rely On
- `load_configs()` reads from `configs/config.yaml` and returns a dict.
- Missing canonical config is a hard failure (`FileNotFoundError`).
- Windows→WSL path normalization is applied to string values when not on Windows.
- `.env.local` loading is best-effort and does not gate startup if unavailable.

## Unsupported Access Patterns Going Forward
- Runtime modules (non-entry points) calling `load_configs()` internally or inside hot loops.
- Runtime code directly doing `open(...config...)`, `yaml.safe_load(...)`, or hardcoding config file paths.
- Runtime code introducing new “extra” config files/formats outside `configs/config.yaml` (except explicitly-scoped subsystem configs like WSL2 audio).
- Runtime code relying on implicit `${VAR}` interpolation inside YAML (use env vars explicitly instead).
