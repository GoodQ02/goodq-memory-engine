# GoodQ Justification Channel (v1.0.0)

Welcome to the **GoodQ Justification Channel**, the specialized text-first, truth-preserving epistemic envelope and decision comparator UI. This surface is designed strictly for verification, audits, and compliance audits to show exactly why a model retrieved, filtered, or refrained from taking actions.

Served at: `http://127.0.0.1:30000/ui/justification_v1/`

---

## 1. Design & Core Philosophy
The Justification Channel is built under strict constraints:
* **Text-First Layout:** Monospace typography designed to render exact evidence details without stylistic bias, filtering, or ranking modifications.
* **No Mutations:** Read-only surface. It does not contain any options to ingest data, heal configurations, or write queries.
* **Integrity Harness:** Integrates standard FNV-1a32 order fingerprints to trace evidence-sequence preservation.

---

## 2. Interactive Workspace Modes

The UI supports two main operating modes:

### A. Inspection Mode
Renders an `EpistemicReadEnvelope` alongside a `NonActionDecision[]` list:
* **Query block:** The question text asked by the operator.
* **Epistemic Summary:** Shows the query outcome (`answer` vs `dont_know`) and lists candidate answers.
* **Non-Action Decisions:** Shows rules evaluated by the non-action contract (`steps/common/non_action_contract.py`) to prove no telemetry or unauthorized actions took place.
* **Evidence Cards:** Detailed information for each candidate including stores (Qdrant/SQLite), similarity scores, sanitized payloads, and raw provenance metadata.
* **Limits:** Lists what data was missing or constrained during processing.

### B. Comparison (Diff) Mode
Toggled via query parameters (e.g. `?mode=compare&diff_source=file&diff_path=diff.json`) to render `EpistemicDiff` objects:
* **A / B sources:** Paths and load timestamps of the compared envelopes.
* **Identity Basis:** Indicates whether the two runs are entity-comparable.
* **Red/Green Comparator:** monospaced comparison showing exactly what was added, removed, or changed in outcomes, confidence values, or evidence metrics.

---

## 3. Keyboard Hooks & Hidden Diagnostics
* **Diagnostics Toggle (`D` Key)**: Pressing the `D` key overlays a diagnostic window showing live FNV-1a32 order fingerprints, read-model version tags, outcome counts, and validation checks.
* **Golden Renderer Smoke Test**: Load `test_render.js` and call `GoodQJustificationTests.run()` in the browser developer console to run the automated rendering integrity suite.
* **Observer Inspector**: Diagnostic logger logging UI transitions locally. Enable by setting `window.GOODQ_INSPECTOR_ENABLED = true` to log entries to `inspector_log.jsonl` (limited to 500 lines).

---

## 4. Serving & File Structure
* `ui/justification_v1/index.html` —モノスペース screen grid.
* `ui/justification_v1/static/js/app.js` — Core coordinator rendering text/comparison nodes.
* `ui/justification_v1/static/js/integrity.js` — Validation schemas and FNV-1a32 hash generators.
* `ui/justification_v1/static/js/test_render.js` — Automated golden tests.
* `ui/justification_v1/inspector/` — Passive logs recorder.
