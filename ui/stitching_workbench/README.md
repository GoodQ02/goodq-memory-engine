# GoodQ Identity Stitching Workbench (v1.0.0)

Welcome to the **GoodQ Identity Stitching Workbench**, the Human-in-the-Loop (HITL) manual override cockpit for speaker pattern consolidation and ledger mapping. This surface provides a deterministic verification workspace to promote raw voice patterns to verified people entities in the SQLite Knowledge Graph.

Served at: `http://127.0.0.1:30000/ui/stitching_workbench/`

---

## 1. Aesthetic Design Doctrine
The workbench adheres to a high-observability terminal design:
* **Color Palette:** Deep gray-black (`#0a0a0c`) base with high-contrast cyan (`#00d2ff`) headers, green status badges, and yellow warning overlays.
* **Blinking Warn Rails:** High-visibility banner warns operators: `⚠️ MUTATION WORKBENCH ACTIVE — OPERATOR WRITE MODIFICATIONS WILL REBUILD LEDGER GRAPH READ-MODEL IN REAL-TIME`.
* **State Blockers:** Rebuild states lock interaction screens with a spinning modal indicating background SQLite graph update tasks.

---

## 2. Interactive Workspace Architecture

The UI is divided into a **three-column layout**:

```
+-----------------------------------------------------------------------------+
|                  MUTATION WORKBENCH ACTIVE WARNING STRIP                    |
+-----------------------------------------------------------------------------+
| [ UNSTITCHED PATTERNS ]  | [ STITCHING MODULE ]    | [ MAPPINGS LEDGER ]    |
|                          |                         |                        |
| Search/filter list of    | Detail cards,           | Complete log of active |
| unmapped speaker voices, | transcripts, autocom-   | and revoked overrides  |
| occurrence metrics, and  | plete target, notes,    | with custom note       |
| transcript snippets.     | and preview trigger.    | tooltips and revokes.  |
+-----------------------------------------------------------------------------+
```

### A. Unstitched Speaker Patterns List (Left Column)
* Renders a list of all speaker profiles discovered during audio diarization (`steps/audio_diarize/`) that do not map to a named entity in the ledger.
* Displays occurrence count (scenes), total voiced duration (nicely formatted to seconds or minutes), and segment count.
* Integrates a filter input to search speaker tags and sample transcripts in real-time.

### B. Stitching Operator Module (Middle Column)
Provides the active form workspace:
* **Selected Pattern Card**: Displays detailed metrics and a sample transcript excerpt block for the selected pattern.
* **Target Person Input**: Real-time autocomplete suggestions populated from known ledger identities (e.g. `Joe`, `Charlie`, `Tony`).
* **Operator Audit Note**: Mandatory justification field requiring operators to record why the stitch is being made.
* **Preview Trigger**: Promotes the operator to the confirmation modal.

### C. Stitched Mappings Ledger (Right Column)
* The history trail showing all recorded speaker-to-person mappings.
* **Status Badges**: Clearly distinguishes active mappings (green) from revoked overrides (amber).
* **Revocation Cockpit**: Allows operators to cancel mappings inline, prompting for a revocation justification note and rebuilding the database graphs.

---

## 3. Two-Stage Transaction Enforcer (Safety Modal)
To prevent accidental database mutations:
1. **Stage 1 (Preview)**: Submitting the stitching form calls `/api/system/identity/stitch/preview` to check for graph conflicts and calculate exact impact (count of affected scenes and episodes).
2. **Stage 2 (Commit)**: Renders confirmation statistics, warnings, and the audit note. Clicking "Confirm" calls `POST /api/system/identity/stitch` with `confirm: true` to commit the signed mutation transaction to the identity ledger.

---

## 4. Serving & File Structure
* `ui/stitching_workbench/index.html` — The structural layout and crt-screen container.
* `ui/stitching_workbench/static/css/stitching.css` — Flex grid coordinates, warning animations, and layout cards.
* `ui/stitching_workbench/static/js/stitching.js` — State manager, auto-complete Suggest, API connector, and modal handlers.
