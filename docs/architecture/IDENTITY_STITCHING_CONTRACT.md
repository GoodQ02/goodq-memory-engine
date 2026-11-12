<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-11 -->

# Identity Stitching Contract

**Purpose:** define how GoodQ forms identity from audio, semantics, and scene evidence without hallucinating merges.  
**Scope:** speaker-pattern capture, candidate/support/evidence promotion, and explicit non-action rules.  
**Non-goals:** node merges, retrieval policy, UI behavior, or cross-run ranking logic.

This contract also does not define interaction-ownership fields such as `conversation_owner`. Those signals may summarize who an exchange revolves around, but they must not be treated as visual presence or identity promotion.

---

## Cross-References

- Epistemic evidence language: [EPISTEMIC_READ_MODEL.md](EPISTEMIC_READ_MODEL.md)
- Non-action guardrail language: [NON_ACTION_CONTRACT.md](NON_ACTION_CONTRACT.md)
- Memory integrity and persistence doctrine: [MEMORY_STORAGE.md](MEMORY_STORAGE.md)
- Canonical ingest authority: [INGEST_ORCHESTRATION_CONTRACT.md](INGEST_ORCHESTRATION_CONTRACT.md)

---

## Core Principle

Identity stitching is a convergence layer, not a guessing layer.

GoodQ may record that:
- a voice pattern is recurring
- a person name is recurring
- a face is recurring
- a speaker/person pairing is a candidate
- a conversation appears to revolve around a person

GoodQ must not claim identity merely because entities co-occurred in one scene.

---

## Definitions

### Structural identity

Structural nodes preserve raw modality truth without semantic overclaim:
- anonymous `speaker` nodes
- anonymous `face` nodes
- `speaker_pattern` nodes

These nodes may participate in identity edges, but they are not people.

### Semantic identity

Semantic identity is represented by `person` nodes resolved from transcript or visual entity extraction.

### `speaker_voice_signatures`

Per-speaker voice signatures emitted by the WSL audio worker from diarized speech spans.
New ECAPA signatures concatenate selected 16kHz mono spans, encode once, and
normalize the 192D result. They carry the pinned model revision and aggregation
version in `embedding_space`; untagged historical signatures remain legacy.

### `speaker_pattern`

A recurring voice-pattern node created from normalized speaker signatures when cosine similarity is strong enough to treat multiple scene-local speakers as the same recurring voice pattern.

### `voice_pattern_match`

An edge from a scene-local anonymous speaker node to a `speaker_pattern` node. This records recurring voice-pattern similarity only. It is not a person claim.

### `identity_candidate`

A weak, additive identity edge indicating that a structural node may correspond to a person under a narrow rule.

### `identity_supported`

A stronger additive identity edge indicating that the same candidate pattern repeated across multiple scenes without contradiction.

### `identity_evidence`

The strongest current identity edge in the stitching ladder. It indicates repeated, multi-episode agreement for a `speaker_pattern -> person` mapping without contradiction.

---

## Promotion Ladder

### Reusable ingestion comparisons

The optional `identity_matching` configuration supplies explicit read-only
reference sources (`epoch_root`, `identity_path`, `results_path`). Normal
`cli.run_ingestion` freezes these references before processing new media and
saves per-video comparison receipts under the destination epoch's
`identity_matching/` directory. Source epochs, labels, media and vector indexes
are never updated by comparison. The roster's stable person ID carries across
tapes; explicit group ownership may use a nickname different from the display name.

Face references are the operator-labeled representatives, not every inferred
member of a group. Voice references use compatible, pinned ECAPA patterns with
source-bound review clips. A name requires an active manual mapping and its
matching graph review edge; anonymous recurrence remains anonymous. Only like
embedding spaces/dimensions are compared. Scores are cosine similarities, not
identity probabilities. Default proposal thresholds reuse face cosine distance
0.4 (similarity 0.6) and the current ECAPA similarity 0.25, with a 0.05 margin;
these are review heuristics, not calibrated accuracy claims. Competing matches
and simultaneous observations are held. Invalid evidence is reported explicitly.

Frozen initial predictions cannot update their own references or create identity
edges. A repeated run receipt must match its original contents. The passive
`GET /api/identity/matches` reader and report/media routes expose these proposals
in the workbench with exact source imagery, original speech clips and scene
playback. Media paths are resolved only from a validated receipt within configured
source roots, with a content hash check. No comparison endpoint applies a name.
Future reviewed examples are admitted through the existing curated authorities;
reusing predictions as confirmed examples is prohibited.

Configured `reviewed_face_sources` allow both applied appearance-review face
observations (`reviewed_faces`) and roster-linked face cluster representatives from
epoch-attested sibling identity folders (`attested_cluster_faces`) across multiple
prior films to carry forward alongside `reference_sources` into `known_people`,
advisory cluster suggestions, cross-film scans, and match refreshes.
When operator curation advances in an earlier epoch after a later video has already
been ingested, governed `POST /api/identity/matches/refresh` (`refresh_epoch_matches`)
rebuilds that unapplied epoch's reference snapshot and comparison report against the
updated curated sources without re-ingesting media; already-applied reports cannot
be overwritten unless first undone.

Passive read-only curation helpers (`GET /api/identity/cross-film-scan`,
`GET /api/identity/cross-film-media/{epoch_id}/{detection_id}`, `known_people` on
`GET /api/identity/roster`, and advisory `suggested_matches` on
`GET /api/identity/face-clusters`) open source stores in read-only mode (`?mode=ro`),
honor UCF scene retirement, and never write graph edges or promote identity claims.
Sub-threshold cluster suggestions (`cosine >= 0.38` for `opencv-yunet-sface`, marked
`above_threshold: false` below the active policy cutoff) are operator labeling hints
only, never automatic proposals or graph assertions.

### 1. Voice -> Pattern

The WSL audio worker may emit `speaker_voice_signatures` only when speech is sufficiently stable:
- total voiced audio >= `4.0` seconds
- at least `2` usable segments
- each usable segment >= `0.75` seconds
- at most `4` selected segments are concatenated before one ECAPA encoding

If those conditions are not met, the worker must emit:
- `speaker_voice_signatures = []`
- `speaker_voice_signature_meta.status = "skipped"`
- `speaker_voice_signature_meta.reason = "insufficient_diverse_speech"`, or
  `"insufficient_unambiguous_speech"` when overlap exclusions leave insufficient speech

When a valid signature exists, GoodQ may:
- create a new `speaker_pattern`, or
- attach to an existing `speaker_pattern`

Current runtime match rule:
- cosine similarity >= `0.25` for the pinned ECAPA space, >= `0.92` for
  untagged legacy signatures. These are pattern assignment cutoffs, not identity
  probabilities. Compare/update centroids only within the exact same space.
- new pattern names include a space discriminator. Preserve historical vectors,
  IDs and identity mappings; no migration, backfill or automatic name transfer.
  Unknown/incomplete embedding tags fail visibly.
- preserve different diarization speaker labels within the same scene: a pattern
  already linked to another scene-local speaker is ineligible, including after
  reload. This conservative guard can preserve over-segmentation; it does not
  establish identity accuracy or prevent false matches across scenes.

This stage records recurring voice-pattern stability only.

Fresh signature admission excludes whole turns overlapping a different label
before ranking and rechecks the existing speech thresholds. Exclusions retain
their source times/reasons; `insufficient_unambiguous_speech` means no eligible
signature remained after exclusions. Unflagged speaker changes are not detected
by this policy, so remaining speech is not certified pure.

When the same-scene guard blocks a compatible ECAPA match, a
`possible_same_speaker` edge records a review candidate only. Keep the patterns
separate; do not merge centroids or infer a person from this edge. The unstitched
API and stitching workbench show the candidate and signature selection evidence.
Absent metadata on historical records does not establish clean speech.

### Governed promotion consumer

Approved promotion projects retained anonymous speaker evidence only for scenes
with promoted `speaker_merge` frames, into that epoch's actual KG/media nodes.
It reuses signature-space matching and same-scene separation; semantic candidate
accumulation and automatic manual-mapping transfer are outside this projection.
Human decisions retain the separate scoped review/confirmation route. Review flags
survive even when no eligible signature exists.

The scene's `promoted_speaker_projection_sha256` binds the applied speaker payload.
Identical replay does not add signatures again. Changed inputs require explicit
reconciliation and fail before active-view writes. Composed KG writes are atomic.
A replay with no new UCF transition reuses the durable delivery state; it does not
claim fresh vector verification or manufacture a completed receipt.

Live identity routes use WAL-aware read-only graph access so committed evidence is
immediately visible. Sidecar-free immutable reads remain for frozen snapshots.
This path performs no ingestion/model inference and does not qualify general
person search, cross-epoch retrieval or broader speaker-recognition accuracy.

### Reviewed voice in person search

The identity resolver may expose `voice` only from an active saved speaker-pattern
mapping with the matching operator_manual_override identity_evidence edge and
mapping ID, plus a voice_pattern_match / scene-local speaks_in chain. It must
recheck active review and graph evidence per query and apply retirement exclusions.
Candidate edges, transcript mentions, co-occurrence and revoked mappings are not
voice ownership. Exact unique roster display names may associate a reviewed voice
with a roster ID; aliases alone must not merge identity authorities.

Search carries appearance, voice and mention as distinct evidence_types; ranking
priority/boost must not turn voice into visible appearance. Retro labels reviewed
voice explicitly. The existing multimodal endpoint supports an exclusive People
mode (`modalities=["identity"]`) that reads saved identity evidence without query
encoding/model inference; the identity_search.enabled gate still applies. Resolved
source activity and retirement checks apply before returning a scene. Ordinary
multimodal search retains vector retrieval with bounded identity augmentation.
Identity-only results disclose that event relevance is unverified.

### Review-only collapsed speaker-change evidence

`speaker_change_review` is additive scene evidence, independent of signatures,
admission, pattern matching and identity promotion. Rule `collapsed_local_return_v1`
observes decoded exclusive local runs A-B-A that map to the same final cluster.
Overlap breaks the sequence; silence gaps are retained without a maximum-gap
threshold. Local slots are window-specific, not people. A missed local change or
a change without a return will not be detected by this conservative rule.

The worker observes reconstruction without changing its inputs/output and restores
the observer on exit. `status=ok` means evidence extraction succeeded, not that
speech is pure; `flags=[]` is not a clean-speaker certificate. Unsupported seams
yield `unavailable`; extraction failures yield `error` with a reason and preserve
ordinary diarization/signature processing. Historical/missing metadata means
unassessed, not a negative finding.

Each flag retains scene-relative start/end, supporting window, local slot sequence,
final cluster, silence gaps, `status=unreviewed` and `identity_claim=false`.
No exact person attribution or reviewed-boundary claim follows. Do not turn the
flag into signature exclusion, centroid changes, names or automatic splitting.

The bridge and identity ledger preserve the field; KG stores it on the scene node
even when no signature/pattern is emitted. GET `/api/system/identity/speaker-reviews`
reads this evidence for the stitching workbench's separate review section. The
face/identity workbench is not this consumer. No raw intermediate arrays are
required in the persisted payload, and no historical rewrite is performed.

Source integration and controlled caller/renderer checks are complete; deployment
and fresh/live-browser acceptance are separate. See [PROJECT.md](../../PROJECT.md)
for dated state and the bounded K2 evaluation, which does not qualify general
diarization accuracy. This section does not authorize deployment or new inference.

### 2. Pattern -> Candidate Person

GoodQ may emit `identity_candidate` for a `speaker_pattern -> person` mapping only when all of the following are true in-scene:
- exactly one named `person` node is present
- exactly one anonymous speaker is present
- no competing named speaker identity is present
- the speaker's own aligned excerpt contains the person name
- the speaker is dominant in the scene

Current runtime dominance rule:
- `dominant_share >= 0.6`

The candidate must carry evidence, not just a label:
- `scene_id`
- `video_id`
- `speaker_label`
- `voice_similarity`
- `voiced_seconds`
- `segment_count`
- `dominant_share`
- `transcript_excerpt`

Face-based candidate edges may also exist, but they remain weak scene-local hints.

### 3. Candidate -> Supported

GoodQ may emit `identity_supported` only after repeated agreement across scenes and only when the source has no conflicting stronger mapping.

Current runtime thresholds:
- scene-local anonymous `speaker` / `face` sources: >= `2` scenes
- `speaker_pattern` sources: >= `3` scenes

The promoted edge must persist:
- `supporting_scene_count`
- `supporting_scene_ids`
- `supporting_video_count`
- `supporting_video_ids`
- `supporting_evidence`
- `candidate_source`
- `evidence_strength`

### 4. Supported -> Evidence

GoodQ may emit `identity_evidence` only for `speaker_pattern -> person` mappings after multi-episode agreement.

Current runtime thresholds:
- >= `5` supporting scenes
- >= `2` supporting episodes
- no conflicting `identity_supported` or `identity_evidence` edge from the same structural source to a different person

This is the first stage that should be treated as durable cross-episode identity evidence, but it is still additive rather than merge-destructive.

---

## Evidence Rules

### Allowed evidence

The stitching layer may rely on:
- aligned speaker transcript excerpts
- repeated person-name alignment
- voice-pattern similarity
- voiced duration and segment diversity
- dominance within a scene
- repeated support across scenes and episodes

### Disallowed evidence

The stitching layer must not promote identity from:
- mere co-presence in a scene
- one-off mentions
- anonymous speaker labels alone
- anonymous face labels alone
- a single strong scene without repetition

### Ledger requirement

Every `identity_supported` and `identity_evidence` edge must be explainable through a scene-level evidence chain. The ledger projection may summarize this chain, but it must not invent missing evidence.

---

## Non-Action Rules

The stitching layer must not act when evidence shape is insufficient.

### No action from one scene alone

One scene may produce:
- `voice_pattern_match`
- `identity_candidate`

One scene must not produce:
- `identity_supported`
- `identity_evidence`

### No action from co-presence alone

If a person is merely present in the scene, but the speaker-aligned excerpt does not support that person name, no speaker identity candidate may be emitted.

### No action under ambiguity

If multiple named people are present and the system cannot isolate the speaking person, it must preserve structural nodes only.

### No action under conflict

If a structural source already has `identity_supported` or `identity_evidence` to a different person, new promotion must stop until contradiction is resolved.

### No action from weak audio shape

If speech is too short or not diverse enough to create a stable signature, the system must emit no speaker-pattern claim.

### No destructive merge

This contract does not authorize:
- replacing anonymous nodes with person nodes
- deleting candidate edges
- collapsing structural nodes into people

Uncertainty must remain visible.

---

## Success Condition

The stitching layer is behaving correctly when:
- `speaker_pattern` and `voice_pattern_match` accumulate before person claims do
- `identity_candidate` appears only in narrow, explainable cases
- `identity_supported` and `identity_evidence` remain zero when evidence is thin
- every promoted mapping can answer "why?" with scene-level support

Zero promotions is a valid outcome.

---

## Runtime Sources

Current runtime implementation lives in:
- `wsl2_audio/process_audio.py`
- `lib/kg_realtime_integration.py`
- `lib/identity_ledger.py`
- `lib/identity_matching.py`
- `api/utils/identity_cross_film.py`
- `api/utils/identity_read_projection.py`

This document describes the current contract those runtime surfaces are expected to preserve.
