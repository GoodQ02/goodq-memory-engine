<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-02-12 -->

# Bootstrap Contract v1 (Phase 0 Complete)

## Authoritative Artifacts
The following Phase 0 bootstrap artifacts are authoritative:
- `docs/reference/DEPENDENCIES.md`
- `docs/archive/reports/bootstrap_report.json`
- `docs/reference/GPU_CAPABILITY_MATRIX.md`
- `docs/reference/PLATFORM_SUPPORT.md`

## Contract Statements
- `BASELINE` profile must remain CPU-safe and GPU-optional.
- `GPU_ENHANCED` is additive and must not affect correctness.
- Desktop is canonical host; laptop is follower-only.
- No runtime behavior was modified during Phase 0.

## Phase 0 Record
- Commit `641449e` reclassified CUDA in `docs/reference/DEPENDENCIES.md`.
- Commit `a6ea29e` aligned `docs/archive/reports/bootstrap_report.json`.
- Phase 0 scope was forensic analysis and contract alignment only.

## Next Phase Preview
- Path abstraction
- Profile flag wiring
- Documentation normalization
- No feature changes

## Phase A Preview
- Path abstraction has begun with `GOODQ_DATA_ROOT`-driven data root resolution.
- Phase A Step 2: WSL identity abstraction implemented.
- Phase A Step 3: Host profile flag introduced.
- Phase A Step 4: Semantic profile normalization complete.
