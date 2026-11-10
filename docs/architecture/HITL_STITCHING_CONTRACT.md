<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-10-26 -->

# HITL Stitching Contract

**Purpose:** Define the mutation, persistence, and evaluation contracts for human-in-the-loop (HITL) identity stitching in GoodQ.
**Scope:** Manual mapping structures, status transitions, preview/confirmation logic, and safe read-model rebuilds.
**Non-goals:** Ingestion pipelines, scene or timeline file rewrites, Qdrant updates, or automated routing policies.

---

## Core Invariants

1. **Additive Evidence Only (No Destructive Merges):**
   * Manual mappings are treated as operator-provided evidence edges in the Knowledge Graph, never as destructive node merges.
   * Original anonymous nodes (`speaker`, `face`, `speaker_pattern`) and original `person` nodes must never be deleted, renamed, or collapsed.
   * The structural timeline and scene records are immutable raw source signals.

2. **Conflict Visibility:**
   * Manual mappings may dominate read-model resolution (e.g., in ledger summaries), but they must not erase or delete underlying conflicts.
   * Modality contradictions and name mismatches must remain queryable in the raw graph database.

3. **Reversibility (`status=revoked`):**
   * Manual mappings must never be deleted from the persistent record.
   * To reverse a mapping, its status field in the persistent mapping JSON must be transitioned to `"revoked"`.
   * The ledger re-application engine must ignore any mapping with a status of `"revoked"`.

4. **Identity Stability:**
   * Names are display labels and subject to cleanup. Mappings must bind stable, unique structural node IDs (e.g., node names/IDs) and target `person` node names/IDs.

5. **Mutation Safeguards:**
   * All operator writes require a two-stage transaction:
     1. **Preview (`confirm=false`):** Simulates the mapping addition, checks for existing conflicts, and lists the affected scenes and episodes.
     2. **Commit (`confirm=true`):** Persists the mapping, updates the SQLite graph database, and triggers ledger updates.
   * Operator Console v1 remains strictly read-only. Retro Console browsing is
     read-only except for its explicit governed request-staging pad; that pad
     does not perform identity mutation or direct ingestion execution.
   * Any mutation UI or stitching features must reside in a clearly separate Identity Stitching workbench.

6. **Rebuild Boundaries:**
   * A rebuild action triggered by manual stitching is strictly limited to refreshing the identity ledger (`identity_ledger.py`) and the SQLite database read-model.
   * Rebuilds must never trigger fresh media ingestion, Qdrant vector store updates, or timeline/scene JSON file rewrites.

---

## Schema Specification

Manual mappings will be persisted in a versioned JSON document located in the epoch data directory:
`<GOODQ_DATA_ROOT>/epochs/<epoch_id>/manual_identity_mappings.json`

### Mapping Entry Schema

```json
{
  "version": 1,
  "mappings": [
    {
      "mapping_id": "map_2026_05_24_0001",
      "source_node_type": "speaker_pattern",
      "source_node_name": "voice_pattern_02_1988_1989_speaker_1",
      "target_person_name": "Joe",
      "status": "active",
      "history": [
        {
          "status": "active",
          "timestamp_utc": "2026-05-24T17:00:00Z",
          "operator_note": "Identified speaker as Joe via scene 3 diaper scene"
        }
      ]
    }
  ]
}
```

---

## API Lifecycle

### Appearance connections from saved face groups

The Identity Curation Workbench also supports a separate appearance-only flow:

- `GET /api/identity/appearances/saved` browses persisted appearance edges, with
  an optional exact `person_id`. It excludes retired scenes, mentions and voice
  links and does not prepare a preview. Saved graph names and observation IDs
  remain independent of pending roster edits; unavailable face images stay
  visibly unavailable. Ambiguous source containment has no playback target.
- The workbench's People → Scenes → Watch path uses these saved connections and
  the existing scene reader. Explorer validates the epoch, person, source and
  scene before selecting its existing original-media player. A stale or missing
  link fails visibly instead of selecting another scene. Return restores the
  person/scene selection and waits for scoped desktop playback dismissal; it
  never stops a different playback owner. No search or inference is invoked.
- `GET /api/identity/appearances/preview` reads the saved roster, labeled face
  groups, exact promoted face evidence and graph scene authority. It creates no
  receipts or graph rows. A face must resolve to one saved scene. The preview
  includes every target observation, person/scene counts and shared aliases held
  for review. All transcript mentions and voice links are excluded.
- `POST /api/identity/appearances/apply` takes the reviewed `plan_sha256` and the
  normal single-use confirmation token. Its scope binds the epoch, graph path
  digest and request digest. Under the roster/label locks and a graph write
  transaction, it recomputes the preview and refuses changed inputs. It only adds
  missing curated `Person` / `FaceCluster` nodes and appearance/group edges;
  conflicting existing facts are not overwritten. Appearance confidence remains
  candidate, preserving the distinction between a user label and recognition quality.
- The same SQLite transaction records the exact inserted rows in
  `identity_appearance_receipts`. Repeating an applied plan creates no duplicate
  rows. `GET /api/identity/appearances/history` reads durable applied/undone status.
- `POST /api/identity/appearances/undo` uses a separately confirmed receipt ID and
  receipt digest. It removes only this receipt's additions, refusing edited rows
  or later dependent edges. Pre-existing people, scenes and connections remain.
  The receipt is retained as `undone`; it is never deleted.

This flow uses the existing capitalized curated identity projection, distinct
from manual voice stitching and its `manual_identity_mappings.json`. It never
changes labels, roster facts, original scene/face/speaker nodes, source media,
transcripts, vectors or the ingestion pipeline. The legacy roster `confirmed`
field is not an additional face-readiness gate. The whole-identity CLI remains a
separate broader operation and is not called by the workbench Apply action.

### Individual face review from frozen comparisons

Match Review provides Correct / Incorrect / Unsure for the displayed named
reference. Correct identifies that observation; Incorrect rejects that pairing
without naming another person; Unsure remains unresolved. Choices are browser-local
drafts keyed by epoch, report ID and report content digest until Apply. The v2 key
preserves the original Confirm/Hold draft and refuses stale-tab overwrites. Existing
positive selections migrate to Correct. A completed earlier batch can carry its
remaining faces as `not_accepted`, explicitly reviewed with wrong-versus-uncertain
unspecified. This does not invent individual negatives or require another full review.
Voice/mention evidence stays held. A human can recognize a below-threshold face
without changing the original score or cutoff. Choosing an alternative person is
not yet supported.

`POST /api/identity/matches/preview` is passive despite accepting a JSON selection.
It checks the immutable report, configured reference roots, unchanged roster and
labels, reference promotion/retirement, media hashes, exact destination face/time/
box and promoted scene/movie authority. Conflicting simultaneous identities or
already assigned observations are refused. Preview accounts for each decision,
groups Correct observations into person/scene links, and shows the explicitly
approved reusable-example count. A completed batch must account for every face.
No draft or graph rows are written.

The existing `POST /api/identity/appearances/apply` accepts the preview digest and
optional `match_review` selection. The same single-use authority binds all choices
to the destination epoch/store. It rechecks the plan inside the graph transaction,
adds stable `Person` nodes and appearance edges only, and retains original face IDs,
report/reference IDs, scores and human-review provenance. Further reviewed faces
can extend an existing appearance without discarding earlier evidence or facts.
The receipt records inserted rows and before/after properties for extended edges.
Existing Undo restores only those additions, refusing later edits/dependencies.
The receipt also persists Incorrect, Unsure and carried-forward non-acceptance
decisions, including reviews with no Correct faces. Later reviews of the same
batch must be undone first. Changing a saved Correct decision or withdrawing its
reuse requires Undo. Names, source groups, frozen predictions, media, vectors and
voice mappings remain unchanged.

### Reusing confirmed faces

`reuse_confirmed_faces` is explicit in both preview and confirmed request. Only
Correct observations in an applied receipt with that permission become examples.
The receipt binds the stable roster ID, exact face ID, scene, report, source hash,
saved pixels, bounding box, timestamp, encoder space and saved encoding digest.
The example is read from existing promoted evidence; no inference or embedding
rebuild occurs. Incorrect decisions are scoped feedback about the displayed pair,
not automatically generalized negative training data. Unsure, legacy non-acceptance,
unreviewed observations, group members and predictions never become examples.

Normal ingestion's `prepare_matching` / `load_reference_catalog` reads eligible
receipts in configured reference epochs and additional `identity_matching.reviewed_face_sources`
epoch roots. The latter need no duplicate roster or face-group labels: the original
roster still owns person IDs. Each example requires its active reviewed appearance
edge and exact promoted source evidence. Changed receipts, pixels or encodings fail
visibly; retired scenes are excluded. Undo revokes admission. Future review refuses
a frozen proposal whose reusable reference authority has changed. Previously
frozen comparison reports and run catalogs remain historical evidence, unchanged.

### 1. `GET /api/system/identity/unstitched`
* Scan the knowledge graph database for `speaker_pattern` nodes that lack any active `identity_supported` or `identity_evidence` mappings.
* Return list of unstitched patterns with duration, distinct active `scene_count`,
  selected speech-turn `segment_count`, and sample transcript excerpts. A voice
  signature can aggregate multiple turns; missing selected-turn provenance yields
  a null count, displayed as Unknown. Legacy `occurrence_count` remains a graph
  observation statistic and must not be labeled as scenes.

### 2. `POST /api/system/identity/stitch/preview`
* Accept mapping parameters: `{ "source_node_name": str, "target_person_name": str }`.
* Perform dry-run evaluation:
  - Find the source node in SQLite.
  - Resolve the target `person` node.
  - Scan the graph for existing mappings to the same source.
  - Return: `{ "success": bool, "affects": { "scenes": int, "episodes": int }, "conflicts": [...] }`.

### 3. `POST /api/system/identity/stitch`
* Accept same mapping parameters as preview plus: `{ "confirm": bool, "operator_note": str, "confirmation_token": str | null }`.
* Reject immediately if `confirm != true`.
* The real authority returns a 403 `needs_confirmation` envelope with a scoped,
  single-use token on preparation. After operator confirmation, the stitching UI
  resubmits the same mapping payload with that token. Other failures must remain
  visible; they must not trigger an unguarded write or automatic retry.
* Update `manual_identity_mappings.json` with the new entry (or update an existing one if it was previously revoked).
* Insert an `identity_evidence` edge in `knowledge_graph.db` with properties `{"source": "operator_manual_override", "weight": 1.0}`.
* Re-run `identity_ledger.py` evaluation to refresh read-model metrics.

### 4. `POST /api/system/identity/stitch/revoke`

* After operator confirmation and a justification note, the workbench prepares
  `identity.revoke_stitch` with the exact mapping ID, then submits that same body
  with the returned scoped single-use token. Failed confirmation is not retried;
  duplicate submissions are blocked while a revocation is pending.
* Revocation appends history and removes only the matching manual identity edge.
  Anonymous patterns, raw speakers, scene links and original evidence remain.

### Scene metrics in Summary

People/place leaderboards expose distinct active scene membership as `scene_count`;
profile counts reflect the deduplicated scene playlist. Shared identity paths do
not multiply scene or co-occurrence counts. Historical occurrence and node-time
fields remain compatible but are not used as scene counts or profile spans.
Profile **Scene coverage** uses persisted playlist bounds within one source. For
multiple source clocks the UI points to individual scene spans instead of merging
unrelated timestamps. Scene coverage is not a claim of continuous speech.
