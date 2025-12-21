# Non-Action Contract (v1)

**Status:** ✅ Contract (declarative; no enforcement wiring)  
**Version:** 1

## Purpose

GoodQ must have a formal, testable definition of when it must **not**:
- answer (LLM output)
- ingest (pipeline registration/execution)
- train/export datasets
- act (agent/tool actions)

This contract is a **guardrail layer**, not a policy engine:
- No thresholds or scoring rules
- No runtime enforcement yet
- Pure evaluation only (returns decisions; does not block execution)

## Cross-References (Authoritative)

- Epistemic envelope + states: `docs/architecture/EPISTEMIC_READ_MODEL.md`
- Memory integrity doctrine (confidence is not policy; audit absence is not evidence): `docs/architecture/MEMORY_STORAGE.md`
- Sensitive source wiring + vault rules: `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`
- Vault token resolution (local-only): `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`

## Terms

### Domains

- `answer`: producing an answer response object (LLM output)
- `ingest`: accepting/running ingestion for a source
- `train`: generating/exporting a dataset or initiating training runs
- `act`: issuing agent/tool actions (including escalation)

### Required Response (declarative only)

- `refuse`: must not proceed (requires explicit change/approval)
- `defer`: must not proceed *yet* (prerequisites missing; stage/consent/manifest required)
- `dont_know`: must return a `dont_know` epistemic outcome (no claim)
- `silent`: must emit no response/action object (e.g., missing required context)

## Contract Structures (Code-Level)

Reference implementation (pure helpers only; no wiring):
- `steps/common/non_action_contract.py`

The contract defines:
- `NonActionCondition` (stable condition codes)
- `NonActionDecision` (domain + condition + required_response + machine-readable rationale)
- `NonActionContext` (minimal inputs; includes EpistemicReadEnvelope when applicable)

## A) Answering (LLM Output) — Non-Action Conditions

Structural (no thresholds):

1) **Missing epistemic envelope**
- Condition: `missing_epistemic_envelope`
- Required response: `silent`
- Rationale shape: `{missing: "epistemic_envelope"}`

2) **Insufficient derived evidence for a claim**
- Condition: `insufficient_evidence_shape`
- Required response: `dont_know`
- Trigger examples (structural):
  - Envelope says `outcome="answer"` but contains no `support` evidence hits.
  - Envelope says `outcome="answer"` but has no candidates.

3) **`dont_know` is required**
- Condition: `envelope_outcome_dont_know`
- Required response: `dont_know`
- Note: `dont_know` is a valid outcome, not a failure.

4) **Sensitive source requested without consent**
- Condition: `sensitive_source_without_consent`
- Required response: `refuse`
- Trigger example: request references `messages/health/wearables` and context indicates no explicit approval.

5) **Conflicting evidence without a resolution path**
- Condition: `conflict_without_next_steps`
- Required response: `defer`
- Trigger example (structural): candidate state is `conflicted` and provides no `next_steps` hints.

## B) Ingestion — Non-Action Conditions

1) **Blocked by design**
- Condition: `ingest_blocked_by_design`
- Required response: `refuse`
- Examples (non-exhaustive): chat ingestion not wired; health ingestion blocked by default; training export gated.

2) **Sensitive staging required**
- Condition: `sensitive_staging_required`
- Required response: `defer`
- Trigger examples:
  - Sensitive input is under vault root.
  - Sensitive input is not staged under `cfg['paths']['processing']`.

3) **Adapter missing**
- Condition: `ingest_adapter_missing`
- Required response: `refuse`
- Example: health export requested but no health-safe adapter is present for that format.

4) **Pipeline wiring disabled**
- Condition: `ingest_pipeline_not_registered`
- Required response: `refuse`
- Example: adapter exists but ingestion is intentionally not registered/available.

## C) Training / Dataset Export — Non-Action Conditions

1) **Vault manifest required for sensitive sources**
- Condition: `training_vault_manifest_required`
- Required response: `refuse`

2) **Explicit human approval required**
- Condition: `training_human_approval_required`
- Required response: `refuse`

3) **Mixed provenance sources**
- Condition: `training_mixed_provenance`
- Required response: `defer`
- Note: this is a structural flag; it does not define how to resolve mixing.

4) **Blocked by design**
- Condition: `training_blocked_by_design`
- Required response: `refuse`

## D) Agent / Tool Action — Non-Action Conditions

1) **Missing epistemic envelope**
- Condition: `act_requires_epistemic_envelope`
- Required response: `silent`

2) **Missing justification payload**
- Condition: `act_requires_justification_payload`
- Required response: `silent`
- Note: justification is a structured payload, not persuasive prose.

3) **Conflicted envelope state**
- Condition: `act_blocked_on_conflict`
- Required response: `defer`
- Trigger example: envelope contains a candidate with `state="conflicted"`.

## Notes

- This contract is intentionally conservative and incomplete-by-design: it enumerates **known** non-action conditions without claiming global completeness.
- Enforcement/wiring belongs to future policy/UI layers; this contract is the shared language those layers must follow.

