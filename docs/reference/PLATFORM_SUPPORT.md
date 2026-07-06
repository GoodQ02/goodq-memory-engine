<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-07 -->

# Multi-Platform Runtime Contract

## Purpose

Define the current supported runtime contract for:

- **Windows Desktop:** The primary canonical host and coordination baseline.
- **Windows Laptop:** A follower host aligning from the desktop.
- **macOS (Apple Silicon):** Native direct execution environment with MPS (Metal Performance Shaders) acceleration.
- **Linux:** Native direct execution environment with CUDA/CPU options.
- **`BASELINE` Profile:** CPU-safe portable execution.
- **`GPU_ENHANCED` Profile:** CUDA / MPS / WSL-accelerated execution.

---

## Host Roles & Platform Contracts

| Platform / Role | Contract |
| --- | --- |
| **Windows Desktop** | Canonical source of truth for code, epochs, ingestion state, and validation baselines. |
| **Windows Laptop** | Follower host that aligns from the desktop and must preserve CPU-safe correctness. |
| **macOS (Apple Silicon)** | Direct native execution host; leverages MPS for perception embeddings, CPU/MPS for Whisper transcription, and CPU for PyAnnote diarization. |
| **Linux (Ubuntu/Arch)** | Direct native execution host; leverages local CUDA or CPU backends natively. |

---

## Mandatory Baseline Assumptions

| Requirement | Why it matters |
| --- | --- |
| Platform-appropriate execution model | Supports Windows (`conda run` or embedded), macOS, and Linux direct execution. |
| Config loaded through `config_loader` | Runtime paths and overrides depend on layered config + `.env.local` and PlatformHelper resolution. |
| Local persistence available | SQLite + Qdrant remain the authoritative local storage layer. |
| CPU-safe behavior preserved | `BASELINE` must remain functional on CPU across all platforms. |
| WSL binding (Windows-only) | WSL is a compute extension for audio acceleration under Windows only, and must be explicitly bound. |

---

## Active Environment Contract

Current profile and strictness controls:

- `GOODQ_HOST_PROFILE=UNSET|BASELINE|GPU_ENHANCED`
- `GOODQ_REQUIRE_GPU=0|1`
- `GOODQ_REQUIRE_WSL_AUDIO=0|1`
- `GOODQ_WSL_DISTRO=<distro>`
- `GOODQ_WSL_USER=<user>`
- `GOODQ_WSL_WORKSPACE=<path>`

Notes:

- `GOODQ_REQUIRE_GPU=1` turns GPU acceleration into a fail-fast requirement.
- `GOODQ_REQUIRE_WSL_AUDIO=1` turns WSL audio acceleration into a fail-fast requirement.
- `GOODQ_WSL_USER` and `GOODQ_WSL_WORKSPACE` are part of the deterministic WSL contract on accelerated hosts.
- `GOODQ_NO_AUTO_GPU` is an internal runtime guard used to keep `BASELINE` CPU-safe. It is not the primary profile-selection surface for operators.

Older enable-style GPU / WSL flags from earlier docs are not part of the live runtime contract.

---

## Profile Semantics

### `UNSET`

- Preserves legacy canonical behavior while config and environment resolve the active host semantics.

### `BASELINE`

- CPU-safe default profile
- WSL audio optional
- correctness must not depend on GPU availability
- runtime may force internal no-auto-GPU behavior to preserve safe execution

### `GPU_ENHANCED`

- additive acceleration profile
- enables CUDA-backed step execution where supported
- prefers WSL unified audio when configured and available
- still relies on the same canonical persistence, manifests, and ingest contracts as `BASELINE`

---

## Deterministic WSL Contract

When WSL audio is part of the active host contract, the following identity must be explicit:

- distro via `GOODQ_WSL_DISTRO`
- user via `GOODQ_WSL_USER`
- workspace via `GOODQ_WSL_WORKSPACE`

Current bootstrap/doctor/runtime truth surfaces distinguish:

- `gpu_ready`
- `transcription_ready`
- `process_import_ready`
- `diarization_ready`

This allows bootstrap and doctor to report transcription-ready but diarization-degraded states honestly instead of treating WSL audio as a single opaque boolean.

`diarization_ready` is the strictest of these surfaces: it means the sourced
WSL runtime can resolve and load the configured diarization pipeline offline
from its active cache root. Import-only checks and token presence are not
treated as sufficient readiness.

For the current operator-facing details, see:

- [`docs/reference/WSL_AUDIO_RUNTIME.md`](WSL_AUDIO_RUNTIME.md)

---

## Compatibility Rule

- A host that satisfies the baseline assumptions is contract-compliant as `BASELINE`.
- `GPU_ENHANCED` is additive and must not be required for correctness.
- Desktop remains canonical for synchronization and witness baselines.
- Laptop remains follower-only even when it can execute accelerated lanes.

---

## Related Docs

- [`docs/releases/SHIP_PROFILE.md`](../archive/releases/SHIP_PROFILE.md)
- [`docs/reference/DEPENDENCIES.md`](DEPENDENCIES.md)
- [`docs/reference/GPU_CAPABILITY_MATRIX.md`](GPU_CAPABILITY_MATRIX.md)
- [`docs/reference/WSL_AUDIO_RUNTIME.md`](WSL_AUDIO_RUNTIME.md)
- [`docs/reference/indexes/ENVIRONMENT_INDEX.md`](indexes/ENVIRONMENT_INDEX.md)
