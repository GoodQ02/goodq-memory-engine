<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-10 -->

# Canonical Runtime Configuration Loading Contract

### 1) Configuration authority

- **Tracked portable baseline:** `configs/config.yaml`
- **Ignored private override:** `configs/config.local.yaml`
- **Private override template:** `configs/config.local.example.yaml`
- **Secrets:** environment variables, optionally provisioned from ignored
  `.env.local`
- **Canonical loader/API:** `steps/common/config_loader.py::load_configs()`
- **Canonical runtime truth:** the resolved dictionary returned by
  `load_configs()`, not either YAML file in isolation
- **Service-local runtime configs:** WSL2 audio JSON configs under `wsl2_audio/`
  remain scoped to that subsystem and are not core configuration authority

Tracked configuration must contain generic defaults only. Operator identity,
machine descriptions, active epoch routing, private service values, and secrets
belong in ignored local authority or environment variables.

Machine topology labels, household service addresses, hardware descriptions,
and operator voice preferences are private deployment values. Their tracked
defaults must remain generic; the concrete values belong in
`configs/config.local.yaml` or supported environment references.

### 2) How Runtime Code MUST Obtain Config
- Runtime **entry points** MUST call `load_configs()` exactly once at process start (optionally with explicit `overrides`) and then pass the resulting `cfg` dict downward.
- Non-entry-point modules MUST NOT call `load_configs()`; they MUST accept `cfg` (or specific config slices) as parameters.
- Runtime code MUST treat the returned config as read-only (no in-place mutation).

### 3) Resolution order

`load_configs()` resolves configuration in this order:

1. Load ignored `.env.local` when present; externally supplied environment
   variables retain precedence.
2. Establish a platform-derived `GOODQ_DATA_ROOT` when the environment does not
   provide one.
3. Load and normalize tracked `configs/config.yaml`.
4. Deep-merge ignored `configs/config.local.yaml` when present.
5. Deep-merge caller-supplied `overrides`.
6. Derive missing runtime paths and resolve supported tools.
7. Apply the local `runtime_config.json` Qdrant host/port override when present
   under `GOODQ_DATA_ROOT`.
8. Validate through `config_schema.GoodQConfig` when importable; otherwise
   return the resolved dictionary with a visible warning on validation failure.

String values support `${NAME}` and `${NAME:-default}` environment references.
Tracked defaults must use those references or platform helpers instead of
literal workstation roots or a dated active epoch.

### 4) Environment variables and private local configuration

- Runtime code MAY read environment variables directly (e.g., `os.getenv(...)`) for secrets and host-specific values.
- Runtime code MUST NOT parse `.env.local` itself; only `load_configs()` performs `.env.local` loading for runtime.
- `.env.local` is a **local developer convenience**, not an authoritative config file; externally-provided environment variables remain authoritative (consistent with default `python-dotenv` behavior).
- `configs/config.local.yaml` is the local non-secret configuration authority and
  is ignored by Git.
- Private values must never be copied back into `configs/config.yaml` merely to
  make the current workstation work.

### 4a) Display and Logging Redaction
- `load_configs()` returns raw runtime config for runtime consumers; do not weaken or redact that object before passing it to runtime code.
- Display, logging, resolved-config snapshots, and other operator surfaces MUST sanitize config-like payloads through `steps/common/config_redaction.py`.
- `cli.print_config` prints sanitized operator JSON by default and has no supported raw-secret print mode.
- Local path tokenization is display-only; it must not change runtime config semantics or persisted runtime paths.

### 5) Windows ↔ WSL2 Interop
- Tracked active configuration must not contain literal Windows drive roots.
- Local overrides may resolve host-specific paths from environment variables;
  the loader normalizes Windows drive paths when the resolved config is consumed
  on WSL/Linux.
- WSL2 audio services currently use JSON configs (`wsl2_audio/config.json`, `wsl2_audio/bridge_config.json`). These remain **subsystem-local**; core runtime code must not treat `~/goodq_audio/config.json` or direct WSL UNC-share reads as authoritative runtime configuration; those reads are diagnostics-only.

### 6) What’s Allowed (Runtime vs Tooling)
- **Runtime code (API/CLI/watchers/services):** may call `load_configs()` at entry points; may read env vars; may read subsystem-local JSON only inside that subsystem.
- **Tooling/scripts/tests:** may continue legacy direct config reads for now, but MUST NOT introduce new runtime dependencies on those patterns.
- **Agent safety rule:** agents must not modify files outside verified runtime entry points (and the canonical loader) unless explicitly instructed.

### 7) Transitional Allowances (Legacy Paths)
Tolerated temporarily (do not expand usage; migrate when touched):
- Direct reads of repo-root `config.yaml` in control-plane/agent code.
- `config/gpu_config.yaml` reads in `cli/step_runner.py`.
- References to older or nonexistent config filenames in tooling that is not a
  verified runtime entry point.

## Invariants Runtime Code May Rely On
- `load_configs()` resolves the tracked baseline, optional ignored local
  override, explicit caller overrides, and runtime-derived values into one dict.
- Missing canonical config is a hard failure (`FileNotFoundError`).
- Windows→WSL path normalization is applied to string values when not on Windows.
- `.env.local` loading is best-effort and does not gate startup if unavailable.
- Absence of `config.local.yaml` is valid and must produce a generic portable
  baseline.

## Unsupported Access Patterns Going Forward
- Runtime modules (non-entry points) calling `load_configs()` internally or inside hot loops.
- Runtime code directly doing `open(...config...)`, `yaml.safe_load(...)`, or hardcoding config file paths.
- Runtime code introducing new “extra” config files/formats outside `configs/config.yaml` (except explicitly-scoped subsystem configs like WSL2 audio).
- Tracked configuration embedding private identity, secrets, literal workstation
  roots, or a dated active epoch.
