# SYSTEM_MAP_v1 — GoodQ (Authoritative System Map)

This document is an orientation and preservation artifact.
It describes what exists now, how the system is layered, where connections are allowed, and where “power” explicitly does not exist.

**Scope:** truth + restraint + observability + read-only plumbing. No roadmap.

---

## Basement / Integrity Foundation

### A) Purpose
- Establish the non-negotiable substrate: local-first persistence, deterministic runtime entry points, and audit-driven stabilization.

### B) Guarantees
- System identity is local-first and persistent (SQLite + KG + Qdrant are authoritative stores).
- Runtime behavior is governed by explicit contracts and “surgical change” norms.
- Sensitive sources are PHI-equivalent by doctrine (vault-only raw; derived-only outputs).

### C) Explicit Non-Goals
- No new architectures or redesigns.
- No implicit “helpful” refactors or cleanup passes.
- No policy coupling (nothing in this layer decides what to do with truth; it only preserves foundations).

### D) Connection Points
- **Frozen at tag:** `basement-v1.0.0`
- **Handoff/ground truth:** `docs/HANDOFF_BASEMENT_PHASE.md`
- **Core doctrines:** `docs/AGENTS.md`, `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/architecture/MEMORY_STORAGE.md`
- **Config authority:** `docs/architecture/CONFIG_LOADING_CONTRACT.md`, `steps/common/config_loader.py`
- **Sensitive source wiring (schema + vault rules):** `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`, `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Witness proof artifact:** `docs/proof_of_concept/WITNESS_RUN_001.md`

---

## Memory Integrity & Observability

### A) Purpose
- Make memory writes and reads visible, explainable, and auditable without changing retrieval behavior.

### B) Guarantees
- Writes are recorded as best-effort, append-only events (attempted/committed, per-target truth in targets).
- Reads can be annotated with provenance pointers derived from write events.
- Retrieval events are durably logged as inert observability (no policy use).
- Confidence is informational; temporal confidence is computed on read and is non-destructive.

### C) Explicit Non-Goals
- No reinforcement, decay policy, ranking changes, filtering, or refusal logic.
- No deletion/compaction of audit history as a “fix”.
- No raw query logging (privacy rule).

### D) Connection Points
- **Frozen at tag:** `basement-v1.0.0`
- **Write auditing:** `steps/common/memory_commit_events.py`
- **Read provenance threading:** `steps/common/memory_provenance.py`
- **Retrieval observability:** `steps/common/retrieval_events.py`
- **Debug gating:** `GOODQ_VECTOR_DEBUG` (used across memory/provenance/retrieval event emitters)
- **Witness validation:** `docs/proof_of_concept/WITNESS_RUN_001.md`

---

## Epistemic & Restraint Contracts

### A) Purpose
- Define the canonical, shared language of “what we know”, “what we don’t”, and “what we must not do” in structures that can be rendered without interpretation.

### B) Guarantees
- Epistemic output is represented as an EpistemicReadEnvelope contract (states, evidence roles, limits, next steps).
- Non-action is a first-class, explicit outcome via a declarative contract (returns decisions; no enforcement).
- Contracts are stable, versioned artifacts intended to prevent drift across UI, agents, and pipelines.

### C) Explicit Non-Goals
- No enforcement wiring (contracts return structure only).
- No thresholds, scoring, or truth adjudication.
- No prompt rewriting or LLM policy changes in the contract layer.

### D) Connection Points
- **Epistemic Read Model frozen at tag:** `basement-v1.0.0`
  - Contract: `docs/architecture/EPISTEMIC_READ_MODEL.md`
  - Formatter (non-authoritative): `steps/common/epistemic_formatter.py`
- **Non-Action Contract frozen at tag:** `non-action-v1.0.0`
  - Contract: `docs/architecture/NON_ACTION_CONTRACT.md`
  - Evaluator (pure): `steps/common/non_action_contract.py`
  - Tests: `tests/unit/test_non_action_contract_smoke.py`

---

## UI Truth Layer (Justification Channel)

### A) Purpose
- Render epistemic truth and restraint literally, in a text-first, order-preserving inspection view.

### B) Guarantees
- Output order is preserved (no sorting/filtering); absence is rendered explicitly (∅).
- Integrity harness validates invariant violations (paths/transcripts/health-value leakage) and fingerprints evidence order.
- Golden render test ensures the canonical text output does not drift.
- State transitions are explicit and immutable (no partial mutation).

### C) Explicit Non-Goals
- No actions, no commands, no ingestion triggers, no training triggers.
- No API calls unless explicitly in the read-only wiring layer (below).
- No interpretive UI metaphors (no gauges, no “better/worse” indicators).

### D) Connection Points
- **Frozen at tags:** `justification-ui-v1.0.0`, `justification-ui-v1.0.2`, `justification-ui-v1.0.3`
- **Comparative Rendering v1 (UI) frozen at tag:** `justification-diff-ui-v1.0.0`
- Visual Projection Contract v1 frozen at tag visual-projection-v1.0.0.
- **Implementation:** `ui/justification_v1/index.html`, `ui/justification_v1/static/js/app.js`
- **Integrity harness:** `ui/justification_v1/static/js/integrity.js`
- **Golden test:** `ui/justification_v1/static/js/test_render.js`
- **Input contract mirrors (docs-only):** `ui/justification_v1/static/js/types_epistemic.js`, `ui/justification_v1/static/js/types_non_action.js`

---

## Observation Layer (GoodQ Inspector v0)

### A) Purpose
- Record a metadata-only, append-only audit trail of UI state transitions and diagnostics to make regressions diagnosable by inspection.

### B) Guarantees
- Observer-only: logs only counts + warning codes + order fingerprint; no envelope text, no evidence content, no paths.
- Disabled by default; explicitly enabled by local flag or query param.
- Best-effort persistence: bounded buffer; file logging only in Node/Electron-like contexts.

### C) Explicit Non-Goals
- No suggestions, no fixes, no actions, no network calls.
- No persistence requirements in browser contexts (in-memory only is acceptable).

### D) Connection Points
- **Frozen at tag:** `goodq-inspector-v0.1.0`
- **Implementation:** `ui/justification_v1/inspector/inspector.js`, `ui/justification_v1/inspector/README.md`
- **Integration points:** called from `ui/justification_v1/static/js/app.js` on state transitions + diagnostics updates

---

## Read-Only Wiring (Truth Plumbing v1)

### A) Purpose
- Prove that the UI can consume real epistemic bundles from real sources without gaining power (read-only data flow only).

### B) Guarantees
- Source switching is explicit (example / local JSON / read-only API) and always goes through immutable state transitions.
- Failures are rendered honestly as `outcome=dont_know` plus a `NonActionDecision(required_response="defer")` (structural explanation only).
- The backend endpoint is strict read-only: returns a precomputed envelope bundle; accepts no queries/commands.

### C) Explicit Non-Goals
- No chat input, no free-form queries, no agent actions, no write endpoints.
- No ingestion/training/repair operations.

### D) Connection Points
- **Frozen at tag:** `justification-readonly-v1.0.0`
- **UI loaders:** `ui/justification_v1/static/js/app.js` (query params: `source`, `path`, `api_base`)
- **Backend endpoint:** `api/main.py` (`GET /api/read/envelope`)
  - Source bundle path: `GOODQ_READONLY_ENVELOPE_PATH` (environment variable)

---

## Comparative Understanding (Epistemic Diff Engine v1)

### A) Purpose
- Compare two EpistemicReadEnvelopes structurally (what changed) without implying correctness, improvement, or resolution.

### B) Guarantees
- Pure and deterministic: no I/O, no mutation, no logging.
- Diffs are structural only: outcome, candidate states/order, decisions, evidence presence/order (no content), limits, next steps.
- Absence is explicit via category presence states; diffs include summary counts for inspector/UI use.

### C) Explicit Non-Goals
- No scoring, ranking, correctness inference, or resolution advice.
- No persistence or UI rendering.

### D) Connection Points
- **Frozen at tag:** `epistemic-diff-v1.0.0`
- **Implementation:** `steps/common/epistemic_diff.py`
- **Tests:** `tests/unit/test_epistemic_diff_smoke.py`
- **Inputs/outputs:** compares two EnvelopeBundles → returns EpistemicDiff v1 object

---

## System Invariants (Do Not Violate)

- The system must never act (tools/agents/side effects) without epistemic justification and an explicit restraint check.
- Non-action is a valid, explicit outcome (refuse/defer/dont_know/silent), not a failure mode.
- Confidence is informational, never policy.
- Absence of data is a first-class signal; it must be representable and renderable as ∅.
- Read-only surfaces must not mutate state.
- Observability is inert: logs/events must not silently become policy inputs.
- Privacy is binding: do not log raw queries; do not surface raw sensitive content; do not leak absolute paths into UI-safe layers.
- “Committed” is per-target truth; store-level truth lives in targets metadata (do not treat a single boolean as universal truth without context).
- Identity is composite; do not assume embedding IDs or scene IDs alone are sufficient for joins across stores.

---

## Intentionally Deferred Capabilities

- **Execution authority / tool actions:** deferred until an enforcement layer exists that consumes Epistemic + Non-Action structures without bypass.
- **Agent autonomy:** deferred until agents are strictly constrained to read-only and contract-checked action plans with explicit human approval pathways.
- **Training / fine-tuning / dataset export:** deferred because sensitive sources are vault-only and exports require explicit manifests + human approval.
- **Live sensor ingestion (wearables/health/chat):** deferred pending adapters and staging rules that guarantee no raw content leaks into memory/KG/UI conduits.
- **Narrative / persuasive output:** deferred to avoid “sounding confident” without evidence; future presentation layers must remain evidence-first and contract-bound.
