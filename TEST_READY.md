# Test Readiness Attestation

## Test Runner Command
To run the staged ingestion harness E2E test suite with the mock compliance layer enabled:
```powershell
$env:TEST_MOCK_HARNESS="1"; conda run -n goodq_core pytest tests/e2e/test_staged_ingestion_harness.py
```
To run the test suite against the actual client to observe expected failures due to unimplemented features:
```powershell
$env:TEST_MOCK_HARNESS="0"; conda run -n goodq_core pytest tests/e2e/test_staged_ingestion_harness.py
```

## Coverage Summary
The test suite consists of **50 tests** mapped across 4 tiers:
- **Tier 1: Feature Coverage** (20 tests, F1.01-05, F2.01-05, F3.01-05, F4.01-05)
- **Tier 2: Boundary & Corner Cases** (20 tests, F1.06-10, F2.06-10, F3.06-10, F4.06-10)
- **Tier 3: Cross-Feature Combinations** (5 tests, collisions, vector backfilling, orphan vectors, validation/sanitization interaction, handshake loop)
- **Tier 4: Real-World Scenarios** (5 tests, complete happy path loop, failure aborts, path audit, concurrency, recovery)

## Feature Checklist Matrix

| Feature | Feature Description | Tier 1 (F1-5) | Tier 2 (F6-10) | Verified (Mock)? |
|---|---|---|---|---|
| **1. Gated Execution** | Command routing in safe/offline/unrestricted profiles & agent failures | Pass | Pass | Yes (10/10) |
| **2. UCF Validation** | Post-ingestion validator (`validate_ucf_epoch.py`) automatic checks | Pass | Pass | Yes (10/10) |
| **3. Human-in-the-Loop** | Staged records lifecycle & confirm/confirmation_token gating | Pass | Pass | Yes (10/10) |
| **4. Path Sanitization** | Redaction of absolute local file paths (C:\ or L:\) in output envelopes | Pass | Pass | Yes (10/10) |

## Cross-Feature and Real-World Scenarios (Tiers 3 & 4)

- **Tier 3 Cross-Feature Combinations**:
  - `test_f3_tier3_01_profile_collision_offline_takes_precedence`: Verified (Pass)
  - `test_f3_tier3_02_qdrant_faiss_backfilling_sync`: Verified (Pass)
  - `test_f3_tier3_03_orphan_vector_injection_blocking`: Verified (Pass)
  - `test_f3_tier3_04_sanitization_applied_to_validation_failure_report`: Verified (Pass)
  - `test_f3_tier3_05_promotion_validation_handshake_loop`: Verified (Pass)
- **Tier 4 Real-World Application Scenarios**:
  - `test_f4_tier4_01_complete_happy_path_loop`: Verified (Pass)
  - `test_f4_tier4_02_validation_failure_aborts_pipeline`: Verified (Pass)
  - `test_f4_tier4_03_path_audit_scenario`: Verified (Pass)
  - `test_f4_tier4_04_concurrency_isolation`: Verified (Pass)
  - `test_f4_tier4_05_agent_failure_recovery_scenario`: Verified (Pass)
