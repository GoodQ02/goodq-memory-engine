<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: CHECKPOINT_EVIDENCE_COMPLETE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# R-05 API and Command Center Authority Audit

## Question

What is the current mounted API/control surface after the completed R-11
checkpoint, which parts of the earlier 78-operation inventory still exist only
in the frozen mixed checkout, and what is the smallest independent authority
repair?

## No-Repeat and Ownership Boundary

The audit used the clean `codex/r05-api-authority` worktree based on the R-11
closure. It did not transplant the frozen identity prototype.

R-17 assigns the frozen Command Center mount and assets plus the Retro Console
navigation intent to R-05. It assigns every frozen `api/routes/identity.py`,
Identity Workbench, identity resolver, phase-job, and identity-test change to
R-08. Those identity changes include unsafe authority and recovery behavior and
must be reconstructed later rather than copied into this seam.

## Route Count Reconciliation

The clean worktree mounts 70 FastAPI operations:

| Effect class | Clean R-05 | Frozen R-08-only additions | Prior mixed snapshot |
|---|---:|---:|---:|
| Passive/read-only | 49 | 5 | 54 |
| Request staging | 4 | 0 | 4 |
| Curated mutation | 8 | 2 | 10 |
| Process execution | 9 | 1 | 10 |
| **Total** | **70** | **8** | **78** |

The eight-operation difference is exact: five frozen passive identity/evidence
reads, two frozen family-roster mutations, and the frozen identity phase-job
launch. The frozen Command Center is an additional static mount, not an API
operation.

There is a separate counting trap: `app.routes` also contains 78 objects in the
clean worktree, but those are 70 `APIRoute` objects, `/openapi.json`, and seven
static mounts. That object count is not the earlier 78-operation inventory.

## Current Effectful Operations

### Request staging

- `POST /api/system/ingest` — fail-closed declaration only
- `GET /api/ingest/token` — self-issued in-memory token
- `POST /api/ingest/submit` — token-gated, policy-labeled, ledgered staging
- `POST /api/ingest/upload` — direct unledgered inbox write

### Curated mutation

- `POST /api/system/identity/stitch`
- `POST /api/system/identity/stitch/revoke`
- `POST /api/summary/collections`
- `DELETE /api/summary/collections/{collection_id}`
- `POST /api/identity/face-clusters/label`
- `POST /api/identity/speaker-clusters/confirm`
- `POST /api/identity/roster/save`
- `POST /api/identity/roster/export`

### Process execution

- `POST /api/search/temporal/summarize`
- `POST /api/summary/video/{video_hash}/generate`
- `POST /api/identity/rebuild-face-clusters`
- `POST /api/identity/roster/validate`
- `GET /api/system/status`
- `HEAD /api/status`
- `GET /api/status`
- `GET /api/gpu/stats`
- `GET /api/wsl2-status`

The last five operations represent the four status paths owned by the passive
runtime-status repair. This seam records their actual current effects but does
not repair or reclassify them.

The remaining 49 operations are passive/read-only projections or computations,
including the disabled system reindex/reload declarations and the stitch
preview. The route inventory was derived from mounted code, not from the
curated `/api` front desk or stale API prose.

## Reproducible Mounted-Operation Register

| Effect | Method | Mounted path | Source anchor |
|---|---|---|---|
| passive | GET | `/` | `api/routes/meta.py:16` |
| passive | GET | `/api` | `api/routes/meta.py:22` |
| passive | POST | `/api/search/multimodal` | `api/routes/search.py:666` |
| passive | GET | `/api/search/text` | `api/routes/search.py:712` |
| passive | GET | `/api/search/visual` | `api/routes/search.py:748` |
| passive | POST | `/api/search/temporal` | `api/routes/search.py:824` |
| process | POST | `/api/search/temporal/summarize` | `api/routes/search.py:879` |
| passive | GET | `/api/videos/{video_id}/scenes` | `api/routes/scenes.py:165` |
| passive | GET | `/api/videos/{video_id}/scenes/{scene_id}` | `api/routes/scenes.py:198` |
| passive | GET | `/api/videos/{video_id}/scenes/{scene_id}/similar` | `api/routes/scenes.py:233` |
| passive | GET | `/api/videos/{video_id}/timeline` | `api/routes/timeline.py:164` |
| passive | GET | `/api/videos/{video_id}/timeline/full` | `api/routes/timeline.py:204` |
| passive | GET | `/api/media/video/{video_id}/scene/{scene_id}/frame/{frame_index}` | `api/routes/media.py:31` |
| passive | GET | `/api/media/audio/{video_id}/{chunk_id}.wav` | `api/routes/media.py:74` |
| passive | GET | `/api/media/video/{video_id}/frame/{frame_name}` | `api/routes/media.py:115` |
| process/R-14 | GET | `/api/system/status` | `api/routes/system.py:105` |
| passive | GET | `/api/system/videos` | `api/routes/system.py:181` |
| staging | POST | `/api/system/ingest` | `api/routes/system.py:227` |
| passive | POST | `/api/system/reindex` | `api/routes/system.py:263` |
| passive | POST | `/api/system/reload` | `api/routes/system.py:291` |
| passive | GET | `/api/system/identity/unstitched` | `api/routes/system.py:325` |
| passive | POST | `/api/system/identity/stitch/preview` | `api/routes/system.py:395` |
| curated mutation | POST | `/api/system/identity/stitch` | `api/routes/system.py:471` |
| passive | GET | `/api/system/identity/mappings` | `api/routes/system.py:613` |
| curated mutation | POST | `/api/system/identity/stitch/revoke` | `api/routes/system.py:626` |
| passive | GET | `/api/summary/dashboard` | `api/routes/summary.py:44` |
| passive | GET | `/api/summary/entity/{entity_id:path}` | `api/routes/summary.py:62` |
| passive | GET | `/api/summary/collections` | `api/routes/summary.py:84` |
| curated mutation | POST | `/api/summary/collections` | `api/routes/summary.py:101` |
| curated mutation | DELETE | `/api/summary/collections/{collection_id}` | `api/routes/summary.py:120` |
| passive | GET | `/api/summary/capabilities` | `api/routes/summary.py:157` |
| passive | GET | `/api/summary/video/{video_hash}` | `api/routes/summary.py:172` |
| passive | GET | `/api/summary/video/{video_hash}/status` | `api/routes/summary.py:249` |
| process | POST | `/api/summary/video/{video_hash}/generate` | `api/routes/summary.py:264` |
| staging | GET | `/api/ingest/token` | `api/routes/ingest.py:119` |
| staging | POST | `/api/ingest/submit` | `api/routes/ingest.py:129` |
| passive | GET | `/api/ingest/status/{request_id}` | `api/routes/ingest.py:203` |
| staging | POST | `/api/ingest/upload` | `api/routes/ingest.py:237` |
| process/R-14 | HEAD | `/api/status` | `api/routes/runtime.py:614` |
| process/R-14 | GET | `/api/status` | `api/routes/runtime.py:614` |
| passive | GET | `/api/health/summary` | `api/routes/runtime.py:704` |
| passive | GET | `/api/engines` | `api/routes/runtime.py:757` |
| passive | GET | `/api/queue` | `api/routes/runtime.py:774` |
| passive | GET | `/api/storage/summary` | `api/routes/runtime.py:998` |
| process/R-14 | GET | `/api/gpu/stats` | `api/routes/runtime.py:1041` |
| process/R-14 | GET | `/api/wsl2-status` | `api/routes/runtime.py:1070` |
| passive | GET | `/api/models` | `api/routes/runtime.py:1076` |
| passive | GET | `/api/runs/latest/preview` | `api/routes/runtime.py:3314` |
| passive | GET | `/api/runs/latest/evidence` | `api/routes/runtime.py:3319` |
| passive | GET | `/api/runs/audio-proof/latest` | `api/routes/runtime.py:3324` |
| passive | GET | `/api/memory/stats` | `api/routes/runtime.py:3384` |
| passive | GET | `/api/read/envelope` | `api/routes/runtime.py:3450` |
| passive | GET | `/api/control-recurrence/reports` | `api/routes/control_recurrence.py:16` |
| passive | GET | `/api/control-recurrence/reports/latest` | `api/routes/control_recurrence.py:23` |
| passive | GET | `/api/control-recurrence/reports/trend` | `api/routes/control_recurrence.py:30` |
| passive | GET | `/api/control-recurrence/reports/{report_id}` | `api/routes/control_recurrence.py:37` |
| passive | GET | `/api/control-recurrence/reports/{report_id}/recommendations` | `api/routes/control_recurrence.py:47` |
| passive | GET | `/api/control-recurrence/reports/{report_id}/markdown` | `api/routes/control_recurrence.py:57` |
| passive | GET | `/api/identity/face-clusters` | `api/routes/identity.py:85` |
| process | POST | `/api/identity/rebuild-face-clusters` | `api/routes/identity.py:95` |
| curated mutation | POST | `/api/identity/face-clusters/label` | `api/routes/identity.py:129` |
| passive | GET | `/api/identity/speaker-clusters` | `api/routes/identity.py:155` |
| curated mutation | POST | `/api/identity/speaker-clusters/confirm` | `api/routes/identity.py:170` |
| passive | GET | `/api/identity/name-mentions` | `api/routes/identity.py:196` |
| passive | GET | `/api/identity/roster` | `api/routes/identity.py:207` |
| curated mutation | POST | `/api/identity/roster/save` | `api/routes/identity.py:226` |
| process | POST | `/api/identity/roster/validate` | `api/routes/identity.py:262` |
| curated mutation | POST | `/api/identity/roster/export` | `api/routes/identity.py:302` |
| passive | GET | `/docs` | `api/main.py:139` |
| passive | GET | `/redoc` | `api/main.py:154` |

## Authority Findings

1. The ingest facade still has two competing staging paths. `/submit` consumes
   a self-issued token, requires a policy profile, computes a hash, writes an
   atomic request record, and returns a request ID. `/upload` writes a randomly
   named file directly into the watched inbox without that ledger, policy,
   request identity, or durable decision evidence.
2. The ingest token is held in a process-local set. It is neither durable nor
   bound to an operation and exact request scope. The completed MiniAgent
   checkpoint now provides atomic, single-use, exact-operation/full-scope
   confirmation and durable generic audit evidence, but no API route uses it.
3. There is no common route-effect registry or request-client guard. Loopback is
   the configured default, but environment/config overrides can bind elsewhere;
   mutation requests are not independently denied when the client is remote.
4. Curated mutations do not share a durable decision/execution audit. Identity
   stitch still uses a request boolean as confirmation. Collection, mapping,
   and identity writes use separate file helpers with inconsistent locking,
   flush, replacement, and failure behavior.
5. Summary generation and identity helper execution have no common confirmed
   process authority. Summary duplicate protection is memory-only, and its
   background work has no persistent job record. Identity process recovery and
   live roster authority remain R-08-owned.
6. The frozen Command Center calls the R-08-owned unconfirmed identity
   `run-phases` prototype. Its visual intent is preserved, but it must not be
   mounted as a live control until a governed backend exists.

## UI Truth Findings

- Retro Console labels its surface read-only/no-ingestion while its Upload Pad
  posts directly to `/api/ingest/upload`. Success copy says ingestion is
  starting even though the route only stages a file.
- Stitching Workbench is visibly mutation-oriented, but commit/revoke rely on
  browser/request booleans rather than the common authority.
- Summary Console visibly saves/deletes collections and starts summary
  generation; the backend lacks common audit/confirmed-job evidence.
- The clean Identity Workbench exposes current curated/process routes. Its
  underlying atomicity, authority precedence, recovery, and redaction repairs
  remain separately owned.

## First Implementation Seam

Converge the Retro Upload Pad and local-path submit flow on one ledgered request
staging implementation. The first test must prove that no upload reaches the
watched inbox without a durable request record and request ID. Remove the
duplicate `/upload` authority rather than retaining it as a compatibility
layer, then make the UI say “staged/requested” rather than “ingestion started.”

This seam is independent of identity recovery, passive status probing, network
exposure, and clean-memory replacement. Later R-05 seams can build the common
route registry, remote-mutation denial, curated-write audit, and confirmed
persistent process-job contract on the proven R-11 authority.

## Audit Safety

- No API route was called.
- No service, process, ingestion, identity, memory, Qdrant, file-store, or
  network state was mutated.
- The frozen mixed checkout remained at 96 expanded entries.
- The public checkout remained at zero working entries.
