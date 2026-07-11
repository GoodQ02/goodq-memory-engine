<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Active bounded mission

Roadmap item: R-10 — align architecture contracts.

## Outcome

Resolve the Qdrant storage-root contradiction exposed by the documentation
semantic gate. The configured path, runtime consumers, operator guidance, and
canonical architecture contracts must describe one proven layout.

## Scope

- Trace `paths.qdrant_storage` from configuration through service launchers and
  runtime consumers.
- Correct only the canonical contract claims that the trace proves wrong.
- Add focused storage-path evidence or tests before changing prose.
- Rerun the full documentation authority and current-state gates.

## Boundaries

- Do not change the configured storage root merely to make prose green.
- Do not move Qdrant data, restart services, or alter network bindings.
- Do not reopen the verified current-state evidence unless a fresh capture
  proves drift.
- Do not touch the frozen mixed checkout or the public checkout.

## Resume authority

Use `docs/releases/ROADMAP.md` for the long-running register. Use this file only
for the bounded mission above; completed work belongs in checkpoints and Git
history, not in another backlog.
