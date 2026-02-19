<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-19 -->

# GoodQ4All

GoodQ4All is a local-first multimodal memory system for long-running ingestion, retrieval, and analysis across video, audio, text, embeddings, and knowledge graph context.

## Mission

- Keep memory local, auditable, and durable.
- Treat scenes as the atomic unit of intelligence.
- Support CPU-safe baseline execution and additive GPU/WSL acceleration.
- Preserve operational continuity under partial failures.

## System Identity

- Local-first operation with no required cloud runtime dependency.
- Persistent state through SQLite + Qdrant + knowledge graph storage.
- Watchdog and control-plane driven for long-running workloads.
- Audit-grade behavior: failures are visible, logged, and attributable.

## Capability Surface

- Vision: scene detection, captions, OCR, object and embedding extraction.
- Audio: transcription, diarization, emotion tagging, embedding extraction.
- Text: semantic indexing, sentiment and entity enrichment.
- Memory: scene manifests, relational state, vector retrieval, graph context.
- Operations: watchdog ingest, health checks, deterministic bootstrap validation.

## Runtime Profiles

GoodQ4All is profile-governed, not hardware-assumption governed.

| Profile | Intent | Behavior |
| --- | --- | --- |
| `UNSET` | Legacy canonical | Preserves historical default behavior |
| `BASELINE` | Portability-first | CPU-safe correctness, optional accelerators |
| `GPU_ENHANCED` | Throughput-first | Enables additive CUDA/WSL acceleration |

Strict fail-fast flags:

- `GOODQ_REQUIRE_GPU=1`: fail when GPU capability is required but unavailable.
- `GOODQ_REQUIRE_WSL_AUDIO=1`: fail when WSL audio path is required but unavailable.

## Environment Contract (v2.2.0)

Primary host identity and portability variables:

- `GOODQ_HOST_PROFILE`
- `GOODQ_DATA_ROOT`
- `GOODQ_CONDA_ENV` (default fallback: `goodq_core`)
- `GOODQ_WSL_DISTRO` (default fallback: `Ubuntu`)
- `GOODQ_WSL_USER` (recommended explicit for strict desktop)
- `GOODQ_WSL_WORKSPACE` (recommended explicit for strict desktop)
- `GOODQ_REQUIRE_GPU`
- `GOODQ_REQUIRE_WSL_AUDIO`

Path abstraction contract:

- Active docs and runtime surface use `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>`.
- Legacy literals are documented only in allowlisted legacy docs.

Reference: [`docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md`](docs/bootstrap/PATH_ABSTRACTION_CONTRACT.md)

## Quick Start

### 1. Open Repo Root

```powershell
git clone <repo_url>
cd goodq4all
```

### 2. Choose Profile

```powershell
# CPU-safe portability mode
$env:GOODQ_HOST_PROFILE = "BASELINE"

# Optional strict checks
$env:GOODQ_REQUIRE_GPU = "0"
$env:GOODQ_REQUIRE_WSL_AUDIO = "0"
```

### 3. Run Bootstrap Validation

```powershell
.\scripts\bootstrap_validate.bat
```

This staged check validates docs governance, bootstrap semantics, and test status.

### 4. Launch

```powershell
# PowerShell launcher
.\LAUNCH_GOODQ.ps1

# or Batch launcher
.\LAUNCH_GOODQ.bat
```

## Security Posture

- Secrets live in `.env.local` only.
- No telemetry or phone-home behavior in canonical runtime.
- Raw sensitive query text should not be persisted in retrieval event logs.
- Local storage is the source of truth; logs support investigation, not authority.
- Operational posture is conservative by design: explicit config, clear failure signals, minimal trust assumptions.

## Documentation Map

### Start Here

- Install (canonical): [`docs/guides/install/INSTALL.md`](docs/guides/install/INSTALL.md)
- Quickstart (canonical): [`docs/guides/install/QUICKSTART.md`](docs/guides/install/QUICKSTART.md)
- Laptop profile guide: [`docs/guides/install/LAPTOP.md`](docs/guides/install/LAPTOP.md)
- Smoke matrix: [`docs/bootstrap/smoke_matrix_phase_a.md`](docs/bootstrap/smoke_matrix_phase_a.md)

### Runtime Authority

- Handoff baseline: [`docs/HANDOFF_BASEMENT_PHASE.md`](docs/HANDOFF_BASEMENT_PHASE.md)
- Agent status: [`docs/goodq4all_agent_status.md`](docs/goodq4all_agent_status.md)
- System snapshot: [`docs/SYSTEM_SNAPSHOT.md`](docs/SYSTEM_SNAPSHOT.md)
- Runtime authority memo: [`docs/RUNTIME_AUTHORITY_MEMO.md`](docs/RUNTIME_AUTHORITY_MEMO.md)
- Data epochs: [`docs/data_epochs.md`](docs/data_epochs.md)

### Architecture and Operations

- System architecture: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- Memory storage: [`docs/architecture/MEMORY_STORAGE.md`](docs/architecture/MEMORY_STORAGE.md)
- Vision pipeline: [`docs/architecture/components/VISION_PIPELINE.md`](docs/architecture/components/VISION_PIPELINE.md)
- Watchdog system: [`docs/systems/WATCHDOG_SYSTEM.md`](docs/systems/WATCHDOG_SYSTEM.md)
- Control agent: [`docs/CONTROL_AGENT.md`](docs/CONTROL_AGENT.md)
- Multimodal fusion: [`docs/PHASE6_MULTIMODAL_FUSION.md`](docs/PHASE6_MULTIMODAL_FUSION.md)
- CLI reference: [`docs/CLI-REFERENCE.md`](docs/CLI-REFERENCE.md)
- Library components: [`docs/technical/LIB_COMPONENTS.md`](docs/technical/LIB_COMPONENTS.md)

### Governance and Drift Controls

- Governance summary: [`docs/bootstrap/doc_governance_summary.md`](docs/bootstrap/doc_governance_summary.md)
- Authority policy: [`docs/bootstrap/doc_authority_policy.md`](docs/bootstrap/doc_authority_policy.md)
- Authority map: [`docs/bootstrap/doc_authority_map.md`](docs/bootstrap/doc_authority_map.md)
- Script registry: [`docs/bootstrap/SCRIPT_REGISTRY.md`](docs/bootstrap/SCRIPT_REGISTRY.md)
- Legacy path registry: [`docs/technical/LEGACY_PATHS_DEPRECATED.md`](docs/technical/LEGACY_PATHS_DEPRECATED.md)
- Drift lint: [`scripts/docs/doc_drift_lint.py`](scripts/docs/doc_drift_lint.py)

## Validation and Quality Gates

Recommended pre-push checks:

```powershell
python scripts/docs/doc_drift_lint.py
python -m pytest -q
.\scripts\bootstrap_validate.bat
```

## Historical Material

Historical reports and migration artifacts are intentionally preserved under [`docs/archive/`](docs/archive/).

## License

MIT. See [`LICENSE`](LICENSE).
