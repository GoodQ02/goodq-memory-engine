<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-26 -->

# Dual-Host Runtime Contract (Desktop + Laptop)

## Purpose

Define the current supported runtime contract for:

- desktop as the canonical Windows host
- laptop as the follower host
- `BASELINE` as the CPU-safe profile
- `GPU_ENHANCED` as the additive CUDA + WSL acceleration profile

This document describes the live contract, not proposed future flags.

---

## Host Roles

| Role | Contract |
| --- | --- |
| Desktop | Canonical source of truth for code, epochs, ingestion state, and validation baselines |
| Laptop | Follower host that aligns from desktop and must preserve CPU-safe correctness |

---

## Mandatory Baseline Assumptions

| Requirement | Why it matters |
| --- | --- |
| Windows host + `conda run` execution model | Current launcher and interpreter bindings are Windows-first and environment-bound |
| Config loaded through `config_loader` | Runtime paths and overrides depend on layered config + `.env.local` |
| Local persistence available | SQLite + Qdrant remain the authoritative local storage layer |
| CPU-safe behavior preserved | `BASELINE` must remain functional without GPU acceleration |
| Deterministic WSL binding when enabled | WSL is a compute extension and must be invoked through explicit distro/workspace identity |

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

- [`docs/releases/SHIP_PROFILE.md`](../releases/SHIP_PROFILE.md)
- [`docs/reference/DEPENDENCIES.md`](DEPENDENCIES.md)
- [`docs/reference/GPU_CAPABILITY_MATRIX.md`](GPU_CAPABILITY_MATRIX.md)
- [`docs/reference/WSL_AUDIO_RUNTIME.md`](WSL_AUDIO_RUNTIME.md)
- [`docs/reference/indexes/ENVIRONMENT_INDEX.md`](indexes/ENVIRONMENT_INDEX.md)
