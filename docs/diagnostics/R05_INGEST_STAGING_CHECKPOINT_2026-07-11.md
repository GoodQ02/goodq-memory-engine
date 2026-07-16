<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-05 Governed Ingest Staging Checkpoint

## Invariant

The local operator may prepare one media request, inspect its server-derived
scope, and explicitly confirm or cancel it. Only a confirmed, unchanged copy may
become visible to Watchdog. The API does not execute ingestion, remote clients
cannot mutate this surface, and public responses do not expose internal paths
or raw runtime failures.

## Checkpoint Lineage

- Branch: `codex/r05-api-authority`
- Authority audit: `21c94bc5 docs: checkpoint R-05 authority audit`
- Staging implementation: `b69803af feat: converge governed ingest staging`
- R-05 status: still `IN_PROGRESS`; this checkpoint closes only the first
  request-staging seam

## One Staging Authority

The superseded `/api/ingest/token` and `/api/ingest/upload` routes are removed.
JSON local-path preparation and multipart browser preparation now share
`POST /api/ingest/submit`. Preparation creates a durable request record and a
private pending copy. Confirm and cancel are separate JSON transitions on that
same route. Retro Console shows the exact derived name, size, hash prefix, and
request ID before using a visible operator confirmation; duplicate evidence is
reported as already processed rather than as a failed upload.

The staging authority is the R-11 MiniAgent exact-scope token store. Standalone
authorization is restricted to `stage_ingest_request`; native executable tools
still require their handler-and-audit path. Tokens are single-use and bound to
the complete request scope. The ledger persists only the token fingerprint and
expiry, never the bearer token.

## Storage, Recovery, and Runtime Truth

The submit mutation route accepts loopback clients only. Multipart file bytes
are bounded during parser streaming, aggregate pending storage has an explicit
configuration budget, and active partial files count toward that budget.

Before a new preparation, every incomplete ledger record is inspected. Only
candidate records take their per-request lock. Abandoned receiving or
unconfirmed artifacts expire from the persisted expiry; interrupted
cancellation is retried; and an already-authorized hidden verification copy is
recovered. The scan has no fixed history prefix that can hide later requests.

Confirmation rechecks the private pending copy, claims the exact authority,
moves the copy through a hidden inbox verification path, rechecks it again, and
then uses an atomic visible rename. Exact runtime evidence reconciles a file
that Watchdog picks up before the route records its final state, including the
race during the post-rename verification itself. Same-token retries recover
claim/revoke and final-move crash windows without authorizing a different
scope.

Request status requires the unique staged name as well as the content hash
before using Watchdog registry evidence. Unconfirmed, canceled, expired, and
integrity-failed records cannot inherit another same-content request's result.
Public failure text is generic, and submit/status models omit source, partial,
pending, verification, and staged paths.

## Verification Evidence

Fresh evidence from the isolated worktree:

- 167 focused ingest staging, route, status, ledger, isolation, MiniAgent
  confirmation, and durable-audit tests passed.
- Deterministic regressions cover concurrent confirm/cancel calls, claim and
  revoke recovery, transient pending deletion, tampering, parser-time limits,
  pending quotas, persisted expiry, history beyond 1,000 terminal records,
  hidden verification recovery, post-move retry, and Watchdog pickup during the
  final visible verification.
- Changed Python files and the convergence test compile successfully.
- Documentation authority, documentation drift, banned-token,
  dependency-drift, configuration-budget, and staged-diff gates passed.
- Documentation drift scanned 294 active files with zero active violations.
- Independent specification and security/concurrency reviews returned
  `APPROVED` after their findings were converted into focused regressions.

The unchanged legacy API-root harness still has four pre-existing import-stub
failures because its synthetic `api.routes` package omits the existing
`identity` module. Neither that test nor `api/main.py` changed in this seam; the
real mounted ingest inventory and focused router tests passed. This checkpoint
does not relabel that unrelated harness as green.

## Follow-up Evidence

Security review also found unchanged base behavior where a native MiniAgent
handler may return `status=error` while the generic wrapper retains success and
return code zero. It is not reachable from the authorization-only ingest
staging action and is not caused by this diff. It does contradict the broad
handler-outcome truth expected after R-11, so `R-11-F1` is recorded in the
roadmap as a separate isolated follow-up rather than being silently mixed into
this checkpoint.

## Boundary Accounting

The frozen mixed checkout remains unchanged at 96 expanded status entries. The
public checkout remains at zero working entries. Tests used temporary roots;
no live inbox, Watchdog job, media, Qdrant state, identity state, service
binding, or public release surface was mutated.

## Resume

Run the isolated `R-11-F1` handler-outcome truth repair before widening the
remaining R-05 route authority. Then continue R-05 with the common route-effect
registry and remote-mutation denial seam. Do not reopen the completed staging
route unless fresh focused evidence contradicts this checkpoint.
