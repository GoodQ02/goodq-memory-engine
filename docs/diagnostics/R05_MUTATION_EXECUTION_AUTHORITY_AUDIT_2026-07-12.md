<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-05 Mutation and Execution Authority Audit

## Question

After the exhaustive route-effect and client-boundary checkpoint, which of the
eight curated mutations and nine process executions use the verified exact-scope
confirmation, durable audit, atomic mutation, or persistent-job authorities, and
what is the smallest coherent next repair?

## Authority and No-Repeat Boundary

The audit used the clean `codex/r05-api-authority` worktree after checkpoints
`31344a9f` and `f06e9a01`. It did not invoke an API operation, start a process,
or exercise live GoodQ data.

The route-effect registry and common loopback boundary are complete and were not
reopened. The completed control-authority checkpoint remains the only exact-scope
confirmation and generic decision/execution-audit authority. Its
`MiniAgentClient.authorize_action()` boundary is currently limited to the staged
ingest request, and none of the 17 audited route owners calls MiniAgent.

Identity persistence, recovery, synchronization, and redaction remain with the
identity repair. Status-route side-effect removal remains with passive runtime
status. This audit records their current bypasses but does not absorb those
repairs.

## Fresh Register Proof

The current registry contains 68 mounted method/path operations:

| Effect class | Count |
|---|---:|
| Passive read | 39 |
| Request staging | 1 |
| Automatic mutation | 11 |
| Curated mutation | 8 |
| Process execution | 9 |

A bounded source search across the five owner modules found no MiniAgent,
`authorize_action`, `execute_tool`, confirmation-token, or generic tool-audit
integration for the 17 operations below.

## Curated-Mutation Authority Map

| Operation | Current authority and persistence | Repair owner |
|---|---|---|
| `POST /api/system/identity/stitch` | `execute_stitch()` accepts a request boolean, then updates multiple identity sinks without the common exact-scope token or generic audit. | Identity persistence remains separate; common confirmation/audit is this authority lane. |
| `POST /api/system/identity/stitch/revoke` | `revoke_stitch()` performs the inverse multi-sink write directly; browser confirmation is not server authority. | Same split as stitch. |
| `POST /api/summary/collections` | `create_collection()` calls `summary_aggregator.add_collection()` directly with no exact-scope confirmation or generic audit. Its file replacement helper has no lock/fsync contract. | This authority lane. |
| `DELETE /api/summary/collections/{collection_id}` | `delete_collection()` calls `summary_aggregator.soft_delete_collection()` directly; browser confirmation is not server authority. | This authority lane. |
| `POST /api/identity/face-clusters/label` | `label_face_cluster()` writes identity state directly without the common authority. | Identity persistence remains separate; common confirmation/audit is this authority lane. |
| `POST /api/identity/speaker-clusters/confirm` | `confirm_speaker_cluster()` writes directly; the UI mutates local display state before server success and has no rollback. | Same split as face labeling. |
| `POST /api/identity/roster/save` | `save_roster_identity()` writes the roster projection directly without exact-scope confirmation or generic audit. | Identity persistence and recovery remain separate. |
| `POST /api/identity/roster/export` | `export_roster()` writes an export directly and returns/logs path detail. | Identity persistence/redaction remain separate; common confirmation/audit is this authority lane. |

All eight operations are correctly classified and denied to non-loopback clients.
None is governed by the verified exact-scope authority, and none produces the
generic durable decision/execution record. Three curated UI paths add a browser
modal or request boolean, but those are presentation hints rather than
single-use, operation-and-scope-bound server authority.

## Process-Execution Authority Map

| Operation | Current execution behavior | Repair owner |
|---|---|---|
| `POST /api/search/temporal/summarize` | `summarize_temporal()` performs synchronous model work. `LLMClient` health/fallback behavior can auto-start local model services before chat. There is no confirmation, persistent job, or generic execution audit. | This authority lane, but not the next seam. |
| `POST /api/summary/video/{video_hash}/generate` | `generate_video_summary()` starts a FastAPI background task after an LLM probe. Duplicate state is the process-local `_running_summarizations` set. There is no exact-scope confirmation, job record, recovery, or generic execution audit. | This authority lane and the next seam. |
| `POST /api/identity/rebuild-face-clusters` | `rebuild_face_clusters()` launches a blocking identity subprocess without the common authority or durable job. | Common confirmation/audit remains this authority lane; identity persistence, process identity, and crash recovery remain with the identity owner. |
| `POST /api/identity/roster/validate` | `validate_roster()` launches a blocking validation subprocess without the common authority or durable job. | Common confirmation/audit remains this authority lane; identity persistence, process identity, and crash recovery remain with the identity owner. |
| `GET /api/system/status` | Runs runtime probes while presented as status. | Passive status repair. |
| `HEAD /api/status` | Shares the process-executing status endpoint. | Passive status repair. |
| `GET /api/status` | Runs runtime/WSL probes while presented as status. | Passive status repair. |
| `GET /api/gpu/stats` | Executes a GPU probe. | Passive status repair. |
| `GET /api/wsl2-status` | Executes a WSL probe. | Passive status repair. |

The five status operations retain their truthful `process_execution` class until
no-side-effect witnesses justify reclassification. Adding confirmation or job
records to them would preserve the wrong behavior and conflict with their owner.
The two identity subprocesses need the common authority eventually, but their
process identity and crash recovery cannot be repaired independently of the
identity seam.

## UI and Outward-Truth Findings

The active UI has 20 call sites covering 15 of the 17 operations: all eight
curated mutations; one each for temporal summary, video generation, face
rebuild, roster validation, GPU status, and WSL status; and six references to
`GET /api/status`. No caller exists for `GET /api/system/status` or
`HEAD /api/status`, and no active Command Center mount exists in this clean
worktree. Across the 15 covered operations, no caller is aligned with exact-scope
confirmation and durable outcome evidence: four use an ambiguous modal,
checkbox, or boolean, and eleven call the route directly.

The smallest complete outward-truth failure is Summary Console video generation:

- `generate_video_summary()` returns success after registering a response-bound,
  in-process FastAPI background task.
- `_generate_summary_worker()` catches and logs every failure, then removes the
  hash from `_running_summarizations`.
- `get_summary_status()` can report only `running` or `idle`; restart also loses
  the process-local marker.
- `startPollingStatus()` polls every two seconds and treats `idle` as
  "generated successfully," so worker failure or process restart is presented as
  success.
- The video summarizer reads every `scene_summary` and every provenance row
  without filtering them to `video_hash`. A confirmation bound to one video
  would therefore authorize computation over other videos unless the worker is
  narrowed in the same seam.
- A nonempty template fallback is currently labeled `method="llm"` whenever LLM
  use is enabled, so worker outcome metadata is also not a trustworthy success
  oracle.

## Smallest Coherent Next Seam in This Audited Register

Govern video-summary generation as one durable, confirmed external job. Do not
bundle temporal summarization: it is synchronous and returns its result in the
request, so it does not share the same dispatch, rollback, recovery, or UI
verification boundary. The operation remains unresolved under the R-05 roadmap
item and will need its own API/result-retrieval migration rather than being
hidden by this checkpoint.

The next seam must reuse rather than compete with verified control authority:

1. Register one explicit authorization-only action for video-summary generation
   under the existing exact-scope, single-use confirmation store.
2. Bind confirmation to the operation and server-normalized generation scope;
   confirmation material is control metadata, not part of the action scope.
3. Use one generic locked, atomic action-job ledger, exercised only by video
   summary in this seam. Persist `pending_confirmation` before token issuance,
   then move through `authorizing`, `queued`, `running`, and a terminal
   `succeeded`, `failed`, `interrupted`, or `expired` state. Store only a token
   fingerprint, authorization request identifier, owner instance, timestamps,
   sanitized outcome, and audit status; never store the bearer token.
4. Consume confirmation under the job lock before entering `queued`. Recover a
   persisted matching `authorizing` attempt if token claim succeeded before a
   crash, and reconcile prior-instance `queued` or `running` records to
   `interrupted` without silently retrying execution.
5. Add a public external-outcome recorder to the existing
   `goodq.tool-audit.v1` authority; route code must not call private audit
   helpers or create a second audit log. An audit failure after a successful
   side effect must preserve `succeeded` with a visible failed audit status.
6. Keep the response-bound background task as the executor for this seam. The
   worker must filter scene summaries and provenance to the confirmed video,
   treat an exception or returned `success=false` as failure, and label template
   fallback truthfully.
7. Return and poll the durable job identifier. Summary Console must distinguish
   pending confirmation, authorizing, queued, running, succeeded, failed,
   interrupted, and expired outcomes and must never equate `idle` with success.

## Required Implementation Evidence

The next seam is not complete until focused tests prove:

- missing, expired, reused, wrong-operation, wrong-video, and extra-scope
  confirmations fail before queueing or dispatch;
- preparation creates one durable `pending_confirmation` job before token
  issuance, and a valid confirmation is consumed exactly once before the job
  enters `queued`;
- duplicate same-video preparation and dispatch resolve deterministically under
  concurrency without launching two workers;
- terminal states are immutable, token-claim recovery from `authorizing` is
  deterministic, and queued/running restart reconciliation becomes
  `interrupted` rather than a silent retry;
- raw confirmation material, private paths, subprocess output, and exception
  detail are absent from job, audit, response, and UI surfaces;
- decision and external execution outcomes use the existing generic audit
  schema, reject undeclared actions, and preserve successful side-effect truth
  with visible audit-write failure behavior;
- worker exceptions and returned `success=false` both persist `failed`;
- scene-summary/provenance fixtures from another video are excluded from the
  confirmed target, and template fallback is never labeled as LLM output;
- UI polling shows success only from a durable `succeeded` state and shows
  durable failure/recovery states accurately;
- route-effect startup/client-boundary tests remain green and the operation
  remains `process_execution`.

## Audit Safety

- No API endpoint or UI action was invoked.
- No model, worker, job, ingestion, identity operation, Qdrant collection,
  memory store, service, listener, or data-root artifact was changed.
- The frozen mixed checkout and public checkout were not touched.
- This checkpoint changes documentation only and does not claim the selected
  implementation seam is complete.
