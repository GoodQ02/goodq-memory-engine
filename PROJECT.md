<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Active bounded mission

Roadmap item: R-05 — define API and Command Center execution authority.

## Outcome

Finish one local-operator authority model for mounted API and Command Center
surfaces. Every route must have one truthful effect class, and remote clients
must be denied mutation by a common policy rather than route-local convention.

## Scope

- Re-audit the committed mounted route inventory after staging convergence.
- Define one effect registry for passive reads, request staging, curated
  mutation, and process execution.
- Enforce a shared client-boundary rule that keeps passive reads available as
  designed while denying remote mutation by default.
- Preserve the separately owned passive-status and identity-recovery seams.
- Add focused route inventory, policy, OpenAPI, and operator-surface tests.

## Boundaries

- Continue from the verified handler-truth descendant in an isolated worktree.
- Keep the frozen mixed checkout and public checkout unchanged.
- Do not run ingestion, mutate live memory or identity data, expose a service to
  the LAN, or perform destructive/process actions against live state.
- Do not reopen the completed staging or handler-truth checkpoints.
- Do not implement passive runtime probing, identity recovery, LAN gateway,
  clean-memory replacement, or live process execution inside this seam.
- Preserve the exact-scope confirmation/audit authority and the preflight-only
  governor boundary.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register. Use this file
only for the bounded mission above; completed work belongs in evidence and Git
history, not in another backlog.
