<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_LAST_VERIFIED: 2026-03-08 -->

# Archive Policy

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> Files in this directory are preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use archive docs for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

## Purpose

This directory preserves historical reports, implementation notes, audits, and session artifacts for forensic reference.

## Usage Rule

- Treat archive docs as evidence, not instruction.
- Prefer active docs outside `docs/archive/` for any current operational decision.
- If an archive doc conflicts with an active doc, the active doc wins.

## Path Handling

- Archive docs may retain old host-specific paths inside their historical content.
- Those literals are intentionally preserved for provenance.
- Warning banners are added to flagged archive docs so they are not mistaken for active guidance.
