<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-26 -->

# GoodQ4All User Interface Walkthrough

GoodQ4All provides five specialized, local-first, read-only user interface consoles. Each is served directly by the FastAPI API process on port `30000` (or the configured override) and provides high-observability cockpit views of local system data, memory projections, and vector index spaces without offering any database-mutation or control-mutating capabilities.

---

## 1. Retro Memory Explorer (Cyber-CRT Console)
* **Access Route**: `http://127.0.0.1:30000/ui/retro_console_v1/`
* **Design Aesthetic**: Sleek cyber-CRT dashboard utilizing custom Google Fonts (Orbitron & Share Tech Mono), vivid phosphor-green (`#39ff14`) and cyber-blue (`#00d2ff`) glassmorphism grids, subtle screen scanlines, and flicker micro-animations.

### Layout & Features
* **Interactive 4-Panel Grid**: Collapsible, resizable quadrants:
  * **Search & Filter Panel**: Real-time query input. Autocomplete lists matching entity categories.
  * **Interactive Knowledge Canvas**: Uses Force-Directed Graph Layout. Double-clicking nodes triggers smooth transitions and centers the flight camera to the selected node.
  * **Inspector Panel**: Renders dynamic video keyframes and transcript overlays side-by-side with diagnostic log splitters.
  * **Chronological Checklist Panel**: Visual timeline showing processed scenes, VAD segments, and speaker attribution states.
* **Autopilot Zoom & Spacing**: Smart zoom coordinates separate close nodes dynamically without bloating shapes or overlapping text labels.

---

## 2. Classic Operator Console
* **Access Route**: `http://127.0.0.1:30000/ui/operator_console_v1/`
* **Design Aesthetic**: Modern clean diagnostics grid with vibrant status badges (provenance-green, warning-amber, error-crimson) and real-time dashboard widgets.

### Layout & Features
* **Current Scope Strip**: Top-level header identifying:
  * API Endpoint Port
  * Active Ingestion Run Source (e.g. `Direct CLI Output` or `Stitched Run`)
  * Temporal Range & Scene Count
  * Strict Audio Proof State (`Proven` vs `Unverified`)
* **Flight Deck**: Real-time telemetry monitoring GPU temperature, CUDA vram allocation, and CPU cores load.
* **Proof Panel**: Highlights missing vector matches, recovered exception counts, and pipeline execution logs.
* **Multimodal Retrieval Inspect**: Diagnostic search field letting operators execute hybrid text-visual queries and view detailed distance/similarity scores from Qdrant and FAISS indexes.

---

## 3. Stitching Workbench
* **Access Route**: `http://127.0.0.1:30000/ui/stitching_workbench/`
* **Design Aesthetic**: Table-based grid interface with contrasting row heights, dark modes, and audio waveform canvases.
* **Detailed Guide**: [`ui/stitching_workbench/README.md`](../../../ui/stitching_workbench/README.md)

### Layout & Features
* **Unstitched Voice Patterns List**: Highlights detected speaker segments from diarization steps that do not yet have a verified identity mapping.
* **Visual Waveform Overlay**: Displays VAD confidence intervals and allows inline listening to the voice segment.
* **Stitch Request Manager**: Deterministic human-in-the-loop (HITL) cockpit enabling operators to link voice clusters to verified people nodes in the Knowledge Graph. Action requests emit signed database mutations to `lib/identity_ledger.py`.

---

## 4. Summary Console
* **Access Route**: `http://127.0.0.1:30000/ui/summary_console/`
* **Design Aesthetic**: Premium flat dashboard layout featuring tabs, smooth slide transitions, and CSS chart modules.
* **Detailed Guide**: [`ui/summary_console/README.md`](../../../ui/summary_console/README.md)

### Layout & Features
* **PEOPLE Tab**: Renders connected user profiles, active voice signatures, and dialogue count statistics.
* **PLACES Tab**: Maps geo-locations and scene boundaries onto an interactive visual timeline.
* **MOODS Tab**: Renders mood maps, sentiment trends (from `steps/sentiment/`), and audio emotion summaries (neutral, happy, surprise, etc.) in clean interactive bar graphs.
* **OCCASIONS Tab**: Groups events and chronologically stacks key moments based on Phase 6 multimodal fusion.

---

## 5. Justification Channel
* **Access Route**: `http://127.0.0.1:30000/ui/justification_v1/`
* **Design Aesthetic**: Compact, high-contrast typography designed for audits and compliance verification.
* **Detailed Guide**: [`ui/justification_v1/README.md`](../../../ui/justification_v1/README.md)

### Layout & Features
* **Golden Render Envelope Viewer**: Displays raw, structured JSON response wrappers alongside their verification signatures to prove data provenance.
* **Epistemic Diff Comparator**: Comparative viewer displaying red/green structural diffs between two run outputs (`steps/common/epistemic_diff.py`).
* **Compliance Checks Panel**: Evaluates the active run against the *Non-Action Contract* (`steps/common/non_action_contract.py`) to confirm no telemetry or unauthorized modifications occurred.

---

## 6. Individual Interface Documentation Reference
For deeper context, visual rules, interaction hooks, and module bindings, consult the dedicated README files:
* **Retro Memory Explorer**: [`ui/retro_console_v1/README.md`](../../../ui/retro_console_v1/README.md)
* **Classic Operator Console**: [`ui/operator_console_v1/README.md`](../../../ui/operator_console_v1/README.md)
* **Stitching Workbench**: [`ui/stitching_workbench/README.md`](../../../ui/stitching_workbench/README.md)
* **Summary Console**: [`ui/summary_console/README.md`](../../../ui/summary_console/README.md)
* **Justification Channel**: [`ui/justification_v1/README.md`](../../../ui/justification_v1/README.md)
