# Retro Memory Explorer (v1.5.1)

Welcome to the **Retro Memory Explorer**, the operator-centric cognitive local-first visualization dashboard for GoodQ4All. This interface provides an interactive dashboard to explore ingested memories, audit semantic models, and trace epistemic evidence paths.

Served at: `http://127.0.0.1:30000/ui/retro_console_v1/`

---

## 1. Aesthetic Design Doctrine
The UI employs a premium, high-fidelity **cyber-CRT monitor** style:
* **Color Palette:** harmonious dark-mode base using deep blues and grays, with vibrant cyber-blue (`#00d2ff`) selection outlines and glow highlights.
* **Scanlines & Flickers:** Standby panels and images render with CSS-animated CRT flickering, raster lines, and a neon-green status indicator, reinforcing the hardware terminal aesthetic.
* **Transitions:** Smooth UI animations, fading splitters, and fluid canvas camera translation flights.

---

## 2. Interactive Workspace Architecture

The workspace is organized into a **four-panel resizable grid shell**:

```
+-------------------------------------------------------------+
|                     OPERATOR TOP INTELLIGENCE STRIP          |
+-------------------------------------------------------------+
| [ SEARCH PANEL ]     | [ MAP (CANVAS) PANEL ]               |
|                      |                                      |
| Text search, mode    | Entity co-occurrence network graph.  |
| selector (Text/      | Features pan, drag, and dynamic      |
| Visual/Audio/All),   | spacing zoom controls.               |
| suggestions.         | Supports 2D/3D dual layout modes.   |
|----------------------+--------------------------------------|
| [ TIMELINE PANEL ]   | [ INSPECTOR PANEL ]                  |
|                      |                                      |
| Chronological scene  | Detailed scene/entity metadata.      |
| cards, thumbnails,   | Image keyframe, transcript zone,     |
| and tag filters.     | and split-screen Data Trail logs.    |
+-------------------------------------------------------------+
```

### A. Search Panel
* Multi-modal query interface targeting vector indexes.
* Search options include: Text, Visual, Audio-Only, and All Modalities.
* Provides lexical suggestions dynamically pulled from the timeline's top entities and tags.
* Triggering a search zooms and highlights matching nodes on the graph map.

### B. Map (Canvas) Panel
The central entity co-occurrence graph visualized on an HTML5 `<canvas>` element.
* **Dual Display Layouts**: Supports toggling between a 2D Circular Map and an immersive 3D Spinning Globe via buttons on the bottom margin.
* **Immersive 3D Globe**: In 3D mode, nodes are mapped onto a spherical shell using a golden angle Fibonacci distribution.
* **Dynamic Spacing Zoom:** Spreads node coordinates apart dynamically on zoom rather than scaling the canvas rendering context (`ctx.scale()`). This keeps font rendering and icon lines razor-sharp without element bloating or overlapping, both in 2D and 3D.
* **Autopilot Zoom Flight:** Selecting a node triggers a smooth camera flight animation centering and focusing on the target entity. In 3D mode, the autopilot automatically rotates the sphere so the selected entity faces directly towards the viewer on the front hemisphere.
* **Momentum Spin Physics**: Left-click dragging on empty canvas space in 3D mode rotates the globe. On release, it preserves mouse movement velocity for inertia-based momentum spinning, slowly decelerating into a gentle ambient drift rotation.
* **Depth Perception Sorting (Painter's Algorithm)**: Sorts nodes by depth before drawing, ensuring closer nodes overlay further ones. Far-side edges and nodes fade out, and text labels hide when `rotatedZ < -10` to avoid layout clutter.
* **Interaction Hooks:**
  * **Single-click:** Selects the target entity and centers/focuses it. In 3D, only front-facing nodes can be selected to prevent accidental back-side selection.
  * **Deselect:** Double-click any node or click on empty canvas to clear the selection state.
  * **Drag & Pan:** Left-click and drag the canvas to pan (in 2D) or spin the globe (in 3D). Mouse scroll-wheel zooms in/out.

### C. Timeline Panel
* Displays scene-level cards in order of timestamp.
* Renders keyframe thumbnails, timestamps, text transcripts, and tag chips.
* Interlocks with the **Entity Checklist Filter**: checking multiple entities narrows the timeline display incrementally (AND logic).

### D. Inspector Panel
Displays detailed fields for the selected element:
* **Keyframe Image & Overlay:** Displays the scene's keyframe at the top, embedded with a cyan timecode overlay.
* **Standby Scanner:** When no scene is selected, it shows a CRT diagnostic animated scanning line.
* **Transcript Zone:** Renders the transcript text directly below the keyframe image, keeping transcripts readable without excessive scrolling.
* **Entity Mode:** When inspecting an entity rather than a scene, the keyframe and transcript sections hide, allowing entity details to occupy the full panel height.
* **Split Data Trail Section:** Uses an interactive subsection splitter. The logs terminal can be resized or collapsed independently.

---

## 3. Resizing & Responsive Layouts
All panels are separated by hoverable splitter bars.
* **Layout Controllers:** Dragging a splitter modifies grid flex metrics dynamically.
* **Panel Restoration:** Collapsing a panel down to 0% width hides it and spawns a floating restore tab at the screen border, allowing quick retrieval.
* **Canvas Resilience:** A `ResizeObserver` monitors changes to the canvas bounds and automatically updates graph configurations to prevent aspect-ratio stretching.

---

## 4. File Structure
The UI components are located in:
* `ui/retro_console_v1/index.html` — The semantic HTML5 workspace structure.
* `ui/retro_console_v1/static/css/retro.css` — Styling tokens, layout grids, CRT raster animations, and sizing limits.
* `ui/retro_console_v1/static/js/retro.js` — State machine, canvas math, event bindings, and API connectors.
