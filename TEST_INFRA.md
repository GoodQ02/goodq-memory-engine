<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: REFERENCE_ONLY -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Testing Infrastructure for Agent-Gated Staged Ingestion Harness

This document outlines the architecture, requirements, and design patterns utilized for the E2E test suite of the Agent-Gated Staged Ingestion Harness in `goodq4all`.

---

## 1. Subsystem under Test: Ingestion Gating Harness
The Agent-Gated Staged Ingestion Harness is responsible for securing local system integrity during automated memory ingestion and synchronization. It handles:
- Gated Command Routing: Allowing execution based on active profile (Safe, Unrestricted) or blocking it (Offline) and handling agent offline fallback policy.
- Post-Ingestion UCF Validation: Ensuring ingested epoch entries conform to the Unified Context Frame (UCF) schema prior to staging, by running `validate_ucf_epoch.py` automatically.
- Human-in-the-Loop Gating: Forcing ingested records to remain in a `staged` status until explicit confirmation (`confirm=True`) and a valid `confirmation_token` are supplied.
- Path Sanitization: Stripping absolute drive letters (`C:\`, `L:\`, or `/mnt/l`) and UNC paths in all outputs, envelopes, and reports.

---

## 2. Stateful Mock Compliance Engine (`TEST_MOCK_HARNESS=1`)
To verify the correctness of the test suite in an isolated environment, the suite defines a stateful mock layer when `TEST_MOCK_HARNESS=1` is present.
- **State Store (`MockState`)**: Maintains global lists of registered media sources, staged records, active confirmation tokens, vector index maps, and deleted files.
- **Client Replacement (`MockMiniAgentClient`)**: Implements:
  - Policy checks: Rejects mutating calls in offline profile, allows read-only and blocks mutating operations under agent failure.
  - Token generation: Generates isolated confirmation tokens with metadata (operation, timestamp).
  - Validation: Simulates UCF schema, temporal range bounds checks, spatial regions normalization, and payload flatness validation.
  - Sanitization: Runs regex-based path sanitization on all outcomes returned by client methods.
  - Vector checks: Blocks vector promotion attempts when the vector UUID has no matching staged UCF record.

---

## 3. Test Cases Architecture (4-Tier Approach)
The suite contains **50 distinct tests** divided into:

### Tier 1: Feature Coverage (Tests F1.01-05 to F4.01-05)
- **F1 (Gated Execution)**: Verifies command routing across profiles (safe, offline, unrestricted) and agent availability fallback behavior for custom ops.
- **F2 (UCF Validation)**: Verifies post-ingestion checks trigger automatically and block staging/promotion under failures.
- **F3 (Human-in-the-Loop)**: Verifies ingested records remain staged, automated promotion is blocked, and promotion requires valid token/confirm flags.
- **F4 (Path Sanitization)**: Verifies absolute local path redaction in outcomes, artifacts, and errors while preserving relative ones.

### Tier 2: Boundary & Corner Cases (Tests F1.06-10 to F4.06-10)
- **F1 Boundary**: Verifies profile case insensitivity, invalid profile fallback, unrecognized tool default blocking, and consistency.
- **F2 Boundary**: Verifies validation failure rules for unregistered media, temporal out of range, non-flat payload, schema mismatch, and unnormalized coordinates.
- **F3 Boundary**: Verifies expired tokens, token reuse prevention, token-operation mismatches, empty tokens, and confirmation without token.
- **F4 Boundary**: Verifies nested json path sanitization, empty/None values handling, lowercase drive letters, and natural text prompt preservation.

### Tier 3: Cross-Feature Combinations
- Collisions between offline profiles and agent failure.
- Sync checks during Qdrant/FAISS backfilling to prevent orphan vector injection.
- Sanitizing validation failure reports.
- Full validation and promotion handshake loop.

### Tier 4: Real-World Scenarios
- End-to-end happy path (ingestion -> stage -> validate -> confirm promote -> promoted status).
- Pipeline abort on schema failure.
- Path audit on local media drives.
- Concurrency isolation of tokens.
- Agent failure and recovery scenario.
