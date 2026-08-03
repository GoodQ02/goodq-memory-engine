<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-06-17 -->

# GoodQ4All Dependency Architecture & Ownership Rules

This document outlines the design decisions behind GoodQ4All's dependency split-brain structure and defines clear boundaries for managing and extending our dependencies.

## Architecture: The Split-Brain Model

GoodQ4All deliberately separates its package-level dependencies from its local orchestration runtime environment. This matches our architecture as a local-first system that has a light developer/CLI client interface but runs robust heavy services (GPU compute, audio/vision embeddings, local vector database) in the background.

```
+--------------------------------------------------------+
|                                                        |
|  [ CLI / Packaging Layer ] (setup.py)                  |
|    - Thin client surface (typer, imageio-ffmpeg)       |
|    - Minimal footprint for local import/CLI hooks       |
|                                                        |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
|                                                        |
|  [ Orchestration Runtime ] (environment.yml)           |
|    - Full local stack (FastAPI, uvicorn, PyTorch,      |
|      sentence-transformers, qdrant-client, faiss)      |
|    - Authoritative Conda env for active local service   |
|                                                        |
+--------------------------------------------------------+
```

---

## Dependency Ownership Rules

To prevent siloing or accidental leakage (e.g. jamming all packages into `setup.py` or neglecting CI environment alignment), the following ownership boundaries are strictly enforced:

### 1. `setup.py`
- **Scope**: Thin CLI client, packaging, and light developer imports only.
- **Rules**:
  - Must only declare minimal requirements needed to boot the CLI and parse configurations (`typer`, `imageio-ffmpeg`).
  - Heavy ML packages (PyTorch, transformers, qdrant-client) must **never** be added to `setup.py`'s `install_requires`.
  - Can include optional client extensions in `extras_require` (e.g., local audio fallback dependencies like `faster-whisper`), but the base package must remain extremely lightweight.

### 2. `environment.yml` & `environment.gpu.yml`
- **Scope**: Canonical local orchestration environment specifications.
- **Rules**:
  - `environment.yml` is the authoritative definition of the CPU-safe `BASELINE` local orchestration runtime.
  - `environment.gpu.yml` defines the `GPU_ENHANCED` extension layer (adding CUDA-backed throughput packages like PyTorch CUDA and FAISS GPU).
  - Any core CLI dependency listed in `setup.py`'s `install_requires` **must also** be present in `environment.yml` so the development specification remains a complete super-set of package requirements.

### 3. `requirements-baseline-lock.txt` & `environment-baseline-lock.yml`
- **Scope**: Pinned reproducibility snapshots.
- **Rules**:
  - These lockfiles represent the exact, frozen environment states verified on green CI builds.
  - GitHub Actions creates `goodq_core` from `environment-baseline-lock.yml`; it does not resolve the broad development specifications in `environment.yml`.
  - CI prints a concise runtime version receipt and runs `pip check` before verification so any future dependency drift is visible at the environment boundary.
  - Developers must update these lockfiles in lock-step whenever dependencies in definition files (`environment.yml` or `setup.py`) are modified.
  - Updates must be verified via automated lints to ensure they comply with constraints (such as `fastapi<0.137.0`).

### 4. `envs/**/requirements.txt`
- **Scope**: Isolated step environments.
- **Rules**:
  - Specialized pipeline steps (like `image_caption` or `object_detect`) run inside isolated environments to prevent dependency conflicts (e.g., conflicting version requirements for scientific packages).
  - These requirements files **must not** silently introduce global runtime requirements that are expected to be present in the main `goodq_core` orchestration environment.
  - Changes to these isolated steps must be covered by GitHub dependency-review gates.
