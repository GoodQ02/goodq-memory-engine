# Project: UCF Phase 0.9: Terminal State Closure

## Architecture
This project focuses on locking in the terminal state closure behavior for the Unified Context Frame (UCF) lifecycle system in GoodQ4All. The lifecycle transition from staged/validated to terminal states (rejected, superseded) is implemented in `agents/mini_agent_client.py`. 

The architecture consists of:
1. **Lifecycle E2E Tests**: Integration tests in `tests/e2e/test_staged_ingestion_harness.py` validating that the `reject_ucf_frames` and `supersede_ucf_frames` tools transition frames to `rejected` and `superseded` states and assert exact DB counts under the `if not mock_harness_active():` guard.
2. **Tool Registration Matrix Test**: An integration test verifying that the four HITL-gated lifecycle tools (`validate_ucf_frames`, `promote_ucf_to_memory`, `reject_ucf_frames`, `supersede_ucf_frames`) are fully registered across all 6 key registration sections in `agents/mini_agent_client.py`.
3. **Search Loop Visibility Plan**: A plan document answering visibility, search blending, and validation requirements.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | R1: Terminal State E2E Tests | Implement 9 E2E lifecycle tests in `tests/e2e/test_staged_ingestion_harness.py` | None | DONE |
| 2 | R2: Tool Registration Matrix Test | Implement registration matrix test in `tests/agents/test_mini_agent_client.py` | None | DONE |
| 3 | R3: Search Loop Visibility Plan | Write plan document in `docs/agent/UCF_SEARCH_LOOP_PLAN.md` | None | DONE |
| 4 | Final QA and Verification | Execute full test suite and path-leak check | M1, M2, M3 | DONE |

## Code Layout
- `agents/mini_agent_client.py` — Client implementation containing tools registration and verification logic.
- `tests/e2e/test_staged_ingestion_harness.py` — Target for the 9 E2E lifecycle tests.
- `tests/agents/test_mini_agent_client.py` — Target for the tool registration matrix test.
- `docs/agent/UCF_SEARCH_LOOP_PLAN.md` — Target for the visibility plan document.
