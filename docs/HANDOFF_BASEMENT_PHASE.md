<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Basement Phase Handoff (v1) — Current System State

**Status:** Basement phase sealed + truth plumbing sealed (read-only control substrate active).
**Scope:** Integrity + observability + contracts + read-only UI/control truth layers; no execution authority, no policy coupling.

---

## Current Restart Checkpoint (2026-05-07)

This is the practical handoff point for a brand-new Codex session.

- Pause checkpoint:
  - latest local docs-clearance commit: `103b17f` (`docs: add documentation forensics index`)
  - documentation clearance is sealed enough to proceed later from `docs/reference/indexes/DOCS_FORENSICS_INDEX.md`
  - all active Markdown/text docs under `docs/` carry explicit `DOC_STATUS` metadata
  - `docs/archive/diagnostics/wsl2_audio_emotion_sample_output.json` is preserved historical WSL audio emotion-output evidence, not current runtime authority
  - local `reports/control_recurrence/` artifacts remain workspace hygiene unless intentionally promoted
  - next operator input expected: laptop bootstrap audit with two remaining items; analyze that before resuming project-root cleanup
- Current local workspace head:
  - `main` / `origin/main` are the active source line; confirm the exact head with `git log -1 --oneline`
  - source includes WSL audio bootstrap noninteractive/cache hardening through `41230ab`
- Current public-facing branch head:
  - `public` / `origin/public` -> `e5cd974` (`fix: tighten recurrence attribution and audio payloads`)
- Full witness state now banked:
  - Season 1 recompare completed (`01x01`–`01x05`)
  - Season 2 fresh witness completed (`02x01`–`02x12`)
- Latest authoritative witness memos:
  - `docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md`
  - `docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md`
  - `docs/testing/SEASON1_SEASON2_FORENSIC_COMPARISON_MEMO_2026-04-25.md`
- Read-only operator layer is restored and should now be treated as active:
  - `lib/run_index.py`
  - `lib/run_summary.py`
  - `/api/runs/latest/preview`
- First safe control-agent substrate is active as read-only observability:
  - `lib/control_recurrence_report.py`
  - `lib/control_recurrence_index.py`
  - `lib/control_recurrence_recommendations.py`
  - `lib/control_recurrence_trend.py`
  - `python -m cli.control_recurrence_report`
  - `/api/control-recurrence/reports`
  - `/api/control-recurrence/reports/latest`
  - `/api/control-recurrence/reports/{report_id}`
  - `/api/control-recurrence/reports/{report_id}/markdown`
  - `/api/control-recurrence/reports/{report_id}/recommendations`
  - tag anchor: `control-recurrence-v0.4.2`
  - current-state capsule: `docs/releases/CONTROL_RECURRENCE_v0.4.2.md`
  - seal note: `control-recurrence-v0.4.1` remains a valid sealed milestone for direct-run discoverability and truth-surface alignment; current `main` is beyond it with `control-recurrence-v0.4.2` plus retry attribution/coalescing tightening
  - source state beyond the latest control-recurrence tag includes the read-only trend helper/CLI mode, the CLAP audio Qdrant payload provenance patch, native model smoke diagnostics, shared runtime recurrence scoping, and WSL audio runtime black-box diagnostics through `05ae539`
  - shared direct-run stdout events are scoped by persisted video/scene identity before recurrence aggregation
  - direct-run discovery is bounded by existing required artifacts; absent aggregate output, operator metadata, temporal paths, or resolved log paths produce limited/missing-artifact observability rather than a boundary violation
  - local `reports/control_recurrence/index.json` state is workspace artifact hygiene unless the file is explicitly tracked
  - release notes:
    - `docs/releases/CONTROL_RECURRENCE_v0.4.0.md`
    - `docs/releases/CONTROL_RECURRENCE_v0.4.1.md`
    - `docs/releases/CONTROL_RECURRENCE_v0.4.2.md`
    - `docs/releases/CONTROL_RECURRENCE_SHARED_RUNTIME_SCOPING_2026-05-03.md`
  - boundary: not healing yet. This tool/API does not activate `ControlAgent`, does not enable auto-healing, does not mutate configs, does not execute commands, does not use LLMs, does not generate reports from the API, and does not touch `cli/run_ingestion.py`.
- Current upstream normalization status:
  - exact-pair pilot only
  - allowlist contains exactly `Jerry Seinfeld -> Jerry`
  - instrumentation fields:
    - `normalization_applied`
    - `normalization_source`
  - pilot is projection-only and must not be generalized casually
- Current audio-vector success doctrine:
  - contract: `docs/architecture/AUDIO_VECTOR_PROVENANCE_CONTRACT.md`
  - current-run CLAP/Qdrant audio coverage requires `clap_meta.status == ok` plus a Qdrant audio payload with matching `run_id` and required provenance fields
  - scene-id-only Qdrant audio matches are stale or provenance-unverified, not current-run proof
  - one-episode baseline witness: `20260501_114445_audio_qdrant_provenance_02x01_witness` showed `40 / 40` CLAP ok scenes with current-run Qdrant provenance
  - two-episode boundary witness: `20260501_153532_audio_qdrant_provenance_s2_two_episode_witness` showed `75 / 75` CLAP ok scenes with current-run Qdrant provenance across `78` scenes; `2` optional CLAP errors and `1` `audio_silent` skip did not receive current-run Qdrant credit

If resuming after restart, do not begin with a broad rerun. Begin by reading the
three witness memos above and then confirm the current branch head.

### Project-Root Audit Pause Note (2026-05-07)

The docs-index-guided project audit is read-only complete enough to resume from
these findings:

- Validation passed: `python scripts/docs/doc_drift_lint.py`, `git diff --check`,
  and `powershell -ExecutionPolicy Bypass -File scripts/dev/run_pytest.ps1 -q`
  (`493` passed, `5` warnings).
- Tracked source state was clean; the only expected local workspace artifacts
  were untracked recurrence report files under `reports/control_recurrence/`.
- Active docs lint clean. Archive docs still contain historical drive-root
  examples by design and remain non-authoritative.
- Qdrant answered locally. WSL audio preflight returned ready with diarization
  ready, while the sourced worker still reported the observed cu128 drift lane
  and `torchcodec_ready=false`.
- Desktop cache readiness still reported the three current PyAnnote repos as
  missing from the Windows model cache; treat that as a local readiness watch
  item until bootstrap/model prefetch evidence refreshes it.
- Incoming laptop bootstrap audit confirmed `--yes` no longer hangs and model
  prefetch reaches `18 / 18`, but surfaced a final WSL diarization gate caused
  by CRLF in generated Hugging Face `refs/main` and `.goodq_env` artifacts; the
  matching patch writes those generated files as LF-only UTF-8 bytes.
- Repo-root cleanup seam completed: the `17` tracked `steps/*/step.py.backup_*`
  files beside active step modules were removed from the active tree after
  audit showed no active runtime/test consumers. `*.backup*` is ignored to
  prevent recurrence.
- Repo-root config seam completed: the retired root `config.json`
  scene-detection override and its obsolete fixer/monitor helper scripts were
  removed after reference checks showed canonical runtime config is
  `configs/config.yaml` via `steps.common.config_loader`.
- Script registry status: `docs/bootstrap/SCRIPT_REGISTRY.md` is a stale
  generated audit aid, not runtime authority. Canonical script surfaces remain
  root launchers, bootstrap installer/validator/model prefetch, interpreter
  bindings, `cli.run_ingestion`, watchdog, and the unified WSL bridge.
- Test boundary status: default pytest is bounded to `tests/unit`; broad
  explicit collection such as `pytest .` can still wander into retired
  `scripts/archive/legacy_validation/root/test_*.py` harnesses.
- Next source seam, after cleanup triage: silent observability/provenance drops
  in observer, memory commit events, retrieval events, provenance attachment,
  API status probes, and audio helper paths.

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
- **Primary logs for audits:** epoch `logs/step_runs.jsonl`, epoch `processing/<video>/`, and the WSL worker output/workspace.
- **WSL audio black-box recorder:** `bridge_runtime_probe` is expected on unified WSL audio scene outputs and canonical scene-manifest scene audio payloads. The 2026-05-04 witness `20260504_074335_wsl_black_box_02x02_witness` proved all `38` scenes carried it; the active sourced worker reported `torch_lane_status=differs_from_expected` and `torchcodec_ready=false` while Phase 6/Qdrant remained healthy.
- **WSL audio lane classification:** `WSL_AUDIO_LANE_OBSERVED_FUNCTIONAL_DRIFT_CU128`. Bootstrap target remains `torch` / `torchvision` / `torchaudio` on `2.5.1+cu121`; the observed sourced WSL worker lane is `2.8.0+cu128`. That lane was functionally observed through repeated no-ingestion probes and no current ingestion blocker was found from the witness, but it is not bootstrap-approved, not lane-approved for promotion, and not a package recommendation. `torchcodec_ready=false` remains a watch item; promotion requires a future explicit lane-promotion audit before any bootstrap, config, package, source, or lockfile change.

---

## Current Watch List (Known Ongoing Issues)

- **Intermittent WSL2 audio unified failures:** some scenes have extracted audio chunks (`Processing: scene_XXXX.wav`) but WSL2 processing returns an error (often alongside benign stderr warnings); treat this as *audio-present processing failure*, not “no audio”. Start investigation at `scripts/wsl2_audio_bridge.py` + `wsl2_audio/process_audio.py` and confirm the extracted `.wav` exists/has non-trivial size in the epoch `processing/<video>/audio/` tree.
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
- **Schema definitions (TypedDict):** `steps/common/canonical_sensitive_events.py`
- **UI-safe empty reserved conduits:** `cli/conduits_sensitive_sources.py`
- **Vault token resolver contract:** `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Vault token resolver hook:** `steps/common/vault_token_resolver.py`
- **Sensitive staging validator hook:** `steps/common/sensitive_staging.py`

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

- **Chat ingestion:** CME schema + reserved conduits exist; no parsers/writers registered.
- **Health ingestion:** CHE schema + Health Auto Export adapter exist; pipeline wiring is blocked by default to avoid per-record PHI leakage.
- **Wearable ingestion:** CWE schema + reserved conduits exist; no ingestion; vault staging is mandatory before any future processing.
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
- `docs/goodq4all_agent_status.md`
- `docs/architecture/SYSTEM_MAP_v1.md`
- `docs/architecture/MEMORY_STORAGE.md`
- `docs/architecture/EPISTEMIC_READ_MODEL.md`
- `docs/architecture/NON_ACTION_CONTRACT.md`
- `docs/data_epochs.md`
- `docs/testing/SEASON1_RECOMPARE_WITNESS_MEMO_2026-04-24.md`
- `docs/testing/SEASON2_FIRST_CHECKPOINT_MEMO_2026-04-25.md`
- `docs/testing/SEASON1_SEASON2_FORENSIC_COMPARISON_MEMO_2026-04-25.md`

### Verify active epoch + readiness (no ingestion)

- `python -m cli.print_config`
- `python -m cli.goodq_doctor`
- `.\LAUNCH_GOODQ.ps1 -DryRun`

### Build/refresh UI-safe conduits (no ingestion)

1) Build all conduit schemas:
- `python -m cli.conduits_build`

2) Build UI rollups (scene spine + modality coverage):
- `python -m cli.ui_conduits_rollup`
  - `scene_modality_coverage.has_audio_clap` is memory-commit presence only.
    Prefer `audio_vector_provenance_state` for UI status language; it is not
    current-run Qdrant proof unless the audio-vector provenance contract is
    satisfied.

3) Build observability rollups (optional; additive):
- `python -m cli.observability_rollup`
- `python -m cli.observability_rollup --commits`

### Run read-only control recurrence reports (no healing)

- Single-run recurrence summary:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness`
- Direct canonical run-root recurrence summary:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-root reports/fresh_ingest_runs/<direct_run_root>`
- Comparison JSON between witness roots:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --json`
- Deterministic markdown operator artifact:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness --write-md`
- Durable markdown + JSON artifacts and index update:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md --write-json-file`
- List indexed artifacts from the CLI:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --list-reports --json`
- Draft deterministic operator inspection recommendations from an indexed report:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --recommendations-for 20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness`
- Derive conservative trends from indexed durable JSON reports:
  - `conda run --no-capture-output -n goodq_core python -m cli.control_recurrence_report --trend --json`
- Read the existing index from the local API:
  - `curl http://127.0.0.1:30000/api/control-recurrence/reports`
- Read the latest indexed entry from the local API:
  - `curl http://127.0.0.1:30000/api/control-recurrence/reports/latest`
- Read deterministic inspection recommendations from the local API:
  - `curl http://127.0.0.1:30000/api/control-recurrence/reports/20260424_003250_season1_recompare_witness__vs__20260424_182406_season2_fresh_witness/recommendations`

This is read-only control-plane observability only. The CLI reads existing persisted artifacts (`step_runs.jsonl`, run warnings, `scene_ingest_results.json`, `scene_manifest.json`, `temporal_index.json`, and `experiment_log.json`). For direct canonical run roots without a wrapper ledger, it can also read existing `operator_run_metadata.json`, `output/scene_ingest_results.json`, `workspace/_resolved_config.json`, canonical `step_runs.jsonl`, and captured ingestion stdout/stderr events. Direct roots may contain one or more videos, and metadata-described output/workspace paths are read only when present. Recurrence reports include observer-only latency summaries from existing `step_runs.jsonl` `duration_ms` rows; those summaries do not alter recurrence classification or trigger remediation. It writes artifacts only when explicitly asked. Recommendation drafts read existing durable JSON reports and return inspection steps only. Trend mode reads only the recurrence artifact index and indexed durable JSON reports; it does not reconstruct trend data from markdown or raw run roots. The API reads only `reports/control_recurrence/index.json` and indexed artifacts. It does not generate reports, trigger ingestion, activate ControlAgent, execute commands, mutate configs, or heal.

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
- **Current pipeline/intelligence next step:** do not broaden normalization. The
  current safe pilot is a single exact pair only. New candidates must satisfy
  the same proof gate before implementation:
  - appears in at least `2` segments
  - across at least `2` scenes
  - no competing entity surfaces
  - no title/alias collision

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
- **Read-only control recurrence reports:** `cli/control_recurrence_report.py`, `lib/control_recurrence_report.py`, `lib/control_recurrence_index.py`, `lib/control_recurrence_recommendations.py`, `api/routes/control_recurrence.py`
- **Sensitive-source contracts:** `docs/architecture/CANONICAL_SENSITIVE_EVENTS.md`, `docs/architecture/VAULT_TOKEN_RESOLVER_CONTRACT.md`
- **Sensitive schema definitions:** `steps/common/canonical_sensitive_events.py`
- **Health adapter (dry-run):** `steps/health_auto_export/adapter.py`
- **Justification Channel UI:** `ui/justification_v1/`
- **Inspector v0:** `ui/justification_v1/inspector/`
- **Interpreter binding helpers:** `scripts/_lib/interpreter_bindings.ps1`, `scripts/_lib/interpreter_bindings.bat`
- **WSL2 audio bridge:** `scripts/wsl2_audio_bridge.py`, `steps/audio/audio_wsl2_bridge.py`, `wsl2_audio/`
- **Model pin/verify tooling:** `configs/model_registry.yaml`, `scripts/pin_model_versions.py`, `scripts/utils/verify_model_lockdown.py`
