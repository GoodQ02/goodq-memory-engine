<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# R-05 Route-Effect and Client-Boundary Checkpoint

## Invariant

Every mounted API method/path operation has one truthful current-effect class.
Application startup fails closed when the mounted route graph no longer matches
that authority. A non-loopback client cannot reach request staging, automatic
mutation, curated mutation, or process execution through the raw API, while
passive and framework-owned behavior retains its existing semantics.

## Checkpoint Lineage

- Branch: `codex/r05-api-authority`
- Route-effect audit: `2ff140fa docs: checkpoint R05 route effect audit`
- Implementation: `31344a9f feat: enforce API route effect boundary`
- R-05 status: still `IN_PROGRESS`; this checkpoint closes the exhaustive
  route-effect registry and common client-boundary seam only

## One Mounted-Operation Authority

The registry contains all 68 mounted method/path operations using five exclusive
current-effect classes: 39 passive reads, 1 request-staging operation,
11 automatic mutations, 8 curated mutations, and 9 process executions. The
66 OpenAPI-published operations expose `x-goodq-effect`; `/docs` and `/redoc`
remain governed out-of-schema operations.

Startup reconciliation rejects missing, extra, duplicate, stale, colliding,
mis-mounted, or provenance-changed routes. It snapshots the ordered route graph
before the original application lifespan and verifies the same graph after
lifespan entry, so a same-method/path endpoint replacement cannot inherit an
approved effect. Duplicate canonical mount paths are rejected. Original lifespan
teardown still runs after a rejected startup.

The pure ASGI boundary uses only a full Starlette route match. It denies every
non-passive operation for missing, malformed, hostname, unspecified, private-LAN,
or public client addresses before request-body receive or downstream execution.
Locality comes only from the raw ASGI client address parsed with `ipaddress`;
IPv4, IPv6, and IPv4-mapped loopback are accepted, while forwarding, origin,
referer, and host headers confer no trust. Server launch explicitly disables
proxy-header rewriting.

The former route-local ingest locality check is removed only because the common
boundary now governs that operation. Exact-scope confirmation and durable audit
authority remain independent and unchanged.

## TDD Correction and Review

The final read-only review identified one missing graph invariant: the initial
implementation reduced operations to method/path and checked infrastructure
mounts independently. Two new witnesses first failed because duplicate canonical
mounts and a lifespan endpoint replacement were accepted. The minimal graph
identity/provenance repair then made both witnesses pass. The full focused
route-effect authority module passed 75 tests, and re-review returned
specification `PASS` and code/security quality `APPROVED` with no remaining
Critical or Important issue.

Two Codex Security app scan attempts are deliberately excluded from evidence.
Their validated targets resolved to an older commit range and omitted the staged
implementation; both were canceled before substantive analysis or artifact
generation. They must not be regenerated or cited as review of this checkpoint.

## Verification Evidence

Fresh post-fix evidence from the isolated worktree:

- 184 focused and adjacent API, route-effect, staging, status, search, summary,
  and system contract tests passed.
- Both new graph-identity witnesses were observed RED for the intended missing
  invariant before the production repair and GREEN afterward.
- All 13 staged Python files compiled successfully.
- The exact staged scope contained 13 expected files, with no missing, extra, or
  unstaged file.
- Staged and unstaged diff checks passed.
- The final staged binary-diff SHA-256 was
  `ded35200b0dd8651a78d79f63aa1900118dc79d825e42acbf1a68c5deceb671e`.

## Boundary Accounting

No API endpoint was invoked. No live ingestion, identity operation, process
action, model, memory store, Qdrant collection, listener, firewall rule, frozen
mixed checkout, public checkout, or data-root artifact was changed or exercised.
Tests used isolated fixtures and temporary roots.

## Resume

Do not reopen the completed staging or route/client-boundary seams without fresh
contradictory evidence. Continue R-05 with a read-only audit of the eight curated
mutation and nine process-execution operations against the verified R-11
exact-scope confirmation and durable-audit authority. Determine which operations
still bypass common confirmation, atomic mutation, persistent job, or execution
audit contracts before selecting one implementation seam.

Keep R-05-F1 hidden read mutation, R-08 identity recovery, R-14 passive status,
R-19 supervision, and R-20 LAN/gateway work under their existing owners.
