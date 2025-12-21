# Basement Phase Handoff (v1)

**Status:** Basement phase sealed (integrity + observability + conduits + sensitive wiring).  
**Scope:** Administrative + contract + tooling hardening; no UI, no policy coupling.

---

## A) Phase Scope

The “Basement Phase” established the non-negotiable foundation for GoodQ:
- **Memory Integrity v1:** auditable writes, explainable reads, and inert observability (no reinforcement/policy yet).
- **Epistemic representation:** a stable contract for how answers/evidence/limits are represented (schema + semantics).
- **UI-safe conduits:** additive, whitelisted, path-sanitized derived tables/views for later UI/visualization layers.
- **Sensitive-source wiring:** schema + vault boundary contracts for chat/health/wearables (no ingestion).
- **Deterministic execution:** explicit interpreter binding for conda + WSL invocations (no PATH drift).
- **Model storeroom tooling:** pin/verify ML model revisions + hashes for offline-repeatable operation.

---

## B) What Is COMPLETE

### Memory Integrity v1

- **Audited memory writes:** `steps/common/memory_commit_events.py`
- **Audited retrieval hits (observability only):** `steps/common/retrieval_events.py`
- **Provenance threading:** `steps/common/memory_provenance.py`
- **Temporal confidence (read-time, non-destructive):** `steps/common/memory_provenance.py`
- **Doctrine:** `docs/architecture/MEMORY_STORAGE.md`

### Observability rollups (growth-safe, additive)

- **On-demand rollups:** `cli/observability_rollup.py` (`retrieval_events_daily`, `memory_commit_events_daily`)
- **Health report:** `cli/observability_health.py`

### Epistemic Read Model + formatter (integrity-only)

- **Contract:** `docs/architecture/EPISTEMIC_READ_MODEL.md`
- **Deterministic formatter (non-authoritative):** `steps/common/epistemic_formatter.py`

### Non-Action Contract v1 (declarative restraint; no enforcement)

- **Contract:** `docs/architecture/NON_ACTION_CONTRACT.md`
- **Pure evaluator (no wiring):** `steps/common/non_action_contract.py`
- **Note:** declarative only; enforcement is deferred by design; future UI/agents/pipelines must consult this contract.

### UI reset (clean slate prep)

- **Legacy UI archived:** `archive/legacy_ui/README.md`
- **Only supported UI direction:** `ui/justification_v1/` (scaffold only; consumes `EpistemicReadEnvelope`, `NonActionDecision`, and `_public` conduits)

### Conduit Pack v1 (UI-safe, whitelisted)

- **Builder:** `python -m cli.conduits_build` (`cli/conduits_build.py`)
- **Modules:** `cli/conduits_memory.py`, `cli/conduits_kg.py`, `cli/conduits_processing.py`, `cli/conduits_store_stats.py`
- **UI rollups:** `python -m cli.ui_conduits_rollup` (`cli/ui_conduits_rollup.py`)
- **Media ref token resolver (local-only):** `cli/media_refs.py`
- **Doctrine:** `docs/architecture/MEMORY_STORAGE.md`

### Sensitive Source Wiring Pack v1 (schema-only; no ingestion)

- **Contract:** `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`
- **Schema stubs (TypedDict):** `steps/common/canonical_sensitive_events.py`
- **UI-safe empty conduit stubs:** `cli/conduits_sensitive_sources.py`
- **Vault token resolver contract:** `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Vault token resolver stub:** `steps/common/vault_token_resolver.py`
- **Sensitive staging validator stub:** `steps/common/sensitive_staging.py`

### Health Auto Export adapter (schema-first; dry-run only)

- **Adapter module:** `steps/health_auto_export/adapter.py` (read-only; emits CHE objects; redacts raw values)

### Interpreter Binding Pack v1 (deterministic conda/WSL)

- **Shell helpers:** `scripts/_lib/interpreter_bindings.ps1`, `scripts/_lib/interpreter_bindings.bat`
- **Python conda resolution:** `steps/common/tool_paths.py` (used by `steps/common/conda_runner.py`)
- **WSL distro binding:** `GOODQ_WSL_DISTRO` (default `Ubuntu`) used by WSL entrypoints and scripts.

### Model storeroom (pinned + hashed; offline tooling)

- **Registry:** `configs/model_registry.yaml`
- **Pin revisions + hashes:** `scripts/pin_model_versions.py` (launcher: `scripts/PIN_MODEL_VERSIONS.bat`)
- **Verify lockdown:** `scripts/verify_model_lockdown.py` / `scripts/utils/verify_model_lockdown.py` (launcher: `scripts/VERIFY_MODEL_LOCKDOWN.bat`)

---

## C) What Is BLOCKED BY DESIGN

These are intentionally *not* wired into ingestion yet:

- **Chat ingestion:** CME schema + conduit stubs exist; no parsers/writers registered.
- **Health ingestion:** CHE schema + Health Auto Export adapter exist; pipeline wiring is blocked by default to avoid per-record PHI leakage.
- **Wearable ingestion:** CWE schema + conduit stubs exist; no ingestion; vault staging is mandatory before any future processing.
- **Training dataset export:** requires an explicit vault build manifest + explicit human approval; do not export raw or derived sensitive corpora by default.

---

## D) Safety & Invariants (Non-Negotiables)

- **Vault-only raw sensitive data:** raw message text / raw health values / raw wearable media must never appear in memory/KG/conduits by default.
- **Derived-only outputs:** only whitelisted, non-identifying derived fields may reach UI-safe conduits.
- **No raw queries in retrieval observability:** `retrieval_events` must never store raw user queries.
- **Confidence is not policy:** confidence fields are informational; no gating/reranking/refusal coupling without an explicit policy layer.
- **Audit absence is not evidence:** missing observability rows can be “disabled” or “best-effort dropped”.
- **Committed is per-target truth:** store-level truth lives in `targets_json`; row-level `committed=true` means all *attempted* targets succeeded.
- **Composite identity:** future joins must use `(store_type, store_ref, embedding_id)` when possible (avoid ID-only assumptions).
- **No implicit interpreter selection:** avoid `conda activate` and implicit `python`; use explicit conda exe + `conda run`.
- **WSL calls are distro-scoped:** use `GOODQ_WSL_DISTRO` and invoke `wsl -d <distro> -- ...`.

---

## E) How To Resume Safely

### Build/refresh UI-safe conduits (no ingestion)

1) Build all conduit schemas:
- `python -m cli.conduits_build`

2) Build UI rollups (scene spine + modality coverage):
- `python -m cli.ui_conduits_rollup`

3) Build observability rollups (optional; additive):
- `python -m cli.observability_rollup`
- `python -m cli.observability_rollup --commits`

### Run the Health Auto Export adapter (dry-run only)

- `python -m steps.health_auto_export.adapter <vault_or_staged_health_auto_export.json>`

This prints counts by category/name and a UTC date range. It does not write to databases.

### Verify model storeroom / offline readiness

- `scripts\\VERIFY_MODEL_LOCKDOWN.bat`
- (Optional) `scripts\\PIN_MODEL_VERSIONS.bat` (networked; updates pinned SHAs in `configs/model_registry.yaml`)

### Where to start next

- **UI work:** consume only UI-safe conduits (see `docs/architecture/MEMORY_STORAGE.md` “Conduit Pack v1”).
- **Sensitive ingestion:** start from the staging contract + vault resolver; do not run existing steps directly on vault paths.
- **Training/vault phase:** requires an explicit vault build manifest + explicit approval; keep vault boundaries intact.

---

## F) Key Directories & Files

- **Architecture + doctrine:** `docs/architecture/`
- **Basement operating protocol:** `docs/AGENTS.md`
- **Memory/observability core:** `steps/common/`
- **Conduit builders + rollups:** `cli/conduits_build.py`, `cli/ui_conduits_rollup.py`, `cli/observability_rollup.py`
- **Sensitive-source contracts:** `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`, `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Sensitive schema stubs:** `steps/common/canonical_sensitive_events.py`
- **Health adapter (dry-run):** `steps/health_auto_export/adapter.py`
- **Interpreter binding helpers:** `scripts/_lib/interpreter_bindings.ps1`, `scripts/_lib/interpreter_bindings.bat`
- **Model pin/verify tooling:** `configs/model_registry.yaml`, `scripts/pin_model_versions.py`, `scripts/utils/verify_model_lockdown.py`
