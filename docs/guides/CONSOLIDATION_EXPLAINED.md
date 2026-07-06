<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: HISTORICAL_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-03-20 -->

# Environment Consolidation Explained

This file is kept only to explain a December 2025 consolidation phase that no
longer describes the full current runtime contract.

## What Is Historical Here

The earlier consolidation work proved that some image, text, and orchestration
surfaces could move into `goodq_core` without changing step logic.

That phase was real and useful, but it was not the final steady-state model.

## Current Runtime Truth

- `goodq_core` is the orchestration and base runtime environment.
- The supported bootstrap path also provisions a specialized step-env pack for
  workloads that still require isolated dependency boundaries.
- Active image, audio, text, and scene-detection routing is defined by the live
  orchestrators and the environment contract docs, not by the older
  “everything moved to one env” narrative.

## Use Instead

- Bootstrap contract:
  [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](../bootstrap/INSTALL_BOOTSTRAP.md)
- Install guide:
  [`docs/guides/install/INSTALL.md`](../bootstrap/INSTALL_BOOTSTRAP.md)
- System architecture:
  [`docs/architecture/SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md)
- Environment index:
  [`docs/reference/indexes/ENVIRONMENT_INDEX.md`](../reference/indexes/ENVIRONMENT_INDEX.md)
- Troubleshooting:
  [`docs/guides/general/TROUBLESHOOTING.md`](../archive/guides/general/TROUBLESHOOTING.md)

## Practical Guidance

Do not use this note as permission to remove specialized step environments or
to rewrite active env routing without a dependency audit and witness run.
