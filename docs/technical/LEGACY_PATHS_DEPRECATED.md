<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-14 -->

# Legacy Paths Deprecated

This document is the single reference for legacy root path literals that were used before path abstraction.

## Deprecated Legacy Roots
- `L:/models`
- `L:\models`
- `L:/GoodQ_Data`
- `L:\GoodQ_Data`

## Active Documentation Rule
- Do not use the legacy literals above in active docs.
- Use environment-variable abstractions instead:
  - `<GOODQ_DATA_ROOT>/models`
  - `<GOODQ_DATA_ROOT>/GoodQ_Data`
  - `<project_root>`
  - `<GOODQ_WSL_WORKSPACE>`

## Migration Mapping
- `L:/models` and `L:\models` map to `<GOODQ_DATA_ROOT>/models` and `<GOODQ_DATA_ROOT>\models`.
- `L:/GoodQ_Data` and `L:\GoodQ_Data` map to `<GOODQ_DATA_ROOT>/GoodQ_Data` and `<GOODQ_DATA_ROOT>\GoodQ_Data`.
