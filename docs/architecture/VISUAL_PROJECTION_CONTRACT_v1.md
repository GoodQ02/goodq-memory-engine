<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# Visual Projection Contract (v1)

**Status:** ✅ Contract (read-only; projection semantics only)  
**Version:** 1  
**Scope:** Defines how existing epistemic truth structures are made spatially/visually *visible* for situational awareness.  
**Non-goals:** UI implementation, rendering/styling, animations, persuasion, summarization, recommendations, decision support, actions.

## Core Principle (Non-Negotiable)

**Visual projection must not add meaning.**  
It may only make *existing* meaning visible.

This contract therefore constrains projection to:
- preserve ordering and structure of source truth objects
- preserve absence, conflict, and limits as first-class signals
- remain non-destructive (no filtering/removal of truth)
- remain read-only (no state mutation outside view state)

## Cross-References (Authoritative)

- Epistemic states + `dont_know` semantics: `docs/architecture/EPISTEMIC_READ_MODEL.md`
- Declarative restraint (non-action): `docs/architecture/NON_ACTION_CONTRACT.md`
- Memory integrity + observability doctrine: `docs/architecture/MEMORY_STORAGE.md`
- Epoch isolation rationale (legacy preservation + clean starts): `docs/data_epochs.md`

## Terms

- **Projection**: A deterministic mapping from truth structures → spatial/visual presence.
- **Truth structures**: `EpistemicReadEnvelope`, `NonActionDecision[]`, and optionally `EpistemicDiff` outputs.
- **Presence semantics**: Rules describing *how something exists in the view* (visibility, continuity, fragmentation, emphasis), not style (colors/icons).
- **Focus**: Re-orienting the view around a selected item without removing other items.
- **Filter**: Removing/hiding items from the view (forbidden by this contract).
- **Epoch**: A discrete, non-mergeable data generation boundary (stores + processing root), treated as a first-class partition.

## Inputs (Authoritative)

Projection consumes **only** existing, already-sanitized, read-only structures:

1) **Epistemic envelope bundle**
- `EnvelopeBundle = { envelope, nonActionDecisions, sourceLabel, loaded_at_utc }`

2) **Comparative mode (optional)**
- `EpistemicDiff v1` computed from two bundles (A, B), per Comparative Understanding (structural diff).

Projection must not depend on:
- raw embeddings/vectors
- raw logs/transcripts
- absolute filesystem paths
- hidden heuristics or re-ranking

## 1) Projection Axes (Orthogonal, Non-Collapsing)

Projection space is conceptual. Implementations may map axes to x/y/z or panels, but must preserve axis semantics.

### A) Time Axis

**Purpose:** Make temporal structure visible without implying importance.

**Canonical time signals and their mapping rules:**
- **Scene ranges**: `scene.start` → `scene.end` map to a contiguous extent on the time axis.
  - MUST preserve scene order as given (no re-sorting).
  - MUST preserve adjacency/gaps (silence/unknown time remains visible as absence, not auto-collapsed).
- **Provenance timestamps**: `provenance.ts_utc` and `bundle.loaded_at_utc` MAY be mapped as secondary time markers.
  - MUST NOT be converted into numeric “freshness scores” for display.
  - MAY be expressed as categorical staleness presence (see Epistemic State Axis; no numbers).
- **Epoch boundaries**: epoch identity (from configured stores) MUST be represented as a discrete partition.
  - Cross-epoch content MUST NOT be visually merged as if it were the same continuity.
  - If both epochs are shown, they MUST coexist as parallel timelines or clearly separated partitions.

### B) Entity / Subject Axis

**Purpose:** Make “aboutness” visible: which scenes and evidence relate to which entities/subjects.

**Canonical subject signals:**
- Entity identifiers and references already present in envelope evidence payloads (sanitized).
- Scene identifiers (`video_id`, `scene_id`) as stable anchors when entities are absent.

**Mapping rules:**
- MUST be stable within a view session: the same subject key should not “jump” arbitrarily.
- MUST allow “no entities” as a valid state; scenes remain anchorable by `scene_id`.
- MUST avoid inventing entity groupings; only use declared/derived IDs already present.

### C) Epistemic State Axis

**Purpose:** Make support/conflict/unknown/absence visible as *presence semantics*, not as scores.

**Canonical epistemic signals:**
- Envelope-level: `outcome`, `state`, `limits`, `next_steps`
- Candidate-level: `candidate.state`, candidate evidence roles
- Evidence-level: `role` (`support` / `contradict` / `related` / `meta`), provenance presence/absence, confidence fields (informational only)
- Non-action: `NonActionDecision[]` (constraints must be visible)

**Mapping rule:** Epistemic state is a distinct axis; it must not overwrite time or subject axes.

## 2) Visual Presence Semantics (Not Style)

Presence semantics define how items exist in the view, without prescribing color, icons, typography, or animations.

### Presence semantics by epistemic state

**supported**
- MUST present as a single, coherent presence for the claim/candidate.
- MUST show explicit support evidence pointers.

**partially_supported**
- MUST present as incomplete/coarse presence with visible “missing” slots (absence is intentional).
- MUST show what is present and what is missing without collapsing either.

**conflicted**
- MUST present as multiple, non-resolved presences that coexist (e.g., split/fragmented/parallel).
- MUST not resolve or choose a “winner.”
- MUST surface the conflicting evidence pointers and associated limits/next steps (if present).

**unsupported_but_related**
- MUST remain visible but clearly non-affirming (peripheral/adjacent presence is acceptable).
- MUST not be promoted to support implicitly.

**unknown / dont_know**
- MUST present an explicit “unknown” presence rather than an empty screen.
- MUST show why it is unknown structurally (e.g., “no support evidence,” “provenance missing,” “blocked source”), without thresholds.

**absence (∅)**
- MUST be visible as reserved negative space / explicit missing slot, not an error state.
- MUST remain stable (no flicker/jitter caused by missing data).

### Explicit prohibitions

Projection MUST NOT:
- display numeric confidence values (including temporal) as numbers, bars, gauges, or rankings
- sort, rank, or score evidence or candidates beyond source-provided order
- infer or label “importance,” “improvement,” or “correctness”

## 3) Absence as First-Class Spatial Signal

Absence is never treated as a bug by default.

Projection MUST represent:
- missing modalities (e.g., no audio for a scene) as explicit absence slots
- missing provenance as explicit limits (e.g., “provenance_missing”) and an absence marker for provenance linkage
- blocked knowledge (Non-Action constraints) as an explicit boundary: “present but not permitted,” not “not present”

Absence MUST be:
- visible
- stable
- non-alarming (no implied error semantics)

## 4) Focus vs Filter (Critical)

Projection supports **focus**, and forbids **filter**.

### Focus (allowed)

Selecting a subject/scene/time window MAY:
- re-orient the view around the selection
- de-emphasize non-focused items
- reveal additional structural metadata (evidence roles, provenance pointers, limits)

Non-focused items MUST remain visible (at least as context silhouettes/slots).

### Filter (forbidden)

Projection MUST NOT provide “show only X” semantics that remove:
- non-focused entities
- unrelated scenes
- contradicting evidence
- unknown/absence markers

## 5) Interaction Grammar (Read-Only)

Allowed interactions are view-only transformations:

- **scrub**: move along the time axis (change time window / cursor)
- **pan**: translate the viewport across the projection space
- **zoom**: change scale (time granularity / spatial density), without removing content
- **lock-on**: set a focus anchor (entity/scene/candidate) while keeping context visible
- **compare**: enter comparative projection mode (A/B + diff)

Forbidden interactions (must not exist in v1):
- edit, delete, approve, trigger, resolve, retrain, ingest, export
- any control that initiates agent/tool actions or mutates stores

## 6) Comparative Projection Rules (EpistemicDiff v1)

Comparative projection makes *change* visible without claiming meaning.

### Coexistence (before/after)

- A and B MUST share the same conceptual axis definitions (time/subject/state).
- Unchanged regions MUST remain anchored (stable reference frame).
- Changed regions MUST be represented as explicit deltas, not as narrative summaries.

### Diff semantics (structural)

Projection MUST render diff categories as:
- **present_both**: category exists in A and B (even if unchanged)
- **present_a_only / present_b_only**: category exists only on one side, shown as explicit absence on the other side
- **absent_both**: category rendered as `∅` (explicit)

Projection MUST NOT:
- animate changes in a way that implies improvement/regression
- collapse multiple diffs into an interpretive sentence

## 7) Inspector Compatibility (Observer-Only)

If the GoodQ Inspector observes projection mode, it MAY record metadata-only view telemetry, including:
- view mode (`single` / `compare`)
- focus key (entity/scene/candidate identifier only; no payload text)
- time window bounds (if represented)
- diff summary counts and diff codes (in compare mode)

Inspector MUST NOT record:
- evidence bodies
- raw payload content
- transcripts
- file paths
- any derived “importance” or “quality” judgments

## 8) Non-Goals (Explicit)

Visual Projection v1 must not:
- persuade, summarize, recommend, or suggest actions
- “decide” what is correct
- suppress uncertainty, conflict, or absence
- couple confidence to policy or control
- provide decision support or approvals

## Prose Examples (Non-Implementational)

1) **Supported**
- A candidate answer has multiple `support` evidence hits with provenance pointers.
- Projection shows a coherent candidate presence anchored in time (scene extent) and subject (entity or scene_id), with support evidence visible as pointers.

2) **Conflicted**
- Evidence includes both `support` and `contradict` roles.
- Projection shows two coexisting presences (support vs contradict) anchored to the same time/subject region, without resolving them.

3) **dont_know**
- Envelope outcome is `dont_know` because no `support` evidence exists.
- Projection shows an explicit unknown presence, plus visible absence slots for missing evidence/modalities and any non-action decisions requiring `defer`.

4) **Comparative**
- Bundle A and B are compared.
- Unchanged scenes remain anchored; newly added evidence appears as an added presence on B with an explicit absence slot on A; removed evidence appears as a hole on B with the prior presence on A.
