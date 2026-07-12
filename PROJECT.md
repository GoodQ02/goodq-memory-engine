<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-12 -->

# Active bounded mission

Roadmap item: R-05 — define API and Command Center execution authority.

## Outcome

Finish one local-operator authority model for mounted API and Command Center
surfaces. Every mounted method/path operation must have exactly one truthful
current-effect class based on transitive behavior rather than HTTP verb, route
name, or intended product semantics. A common client-boundary policy must deny
every non-passive class to non-loopback clients rather than relying on
route-local convention.

## Scope

- Re-audit the committed mounted route inventory after staging convergence.
- Define one effect registry for passive reads, request staging, automatic
  mutation, curated mutation, and process execution.
- Enforce a shared client-boundary rule that keeps passive reads available as
  designed while denying remote non-passive effects by default.
- Preserve the separately owned passive-status and identity-recovery seams.
- Add focused route inventory, policy, OpenAPI, and operator-surface tests.

## Boundaries

- Continue from the verified handler-truth descendant in an isolated worktree.
- Keep the frozen mixed checkout and public checkout unchanged.
- Do not run ingestion, mutate live memory or identity data, expose a service to
  the LAN, or perform destructive/process actions against live state.
- Do not reopen the completed staging or handler-truth checkpoints.
- Implement only the exhaustive registry, OpenAPI projection, and common
  remote-effect denial in this seam. Do not repair hidden retrieval or identity
  writes, and do not make status probes passive.
- Do not relabel an `automatic_mutation` operation as passive until its owning
  temporary-root or immutable-store witness proves the complete transitive call
  path is non-mutating.
- Do not implement passive runtime probing, identity recovery, LAN gateway,
  clean-memory replacement, or live process execution inside this seam.
- Preserve the exact-scope confirmation/audit authority and the preflight-only
  governor boundary.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register. Use this file
only for the bounded mission above; completed work belongs in evidence and Git
history, not in another backlog.
