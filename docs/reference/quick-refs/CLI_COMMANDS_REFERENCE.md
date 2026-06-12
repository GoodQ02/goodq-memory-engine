<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_POINTER -->
<!-- DOC_LAST_VERIFIED: 2026-03-26 -->

# CLI Commands Reference Pointer

This older extended command sheet is kept only to preserve incoming links.

## Use Instead

- Full canonical CLI surface:
  [`docs/reference/CLI-REFERENCE.md`](../CLI-REFERENCE.md)
- Current Windows launch runbook:
  [`docs/guides/general/LAUNCH_INSTRUCTIONS.md`](../../guides/general/LAUNCH_INSTRUCTIONS.md)
- Compact current operator quick ref:
  [`docs/reference/quick-refs/QUICK_REFERENCE_CARD.md`](QUICK_REFERENCE_CARD.md)

## Current Operator Commands

```powershell
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
.\LAUNCH_GOODQ.ps1 -StartIngestion
conda run -n goodq_core python -m cli.watchdog
python -m api.server
```

## Important Note

Prefer explicit `conda run -n goodq_core ...` bindings for supported runtime operations.

Do not treat older activated-shell guidance as canonical operator policy.

## Historical Note

The previous contents of this file predated the current launcher/runbook cleanup and mixed active commands with older step names, legacy paths, and superseded operational advice.
