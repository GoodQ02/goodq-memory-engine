<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Basement Phase Handoff (v1) — Current System State

**Status:** Basement phase sealed + truth plumbing sealed (read-only).  
**Scope:** Integrity + observability + contracts + read-only UI truth layer; no execution authority, no policy coupling.

---

## A) Phase Scope

The “Basement Phase” established the non-negotiable foundation for GoodQ:
- **Memory Integrity v1:** auditable writes, explainable reads, and inert observability (no reinforcement/policy yet).
- **Epistemic representation:** a stable contract for how answers/evidence/limits are represented (schema + semantics).
- **Truth layer UI (read-only):** a deterministic Justification Channel that renders envelopes literally (no actions).
- **Comparative understanding (read-only):** structural diffs between two envelopes without implying correctness.
- **UI-safe conduits:** additive, whitelisted, path-sanitized derived tables/views for later UI/visualization layers.
- **Sensitive-source wiring:** schema + vault boundary contracts for chat/health/wearables (no ingestion).
- **Deterministic execution:** explicit interpreter binding for conda + WSL invocations (no PATH drift).
- **Model storeroom tooling:** pin/verify ML model revisions + hashes for offline-repeatable operation.

---

## Version Anchors (Tags)

- `basement-v1.0.0` — integrity foundation + observability + conduits + sensitive wiring + interpreter bindings + model tooling.
- `data-epoch-v1.0.0` — epoch isolation + safe launcher defaults (dry-run unless explicitly started).
- `non-action-v1.0.0` — Non-Action Contract v1 (declarative restraint; no enforcement).
- `justification-ui-v1.0.3` — Justification Channel v1 (literal renderer + safety substrate + navigation hardening).
- `goodq-inspector-v0.1.0` — GoodQ Inspector v0 (observer-only UI maintenance).
- `justification-readonly-v1.0.0` — Read-Only Wiring Phase v1 (explicit data sources; honest dont_know failures).
- `epistemic-diff-v1.0.0` — Epistemic Diff Engine v1 (structural comparison).
- `justification-diff-ui-v1.0.0` — comparative diff rendering (mode=compare; read-only).
- `visual-projection-v1.0.0` — Visual Projection Contract v1 (meaning-before-motion).
- `situational-projection-v1.0.0` — situational awareness projection (mode=project; read-only).
- `system-map-v1.0.0` — System Map v1 (authoritative orientation): `docs/architecture/SYSTEM_MAP_v1.md`.
- `wsl2-audio-bridge-v1.0.1` — WSL2 audio bridge syntax fix (f-string backslash).

---

## Runtime Snapshot (Operational)

- **Active epoch + stores:** `docs/data_epochs.md` + `configs/config.yaml` (`paths.*`, `qdrant.collections.*`, `phase6.*`).
- **Safe launcher default:** `LAUNCH_GOODQ.ps1` defaults to `-DryRun` unless `-StartIngestion` is explicitly passed.
- **No-audio vs processing failure (critical distinction):**
  - `  [OK] No audio track in video (video-only)` → no audio stream (`_extract_audio_chunk()` returned `None`).
  - `Processing: scene_XXXX.wav` followed by an error → audio exists; WSL2 processing failed (do not treat as “no audio”).
- **WSL2 audio components:** `steps/audio/audio_wsl2_bridge.py`, `scripts/wsl2_audio_bridge.py`, `wsl2_audio/process_audio.py`.
- **Primary logs for audits:** `logs/step_runs.jsonl`, `logs/scene_ingest/`, `wsl2_audio/logs/`.

---

## Current Watch List (Known Ongoing Issues)

- **Intermittent WSL2 audio unified failures:** some scenes have extracted audio chunks (`Processing: scene_XXXX.wav`) but WSL2 processing returns an error (often alongside benign stderr warnings); treat this as *audio-present processing failure*, not “no audio”. Start investigation at `scripts/wsl2_audio_bridge.py` + `wsl2_audio/process_audio.py` and confirm the extracted `.wav` exists/has non-trivial size in `logs/scene_ingest/.../audio/`.
- **Status pages can be stale:** `docs/goodq4all_agent_status.md` is a snapshot and may lag current tags; use `git tag --list` + `docs/HANDOFF_BASEMENT_PHASE.md` + `docs/architecture/SYSTEM_MAP_v1.md` for authoritative anchors.

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

### UI truth layer (read-only; invariant-safe)

- **Legacy UI archived:** `archive/legacy_ui/README.md`
- **Justification Channel v1:** `ui/justification_v1/` (literal renderer; no actions)
- **Integrity harness + golden test:** `ui/justification_v1/static/js/integrity.js`, `ui/justification_v1/static/js/test_render.js`
- **GoodQ Inspector v0 (observer-only):** `ui/justification_v1/inspector/`
- **Read-only wiring (explicit sources):** `justification-readonly-v1.0.0` (`GET /api/read/envelope` + local JSON loader)
- **Comparative diff UI (read-only):** `justification-diff-ui-v1.0.0` (mode=compare)
- **Situational awareness projection (read-only):** `situational-projection-v1.0.0` (mode=project; contract `docs/architecture/VISUAL_PROJECTION_CONTRACT_v1.md`)

### Comparative understanding (read-only diffs)

- **Epistemic Diff Engine v1:** `steps/common/epistemic_diff.py`
- **Tests:** `tests/unit/test_epistemic_diff_smoke.py`

### System Map (authoritative orientation)

- **Contract map:** `docs/architecture/SYSTEM_MAP_v1.md`
- **Witness proof:** `docs/proof_of_concept/WITNESS_RUN_001.md`

### Data epochs (preserved + isolated; local-first)

- **Epoch record + rules:** `docs/data_epochs.md`
- **Epoch-bound configuration:** `configs/config.yaml` (paths + Qdrant collection names are epoch-scoped)
- **Safe-by-default launcher:** `LAUNCH_GOODQ.ps1` (`-DryRun`, `-StartIngestion`)

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
- **Scope discipline:** agents must not modify files outside verified runtime entry points unless explicitly instructed.

---

## E) How To Resume Safely

### Orientation (read first)

- `docs/AGENTS.md`
- `docs/architecture/SYSTEM_MAP_v1.md`
- `docs/architecture/MEMORY_STORAGE.md`
- `docs/architecture/EPISTEMIC_READ_MODEL.md`
- `docs/architecture/NON_ACTION_CONTRACT.md`
- `docs/data_epochs.md`

### Verify active epoch + readiness (no ingestion)

- `python -m cli.print_config`
- `python -m cli.goodq_doctor`
- `.\LAUNCH_GOODQ.ps1 -DryRun`

### Build/refresh UI-safe conduits (no ingestion)

1) Build all conduit schemas:
- `python -m cli.conduits_build`

2) Build UI rollups (scene spine + modality coverage):
- `python -m cli.ui_conduits_rollup`

3) Build observability rollups (optional; additive):
- `python -m cli.observability_rollup`
- `python -m cli.observability_rollup --commits`

### Run the Justification Channel (read-only; no power)

- Open: `ui/justification_v1/index.html`
- Golden render check (browser console):
  - Load `ui/justification_v1/static/js/test_render.js` and run `GoodQJustificationTests.run()`
- Enable Inspector v0 (observer-only):
  - `?inspector=1` (or set `window.GOODQ_INSPECTOR_ENABLED = true` in console)
- Comparison mode (EpistemicDiff v1 renderer; read-only):
  - `ui/justification_v1/index.html?mode=compare&diff_source=file&diff_path=<relative_diff.json>`
  - Diff JSON must conform to EpistemicDiff v1 (output of `steps/common/epistemic_diff.py`)
- Load a local bundle (explicit):
  - `ui/justification_v1/index.html?source=file&path=<relative_bundle.json>`
  - Bundle shape: `{ "envelope": {...}, "nonActionDecisions": [...] }`
- Load from read-only API (explicit):
  - Set `GOODQ_READONLY_ENVELOPE_PATH` to a precomputed bundle JSON path
  - Run API: `python api/server.py` (default port `30000`)
  - Open UI: `ui/justification_v1/index.html?source=api&api_base=http://localhost:30000`

### Run Epistemic diff smoke tests (read-only)

- `python -m pytest tests/unit/test_epistemic_diff_smoke.py -q`

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
- **System map:** `docs/architecture/SYSTEM_MAP_v1.md`
- **Epoch tracking:** `docs/data_epochs.md`
- **Basement operating protocol:** `docs/AGENTS.md`
- **Launcher:** `LAUNCH_GOODQ.ps1`, `LAUNCH_GOODQ.bat`
- **Ingestion entrypoint:** `cli/run_ingestion.py`
- **Memory/observability core:** `steps/common/`
- **Epistemic diff engine:** `steps/common/epistemic_diff.py`
- **Conduit builders + rollups:** `cli/conduits_build.py`, `cli/ui_conduits_rollup.py`, `cli/observability_rollup.py`
- **Sensitive-source contracts:** `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`, `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Sensitive schema stubs:** `steps/common/canonical_sensitive_events.py`
- **Health adapter (dry-run):** `steps/health_auto_export/adapter.py`
- **Justification Channel UI:** `ui/justification_v1/`
- **Inspector v0:** `ui/justification_v1/inspector/`
- **Interpreter binding helpers:** `scripts/_lib/interpreter_bindings.ps1`, `scripts/_lib/interpreter_bindings.bat`
- **WSL2 audio bridge:** `scripts/wsl2_audio_bridge.py`, `steps/audio/audio_wsl2_bridge.py`, `wsl2_audio/`
- **Model pin/verify tooling:** `configs/model_registry.yaml`, `scripts/pin_model_versions.py`, `scripts/utils/verify_model_lockdown.py`
