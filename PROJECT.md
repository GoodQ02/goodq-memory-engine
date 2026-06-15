# Project: Agent-Gated Staged Ingestion Harness

## Architecture
- Subsystem: Ingestion middleware layer gating and validation flow.
- Core component: `agents/mini_agent_client.py` wrapping execution of commands using `goodq_mini_agent.cli` runner.
- Gate validation component: `scripts/ucf/validate_ucf_epoch.py` executed after ingestion.
- Promotion component: `promote_ucf_to_memory` gating via confirmation flags and confirmation tokens.
- Sanitization component: path-agnostic redaction (redacting `L:\GOODCUBE\...`, `C:\Users\...`) of returned envelopes.
- Backfill database: backfilling Qdrant points payload and FAISS sidecar mapping tables with row IDs.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Architecture Mapping & Exploration | Explore MiniAgentClient, test suite, validation script | none | IN_PROGRESS |
| 2 | Mini Agent Gating Middleware | Implement safe/offline/unrestricted runtime profiles, tool validation | M1 | PLANNED |
| 3 | Post-Ingestion Validation Gate | Trigger validate_ucf_epoch.py post-ingestion, check exit status | M2 | PLANNED |
| 4 | Human-in-the-Loop & Verification | Staged status enforcement, confirmation token flow | M3 | PLANNED |
| 5 | Envelope Path Sanitization | Redact local absolute path roots from outputs | M4 | PLANNED |
| 6 | Database/Vector Backfills | Colliding videos ucf_ledger.db integration, Qdrant/FAISS row ID backfills, orphan vector gate | M5 | PLANNED |
| 7 | Full E2E & Verification | Run tests, mock orphan tests, check all 728+ unit tests | M6 | PLANNED |

## Interface Contracts
### MiniAgentClient ↔ Ingestion CLI
- Execution routed via `goodq_mini_agent.cli` runner.
- Profiles: `safe`, `offline`, `unrestricted`.
- Block/allow tool contracts for: `run_ingestion` (`ingest_staged`), `validate_ucf_epoch` (`validate_only`), `promote_ucf_to_memory` (`mutate_canonical`), and `file_delete` (`destructive`).

### Human-in-the-Loop Promotion
- `promote_ucf_to_memory` accepts `confirm_flag: bool` and `confirmation_token: str`.
- Output: `needs_confirmation` and token when unconfirmed, proceeds only when valid token and flag are provided.

### Envelope Sanitization
- Input: JSON dict/string with absolute paths (e.g. `L:\GOODCUBE\...`, `C:\Users\...`).
- Output: Redacted relative path format.

## Code Layout
- `agents/mini_agent_client.py` - Middleware gating client
- `scripts/ucf/validate_ucf_epoch.py` - Ingestion validation script
- `cli/run_ingestion.py` - Ingestion execution loop
- `cli/step_runner.py` - Ingestion step execution
- `tests/` - Unit and integration tests
