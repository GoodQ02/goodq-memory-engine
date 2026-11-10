<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-10-13 -->

# Ingestion failure-mode Rolodex

Reusable lessons distilled at the operator's request when the old corpus and
its reports were retired. These are possible failure mechanisms to check, not
claims that the current code is broken or that prior repairs still pass.
Current behavior requires fresh source-to-consumer evidence.

## What to watch for

| Possible failure mode | Why it matters | Smallest useful fresh check |
| --- | --- | --- |
| Old state masquerades as a new result | A populated index, cached transcript, roster or old success receipt can conceal a failed new producer. | Verify resolved stores/completion caches are empty. Bind results to input hash, revision, configuration, model/embedding space, epoch and run. |
| Copies retain old destinations | Embedded collection names, IDs or ledger references can send writes back to another store. | Initialize new stores; verify all write targets belong to this run. Do not seed them with old bundles, manifests or databases. |
| Prelaunch failures disappear | A worker-only ledger can show no errors although scheduled work never started. | Account separately for admission, launch, execution and persistence. Every selected stage needs a terminal outcome or visible waiting state. |
| GPU resources outlive their owner | Model residency, overlap, cancellation and external GPU use can cause starvation or release a sibling's reservation. | Observe actual residency and per-launch ownership. Check cancellation isolation; measure waiting, inference and I/O separately. |
| Caller, worker and retry policies disagree | CPU fallback in one layer can contradict required GPU in another, or silently change devices on retry. | Record resolved policy and actual device at admission, launch and retry. Keep resource denial visible. |
| Valid output is mistaken for useful evidence | Structural checks, HTTP 200, vector counts or template summaries can pass while a modality is missing or inaccurate. | Inspect source and actual consumer. Distinguish model output, fallback, truncation, supported absence and failure. |
| Production inputs or deployed workers drift | A helper can pass while the real caller supplies the wrong path, interpreter, model or worker version. | Exercise Watchdog-to-worker dispatch and record effective inputs and runtime/model identity. |
| Sampling misses the relevant moment | One frame can omit an action, face or text; multiple samplers can duplicate work. | Record frame timestamps and extraction ownership. Compare manually marked source moments; disclose unexamined intervals. |
| Speech, sound and identity are conflated | A spoken mention is not an acoustic event; the visible face need not own the voice; turns may mix speakers. | Review audible intervals, preserve overlap/uncertainty, separate face/voice evidence and require reviewed identity mappings. |
| Dates or narrative exceed the source | OCR errors, ambiguous years and plausible model stories can become false facts. | Show raw text/frame candidates; separate offsets from calendar dates and observations from interpretations. Allow unknown. |
| Producer success fails to reach consumers | Fresh vectors can coexist with stale metadata; duplicate hits can exaggerate coverage. | Join results to the same run/video/scene, check unique relevant hits and play the original supporting interval. |
| Completion/recovery state contradicts artifacts | Interrupted finalization, stale dedup or partial writes can cause false Done, skipped work or duplicates. | Require terminal evidence; interrupt/resume a bounded job and check idempotency, successful-stage reuse and atomic records. |
| Absence is rendered as failure or readiness | Missing schemas can break dashboards; reachability can be mislabeled as populated indexes. | Check the empty API/UI and distinguish absent, empty and unavailable. Do not fabricate data for a green screen. |

## Retired evidence boundary

Pre-reset corpus reports, model comparisons, saved consumer responses, repair
receipts and generated corpus snapshots are retired from ingestion planning and
acceptance. This includes old run narratives in the roadmap/archives, `reports/`,
`docs/diagnostics/`, and experiment directories in the local retirement manifest
under `tmp/report-retirement-20261013/`.

Do not preload, index into the new video-memory corpus, restore or copy these
outputs into a fresh run. Old counts, identity labels, transcripts, dates,
rankings, timing measurements and test totals are not new ground truth.
Source code, contracts, test cases and product requirements remain in force.
A lesson alone does not authorize a repair or reopen a closed defect.

The reset and post-reset empty-state receipts remain applicable only to their
recorded observations. New acceptance needs independently annotated input and
current production-caller results. Consult an old report only for a named
code-history question that this Rolodex and current source cannot answer.

Navigation: [current milestone](../../PROJECT.md),
[requirements roadmap](../releases/ROADMAP.md),
[source map](../architecture/REPOSITORY_MAP.md).
