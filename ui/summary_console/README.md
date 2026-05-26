# GoodQ Summary Console (v1.0.0)

Welcome to the **GoodQ Summary Console**, the cumulative overview dashboard for browsing consolidated memories, entity networks, and sentiment metrics across ingested epochs. 

Served at: `http://127.0.0.1:30000/ui/summary_console/`

---

## 1. Aesthetic Design Doctrine
The console provides a flat, clean dashboard layout optimized for summary metrics:
* **Color Palette:** Deep dark backgrounds (`#0a0a0c`) with vibrant phosphor accents: green for positive indicators (`#00ff66`), gray for neutral status, and red/amber for negative sentiment signals.
* **Layout Controls:** Clean, responsive grid layout split into leaderboards, inspectors, and custom collections.
* **Visual Data Indicators:** Includes a real-time sentiment distribution bar displaying POS/NEU/NEG segments side-by-side.

---

## 2. Interactive Workspace Architecture

The dashboard is structured into a **three-panel grid**:

```
+-----------------------------------------------------------------------------+
| [ ENTITY LEADERBOARDS ]  | [ PROFILE & PLAYLIST ]  | [ COLLECTIONS LEDGER ] |
|                          |                         |                        |
| Tabbed lists:            | Detailed profile meta,  | Pre-compiled highlights|
| - PEOPLE                 | co-occurrence tag cloud | (Positive, negative,   |
| - PLACES                 | for navigation, and the | gatherings) and custom |
| - OCCASIONS              | scene timeline cards.   | operator save folders. |
| - MOODS (Sentiment/Emo)  |                         |                        |
+-----------------------------------------------------------------------------+
```

### A. Entity Leaderboards (Left Column)
Features a tabbed sidebar for navigating global metrics:
* **PEOPLE**: Renders indexed people nodes sorted by scene frequency.
* **PLACES**: Lists visited geographic and context locations.
* **OCCASIONS**: Identifies Phase 6 multimodal fusion milestones and events with confidence indicators.
* **MOODS**: Displays global sentiment balance ratios (POS/NEU/NEG percentages) and the top emotional tags (neutral, happy, sad, etc.) mapped to scenes.

### B. Profile Inspector & Playlist Viewer (Middle Column)
* **Metadata Card**: Inspects active entities, showing occurrence count, type badges, and temporal span ranges (first/last seen).
* **Interactive Tag Cloud**: Renders co-occurring entity associations. Clicking any tag immediately pivots the profile inspector to that entity and updates the playlist timeline.
* **Playlist Timeline**: Lists cards for all scenes featuring the inspected node, showing video titles, exact timecodes, dialogue transcripts, and keyframe thumbnail image previews.

### C. Collections Ledger (Right Column)
* **Built-in Automated Highlights**: System pre-compiled playlists for positive moments, negative moments, and gatherings featuring three or more people.
* **Operator Custom Overlays**: Durable playlist folders compiled and saved by the operator.
* **Save / Delete Mechanics**: Operators can save their active playlist view via the `SAVE AS COLLECTION` form or soft-delete obsolete collections using inline control triggers.

---

## 3. Serving & File Structure
* `ui/summary_console/index.html` — Tab layouts, modals, and metric components.
* `ui/summary_console/static/css/summary.css` — Flex structures, tag design rules, and sentiment progress bar styling.
* `ui/summary_console/static/js/summary.js` — Core coordinator fetching stats, mapping collections, handling clicks, and saving custom entities.
