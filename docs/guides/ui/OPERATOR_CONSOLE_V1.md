<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

# GoodQ4All Operator Console v1

The Operator Console v1 is a read-only local runtime surface for GoodQ4All. It
is intended for local operators who need to see runtime health, memory status,
latest run evidence, recurrence summaries, and video/timeline inventory without
gaining execution authority.

This is not a polished end-user product UI. It is an operator inspection layer.

## Flight Deck

The first console surface is the Flight Deck. It is a read-only cockpit view
that sits above the older overview cards and makes the operating model visible
before the data drilldowns.

The Flight Deck contains:

- System Map: launcher, API, watchdog, ingestion, SQLite, Qdrant, and Knowledge
  Graph status rows.
- First-Run Observer: import inbox count, watchdog visibility, processing queue,
  latest run age, and whether a first scene memory has been observed.
- Runtime Contract: profile, GPU, WSL2, audio backend, local API, and Qdrant
  addressability.

The Flight Deck must never guess. Unknown process state, unexposed launcher
state, missing runtime profile, or unavailable endpoints must render as
`Not observed` instead of a healthy-looking value. The only action affordances
are read-only navigation links: open the latest run panel or view the first-run
guide.

## Proof Panel

The Proof Panel sits directly below the Flight Deck. It answers the operator
question: "Why do we believe the latest run is inspectable?"

The panel is a frontend-derived read model. It does not call a dedicated proof
endpoint and does not create a new source of truth. It derives coverage from:

- `GET /api/runs/latest/evidence`
- `GET /api/memory/stats`
- `GET /api/runs/latest/preview`

The `Evidence coverage` value is a coverage indicator over UI-safe observed
signals. It is not a confidence score and must not be described as truth
certainty. A signal counts as observed only when the existing API reports a
sanitized artifact, status, or count that proves the UI row.

The provenance gaps card must remain conservative. Current-run Qdrant audio
proof is shown as `Not exposed` until the API returns a current-run audio proof
contract. FAISS audio counts may be displayed as count-only signals, but they
must not be labeled as current-run proof.

Proof Panel actions are navigation only:

- open existing evidence surfaces
- open the selected timeline surface
- open local API docs

No export, explain, ingestion, report generation, or mutation controls belong
in this panel.

## Retrieval Console

The Retrieval Console sits below the Proof Panel. It is the first operator
surface where a user asks local memory a natural-language question.

The console uses the active canonical search surface:

- `POST /api/search/multimodal`

The proposed `/api/retrieval/query` and `/api/retrieval/explain/{scene_id}`
contracts are not active API surfaces on this line. Until dedicated retrieval
explanation endpoints exist, the console derives a conservative explanation
from the search response fields that are already returned:

- result score
- returned modality
- scene/video ids
- transcript, keywords, and objects when exposed
- provenance and confidence objects when exposed
- scene context fields when exposed

The search API now attempts a read-only temporal-index hydration pass after
vector retrieval. When a returned `scene_id` can be matched, the console may see
canonical timeline identifiers, full transcript text, object labels, audio
emotion, speaker continuity, and `scene_context_llm` fields for epochs that
persist them. Missing sentiment remains a real absence: the UI should show it as
not observed instead of inferring it from audio emotion.

The `Why This Matched` panel must not invent modality scores. A progress bar may
be rendered only when the selected result has an explicit score for the returned
modality. Missing or unproven signals must appear under `Missing Signals`
instead of being shown as a low-confidence score.

The Retrieval Console does not store raw queries in local storage, does not log
queries, does not trigger ingestion, and does not mutate memory. The only live
action is a read-only search request. `Advanced` and `Explain Match` are visible
future affordances but disabled until their backend contracts are explicit.

`Open in Scene Inspector` and `View Full Timeline` only change local UI
selection state for returned `video_id` and `scene_id` values. These buttons
must remain disabled when a search result uses an identifier that is not present
in the video/timeline inventory. Hydrated search results may enable this handoff
because the API returns the canonical timeline `video_id` instead of the vector
payload hash.

## Scene Inspector

The Scene Inspector sits below the video/timeline inventory. It is a selected
timeline-row readout for operators who need to see what one scene currently
exposes before building higher-level UI affordances.

The inspector is frontend-derived from:

- `GET /api/videos/{video_id}/timeline/full`

It does not call a scene mutation endpoint, export a manifest, explain a scene,
or request any reprocessing. Selecting a timeline row only changes local UI
state.

The inspector renders:

- Selected scene facts: scene id, time span, continuity key, speaker evidence,
  emotion/sentiment, and normalization state.
- Scene memory evidence: memory tags, tag provenance, time hints, visual
  caption, OCR text, OCR date candidates, and scene-present entities when the
  timeline API exposes them.
- Modality coverage: visual frame presence, visual embedding ids, visual
  caption, OCR text, object detections, transcript text, audio chunks, speaker
  identity, visible people, aligned mentions, sentiment, and temporal hints.
- Schema projection: scalar/array/object/empty field counts plus expected-field
  presence for the current timeline row.

Path-bearing values remain redacted. Representative frame pointers may be
reported as present, but the local path must not be displayed. This panel is a
schema visibility layer, not a canonical artifact owner.

## Location

- UI entrypoint: `ui/operator_console_v1/index.html`
- Styles: `ui/operator_console_v1/static/css/app.css`
- Runtime script: `ui/operator_console_v1/static/js/app.js`
- Existing truth-layer scaffold remains: `ui/justification_v1/`

## Launch

Start the local API:

```powershell
python -m api.server
```

Then open the same-origin console:

```text
http://127.0.0.1:30000/ui/operator_console_v1/
```

For static UI development, the public repo can also be served over localhost:

```powershell
python -m http.server 8000
```

Then open:

```text
http://127.0.0.1:8000/ui/operator_console_v1/
```

The default API base is:

```text
http://127.0.0.1:30000
```

When served by the API, the console uses the current origin as its API base.
The API base can also be provided explicitly:

```text
http://127.0.0.1:8000/ui/operator_console_v1/?api_base=http://127.0.0.1:30000
```

Optional read-only artifact roots:

```powershell
$env:GOODQ_RUN_REPORTS_ROOT="<local witness reports root>"
$env:GOODQ_CONTROL_RECURRENCE_REPORTS_ROOT="<local recurrence reports root>"
python -m api.server
```

These environment variables are only readers. They let a public clone inspect a
local witness/recurrence artifact tree without copying private logs into the
repository.

## Read-Only API Inputs

The console may consume these local read surfaces:

- `GET /api/status`
- `GET /api/health/summary`
- `GET /api/engines`
- `GET /api/gpu/stats`
- `GET /api/wsl2-status`
- `GET /api/queue`
- `GET /api/runs/latest/preview`
- `GET /api/runs/latest/evidence`
- `GET /api/memory/stats`
- `GET /api/control-recurrence/reports/latest`
- `GET /api/control-recurrence/reports/trend`
- `POST /api/search/multimodal`
- `GET /api/system/videos`
- `GET /api/videos/{video_id}/timeline/full`
- `GET /api/read/envelope`

## Boundary Rules

- No ingestion trigger.
- No reindex trigger.
- No config reload trigger.
- No ControlAgent activation.
- No report generation.
- No mutation buttons.
- No hidden execution path.

The console must not convert recommendations into action buttons. It may render
recommendations only as read-only inspection signals.

## Data Hygiene

The console treats local paths, files-read lists, stdout/stderr tails, raw
errors, and machine-specific evidence as local-only. Forward-facing cells must
redact or omit values that resemble absolute Windows paths, home-relative paths,
UNC paths, file URLs, or path-bearing keys.

`GET /api/runs/latest/evidence` is the preferred Operator Console source for
step-run, temporal-index, emotion/sentiment, and knowledge-graph rollups because
it returns sanitized counts and status fields instead of raw path-bearing
artifacts.

The diagnostics panels intentionally render only safe status/count fields from
engine, GPU, WSL, and queue probes. Path-bearing descriptions, raw WSL command
output, and local file lists remain omitted or redacted.

Use `docs/architecture/OUTPUT_SCHEMA_INVENTORY.md` as the UI-safe field
boundary. API preview surfaces are local read-only conveniences, not canonical
artifact owners.

## Relationship to Justification Channel

The Operator Console does not replace the Justification Channel. The console is
an overview and navigation surface. The Justification Channel remains the
literal read-only renderer for epistemic envelopes and restraint decisions.

The console links to `ui/justification_v1/` with an explicit `api_base` when an
operator wants the envelope inspection view.
