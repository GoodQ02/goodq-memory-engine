<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-11-15 -->

# GoodQ4All User Interface Walkthrough

GoodQ4All serves six specialized, local-first user interface consoles directly from the FastAPI process on port `30000` (or the configured reader port). Inspection surfaces remain read-only by default, while explicit human-in-the-loop curation, summary, collection, and inbox-staging actions are gated behind `RouteEffectBoundaryMiddleware` and one-time confirmation tokens or bounded local-reader authorities.

When multi-movie saved libraries are configured (`ui.library_sources`), the combined reader on `:30000` aggregates catalog and saved-appearance views while routing movie-specific evidence, timelines, media streams, and collection-scoped queries via `?library_source=<id>`. If any configured collection reader is offline, consoles surface the `x-goodq-unavailable-sources` partial-library notice rather than silently presenting incomplete totals as complete.

---

## 1. Retro Memory Explorer (`/ui/retro_console_v1/`)
* **Access Route**: `http://127.0.0.1:30000/ui/retro_console_v1/`
* **Mutation Boundary**: Read-only memory exploration plus bounded local desktop playback (`/api/videos/{id}/play`) and explicit inbox file staging (`/api/ingest/upload`, `/api/ingest/path`) on the primary reader.
* **Detailed Guide**: [`ui/retro_console_v1/README.md`](../../../ui/retro_console_v1/README.md)

### Layout & Features
* **Workspace Activity Ribbon & Collection Switcher**: Switches across Explorer, Identity Curation tabs, Speaker Stitching, and Summary views while preserving the selected `library_source` collection context.
* **Dataset, Search & Drop Pad Controls**: Selects active or saved movie sources, runs multimodal/entity queries, and stages supported media into `import_inbox` for Watchdog processing.
* **Scene Grid, Knowledge Graph & Chronological Timeline**: Displays scene keyframes, OCR/caption/emotion badges, force-directed entity relationships, and temporal scene boundaries.
* **Scene Inspector & Transcript Speaker Evidence**: Displays stored `transcript_meta.segments` in order when their text covers the accepted scene transcript. Speaker labels remain unreviewed scene-local assignments unless backed by curated identity evidence; missing or inconsistent turn assignments render as **Unattributed** without fabricating speaker attribution.

---

## 2. Operator Console (`/ui/operator_console_v1/`)
* **Access Route**: `http://127.0.0.1:30000/ui/operator_console_v1/`
* **Mutation Boundary**: Strictly read-only diagnostic and forensic inquiry cockpit (`GET` status/evidence surfaces plus read-only `POST /api/search/multimodal`).
* **Detailed Guide**: [`ui/operator_console_v1/README.md`](../../../ui/operator_console_v1/README.md)

### Layout & Features
* **Guided & Operator View Modes**: Guided mode focuses on primary health, witness, proof, retrieval, and timeline panels while Operator mode exposes full storage, memory, engine, queue, and recurrence diagnostics.
* **Current Scope Banner & Witness Spine**: Identifies the active API endpoint, run source, temporal coverage, audio vector proof status, and any unavailable saved-library collections (`x-goodq-unavailable-sources`).
* **Flight Deck & Proof Panel**: Reports GPU memory reservation, optional model service states, WSL audio readiness, projection gap checks, and structured-run vs Qdrant inventory provenance.
* **Retrieval Console & Media Preview**: Runs per-collection multimodal queries (`Text`, `Visual`, `Audio`, `All`) with explicit collection-scope selection (`#retrieval-library-source`), confidence bands, match explanations, and sanitized keyframe previews.

---

## 3. Identity Curation Workbench (`/ui/identity_workbench/`)
* **Access Route**: `http://127.0.0.1:30000/ui/identity_workbench/`
* **Mutation Boundary**: Human-in-the-loop curation workbench. Draft edits, face/voice match confirmations, roster updates, and epoch-attested apply actions are governed by explicit preview/apply boundaries on the owning movie reader.

### Layout & Features
* **FACE CLUSTERS Tab**: Reviews candidate visual face clusters and representative crops for the active movie epoch.
* **SPEAKER HYPOTHESES & NAME MENTIONS Tabs**: Inspects diarized speaker turns and spoken transcript name cues alongside scene context and audio snippets.
* **FAMILY ROSTER Tab**: Manages canonical person entries used across face clustering, match review, and guarded vocabulary hints.
* **SCENE CONNECTIONS Tab**: Browses curated person appearances across the combined saved library (`/api/identity/appearances/saved`) or an isolated `library_source` collection, disabling offline collections explicitly.
* **MATCH REVIEW Tab**: Confirms or rejects suggested cross-movie face and voice matches, groups unmatched faces, scans reference faces across saved films, and previews/applies decisions to the target epoch.

---

## 4. Stitching Workbench (`/ui/stitching_workbench/`)
* **Access Route**: `http://127.0.0.1:30000/ui/stitching_workbench/`
* **Mutation Boundary**: Governed human-in-the-loop speaker stitching workbench emitting auditable updates through `lib/identity_ledger.py`.
* **Detailed Guide**: [`ui/stitching_workbench/README.md`](../../../ui/stitching_workbench/README.md)

### Layout & Features
* **Unstitched Voice Patterns List**: Surfaces diarized speaker patterns that do not yet map to a confirmed identity.
* **Waveform & Audio Evidence Review**: Plays scene-bounded audio segments and displays voice-activity intervals.
* **Stitch Request Manager**: Links verified voice clusters to canonical people entries in the Knowledge Graph with durable provenance.

---

## 5. Summary Console (`/ui/summary_console/`)
* **Access Route**: `http://127.0.0.1:30000/ui/summary_console/`
* **Mutation Boundary**: Read-only cumulative aggregation by default, with two-step `prepare` + one-time `confirmation_token` `confirm` governance for narrative video summary generation (`/api/summary/video/{id}/generate`) and custom collection creation/deletion (`/api/summary/collections`) within the owning reader's epoch.
* **Detailed Guide**: [`ui/summary_console/README.md`](../../../ui/summary_console/README.md)

### Layout & Features
* **Entity & Source Leaderboards (`PEOPLE`, `PLACES`, `OCCASIONS`, `MOODS`, `SOURCES`)**: Aggregates people, places, transcript/occasion cues, classified sentiment coverage, channel-qualified emotion evidence, and processed video/audio/image/document sources for the selected collection (`?library_source=...`).
* **Profile, Provenance & Narrative Summary Viewer**: Displays entity co-occurrences, scene spans, model/prompt provenance metadata, and durable action-job polling for video summary rewrites.
* **Built-In Highlights & Custom Collections**: Compiles positive/negative/gathering highlight playlists and saves epoch-bound custom scene collections after native operator confirmation.

---

## 6. Justification Channel (`/ui/justification_v1/`)
* **Access Route**: `http://127.0.0.1:30000/ui/justification_v1/`
* **Mutation Boundary**: Strictly read-only provenance and compliance verification surface served with local-only styles and fonts.
* **Detailed Guide**: [`ui/justification_v1/README.md`](../../../ui/justification_v1/README.md)

### Layout & Features
* **Render Envelope Viewer**: Inspects structured read-envelope payloads (`GET /api/read/envelope`) and provenance metadata.
* **Epistemic Diff Comparator**: Compares structural differences across run outputs (`steps/common/epistemic_diff.py`).
* **Compliance Checks Panel**: Evaluates runtime evidence against the Non-Action Contract (`steps/common/non_action_contract.py`).

---

## 7. Individual Interface Documentation Reference
For module-level implementation details, consult the component READMEs where present:
* **Retro Memory Explorer**: [`ui/retro_console_v1/README.md`](../../../ui/retro_console_v1/README.md)
* **Operator Console**: [`ui/operator_console_v1/README.md`](../../../ui/operator_console_v1/README.md)
* **Stitching Workbench**: [`ui/stitching_workbench/README.md`](../../../ui/stitching_workbench/README.md)
* **Summary Console**: [`ui/summary_console/README.md`](../../../ui/summary_console/README.md)
* **Justification Channel**: [`ui/justification_v1/README.md`](../../../ui/justification_v1/README.md)
