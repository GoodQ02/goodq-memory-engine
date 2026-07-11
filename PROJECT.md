<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_BOUNDED_MISSION -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Active bounded mission

Roadmap item: R-11-F1 — repair MiniAgent handler-outcome truth.

## Outcome

When a native MiniAgent handler explicitly reports `status=error`, the outward
tool envelope, return code, side-effect report, and durable execution audit must
all report that failure truthfully without exposing raw handler details.

## Scope

- Preserve existing `blocked` handler semantics.
- Map only explicit handler `status=error` to outward error and return code one.
- Use the controlled handler reason as the error code, with a generic fallback
  when no reason exists and a generic outward message in both cases.
- Prove execution audit status, return code, error codes, and nonmutation agree
  with the outward envelope.
- Re-run the MiniAgent and governed-ingest staging regressions.

## Boundaries

- Work only in this isolated follow-up worktree.
- Keep the frozen mixed checkout and public checkout unchanged.
- Do not run ingestion, mutate live memory or identity data, expose a service to
  the LAN, or perform destructive/process actions against live state.
- Do not change confirmation, token, handler, route, Control Agent, or governor
  authority in this follow-up.
- Return to remaining API-authority work only after focused evidence and a private
  checkpoint close this contradiction.

## Resume authority

Use `docs/releases/ROADMAP.md` as the sole long-running register. Use this file
only for the bounded mission above; completed work belongs in evidence and Git
history, not in another backlog.
