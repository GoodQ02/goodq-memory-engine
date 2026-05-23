<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: WITNESS_RUN_SUMMARY -->
<!-- DOC_LAST_VERIFIED: 2026-05-22 -->

# Home-Memory Witness Run - 2026-05-22

## Purpose

Record the first broad redacted FAMILY home-memory validation run as a real
witness artifact. This report distills the load, persistence, proof, and
operator-console findings without exposing raw media paths, raw transcript
content, or private filenames.

## Witness Verdict

**Passed with visible, bounded follow-up.**

GoodQ4All completed a sustained local-first ingestion of one redacted
home-memory source, produced scene-centric memory across SQLite, Qdrant, FAISS,
temporal index, knowledge graph, sentiment, entity, and operator-console
surfaces, and left the system idle and inspectable afterward.

The remaining issues were not silent failures:

- one optional CLAP/audio-vector terminal error was visible in the step ledger
  and latest evidence route
- three content-dependent text/sentiment skips were visible and explainable
- four scene-context LLM gaps were later traced to fallback/eligibility seams
  and patched for future harmonization
- retrieval audio proof wording was later tightened so selected-scene proof is
  separated from collection-scope diagnostics

## Scope

| Field | Value |
| --- | --- |
| Epoch | `epoch_2026_05_22_family_full_01` |
| Runtime run id | `364f6a6b-37fb-4613-bf06-4c2099c9e6c8` |
| Source scope | first redacted FAMILY media file |
| Video count | `1` |
| Scene count | `141` |
| Temporal duration | `8801.459` seconds, about `2h 26m 41s` |
| Pipeline end state | idle |
| CLI progress bridge | completed, `100%`, non-active |

## Load Metrics

| Metric | Result |
| --- | --- |
| Step ledger rows | `2540` |
| Step rows ok | `2536` |
| Step rows skipped | `3` |
| Step rows error | `1` |
| Step success ratio | about `99.84%` of ledger rows |
| Wall-clock window | about `5.44` hours |
| Median step duration | `2943.459 ms` |
| P95 step duration | `51597.561 ms` |
| Max step duration | `343621.902 ms` |
| Runtime native step-error events | `6` |
| Recovered native step-error events | `5` |
| Terminal native step-error events | `1` |

Interpretation: this was a sustained local run, not a tiny smoke test. The
pipeline kept operating across thousands of step records, recovered from
multiple native subprocess failures, and preserved the remaining terminal
optional failure as inspectable evidence instead of hiding it.

## Memory And Proof Metrics

| Surface | Result |
| --- | --- |
| Current-run audio proof | `140 / 141` CLAP-ok scenes proven |
| Qdrant audio points | `140` |
| Qdrant text points | `281` |
| Qdrant CLIP points | `282` |
| Qdrant DINO points | `282` |
| FAISS indexes | audio, text, CLIP, and DINO all `IndexIDMap2` |
| SQLite projection | `141` scenes, `985` embeddings |
| Knowledge graph | `838` nodes, `2738` edges, `141` events |
| Projection gaps | `0` missing |

Interpretation: the major persistence surfaces agree. Qdrant and FAISS both
received multimodal memory; SQLite and the knowledge graph both held the
scene-level projection; the latest evidence route reported no projection gaps.

## Cognitive Signal Metrics

| Signal | Result |
| --- | --- |
| Entity evidence | `504` total, `198` unique, `120 / 141` scenes with any entity evidence |
| Scene-present entity channel | `25` scenes |
| Dialogue-mentioned entity channel | `117` scenes |
| Candidate-visible people channel | `12` scenes |
| Speaker-aligned mentions channel | `90` scenes |
| Sentiment labels | `139 / 141` scenes |
| Text-emotion rankings | `140 / 141` scenes |
| Audio-emotion score rankings | `141 / 141` scenes |
| Scene-context LLM payloads | `137 / 141` temporal segments |
| Time hints | `30` segments |
| Music events | `8` segments |

Interpretation: this run proves meaningful signal propagation beyond simple
"processed/not processed" status. Entity channels, sentiment, text emotion,
raw audio-emotion score rankings, temporal hints, and scene-context LLM payloads
all populated at scale. Audio emotion stayed correctly conservative: raw scores
were ranked for all scenes, but no promoted label crossed the configured
confidence threshold.

## Runtime Posture After Run

| Surface | Result |
| --- | --- |
| Local API | active |
| Pipeline | idle |
| WSL audio | available |
| `faster_whisper` | ready |
| LLM endpoints | `2 / 2` healthy |
| Qdrant | latest evidence current-run audio proof green |
| Operator console | active on local API, read-only |

Interpretation: the system returned to a clean inspection state after the run.
The UI/API surfaces were able to show both the successful memory state and the
bounded failure/skip details.

## Successes Proven

- Scene-centric ingestion completed for the full source scope.
- Current-run Qdrant audio provenance was strict and green for all CLAP-ok
  scenes.
- FAISS explicit-ID indexing was correct for all active modalities.
- Entity evidence populated through channelized surfaces rather than one vague
  boolean.
- Sentiment and text-emotion readouts populated across nearly all scenes.
- Audio-emotion rankings populated for every scene while preserving the
  threshold between ranked scores and promoted labels.
- Native subprocess failures were observable and mostly recovered.
- Operator Console problem-scope surfaces made errors, skips, and proof scope
  visible without granting mutation authority.

## Corrections Made After Witness

The witness run exposed small seams that have now been patched in source:

- direct CLI progress is read as status only and completed progress remains
  non-active
- runtime step-error logs are folded into latest evidence and UI problem scope
- CLAP keeps non-speech audio embedding intent and retries Windows native
  crashes once with `GOODQ_CLAP_FORCE_CPU=1`
- scene-context LLM uses grounded fallback on LLM transport, parse, or
  normalization failure
- harmonizer treats caption, OCR, time/music hints, and audio-emotion evidence
  as scene-context eligible signal
- retrieval audio proof now keeps selected-scene proof top-level and nests
  run-wide mismatch diagnostics under `collection_scope`

## Remaining Follow-Up

- Re-harmonize or rerun the affected scene scope to convert the current
  `137 / 141` scene-context artifact coverage into post-patch evidence.
- Validate the CLAP CPU retry on a fresh scene-first probe or broad rerun; the
  completed witness still contains one pre-mitigation optional CLAP error.
- Continue UI polish around meaning density, but avoid hiding the forensic
  readings that made this witness useful.

## Verification Surface

This witness was checked through:

- `/api/status`
- `/api/runs/latest/evidence`
- active epoch step ledger aggregates
- targeted unit/integration tests
- `docs/agent/CURRENT_STATE.md`
- `docs/agent/current_state.json`
- `python scripts/docs/doc_drift_lint.py`

Validation after patching:

- `163` targeted tests passed
- current-state JSON parsed successfully
- doc drift lint reported zero active drive-root violations
- API restarted cleanly on the local API target

