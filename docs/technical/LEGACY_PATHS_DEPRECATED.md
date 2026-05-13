<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-14 -->

# Legacy Paths Deprecated

This document is the single reference for legacy root path literals that were used before path abstraction.

## Deprecated Legacy Roots
- fixed-drive `models` roots (slash and backslash variants)
- fixed-drive `GoodQ_Data` roots (slash and backslash variants)

## Active Documentation Rule
- Do not use the legacy literals above in active docs.
- Use environment-variable abstractions instead:
  - `<GOODQ_DATA_ROOT>/models`
  - `<GOODQ_DATA_ROOT>/GoodQ_Data`
  - `<project_root>`
  - `<GOODQ_WSL_WORKSPACE>`

## Migration Mapping
- fixed-drive `models` roots map to `<GOODQ_DATA_ROOT>/models` and `<GOODQ_DATA_ROOT>\models`.
- fixed-drive `GoodQ_Data` roots map to `<GOODQ_DATA_ROOT>/GoodQ_Data` and `<GOODQ_DATA_ROOT>\GoodQ_Data`.

## Model Cache Drift Note

- 2026-05-11 audit: the legacy root-level model cache contained no unique
  material model payloads compared with the canonical
  `<GOODQ_DATA_ROOT>/models` cache. Nonzero payload files matched by hash; the
  only unmatched files were non-runtime cache logs.
- Treat legacy root-level model cache references as drift risk, not runtime
  authority.
- Offline bundles must source model payloads from `<GOODQ_DATA_ROOT>/models`
  or an explicitly staged `%GOODQ_MODEL_CACHE_ROOT%`, not from legacy
  fixed-drive root copies.
- Legacy cache helper files or templates that still encode fixed-drive cache
  roots must be audited before use. Runtime authority remains the configured
  `GOODQ_DATA_ROOT` path resolved through the project config loader.
