# Project: Agent-Gated Staged Ingestion Harness

## Architecture
- Subsystem: Ingestion middleware layer gating and validation flow.
- Core component: `agents/mini_agent_client.py` wrapping execution of commands using `goodq_mini_agent.cli` runner.
- Gate validation component: `scripts/ucf/validate_ucf_epoch.py` executed after ingestion.
- Promotion component: `promote_ucf_to_memory` gating via confirmation flags and confirmation tokens.
- Sanitization component: path-agnostic redaction (redacting `L:\GOODCUBE\...`, `C:\Users\...`) of returned envelopes.
- Backfill database: backfilling Qdrant points payload and FAISS sidecar mapping tables with row IDs.

## Milestones
| # | Name | Scope | Dependencies | Status | Description |
|---|------|-------|-------------|--------|-------------|
| 1 | Architecture Mapping & Exploration | Explore MiniAgentClient, test suite, validation script | none | DONE | Explored codebase, mapping 8 key test files (`test_ucf_*.py` and `test_staged_ingestion_harness.py`). |
| 2 | Mini Agent Gating Middleware | Implement safe/offline/unrestricted runtime profiles, tool validation | M1 | DONE | Implemented `MiniAgentClient` with gating profiles and tool-level validation rules. |
| 3 | Post-Ingestion Validation Gate | Trigger validate_ucf_epoch.py post-ingestion, check exit status | M2 | DONE | Configured automated post-ingestion execution of validator and evaluated exit codes. |
| 4 | Human-in-the-Loop & Verification | Staged status enforcement, confirmation token flow | M3 | DONE | Implemented staged status gating and dynamic confirmation token flow (validation and timeout checking). |
| 5 | Envelope Path Sanitization | Redact local absolute path roots from outputs | M4 | DONE | Implemented path-agnostic absolute path redaction (UNC, WSL, Windows drive letters) in outgoing envelopes. |
| 6 | Database/Vector Backfills | Colliding videos ucf_ledger.db integration, Qdrant/FAISS row ID backfills, orphan vector gate | M5 | DONE | Synchronized collided video frames and backfilled Qdrant points and FAISS mapping sidecar tables with IDs. |
| 7 | Full E2E & Verification | Run tests, mock orphan tests, check all 728+ unit tests | M6 | DONE | Verified entire suite with integration and E2E tests, resolving path, thread safety, and backdoor issues. |
| 8 | E2E doctrine alignment | Align E2E doctrine and schema invariants | M7 | DONE | Hardening E2E ingestion and validation workflows. |
| 9 | Validator fixes | Fix FAISS modality, CLIP registry, and error reporting | M8 | DONE | Implement R2, R4, and R5 in validate_ucf_epoch.py. |
| 10 | Error-path regression tests | Error-path regression coverage | M9 | DONE | Prevent validator regressions and handle edge cases. |
| 11 | Final verification | Run final integration and E2E verification | M10 | DONE | Verify entire test suite and clean up resources. |


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
