<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-03-10 -->

# Open-Source Readiness Status

## Scope

This document describes the publication posture of the sanitized public branch, not
private development history or local runtime artifact trees.

## Current Verdict

`SAFE WITH MINOR FIXES`

The branch has cleared the major publication blockers:

- personal/private machine config removed from the public surface
- private runtime snapshots removed from the public surface
- copyrighted Seinfeld-derived text artifacts removed from the public surface
- tracked env-style files converted to example/template forms
- bootstrap installer added as a portable public entrypoint

## Public-Surface Rules

The public branch should contain:

- code
- documentation
- templates/examples
- bootstrap/install surfaces

The public branch should not contain:

- private runtime snapshots
- machine-local reports
- experiment rerun outputs
- copyrighted transcript or dialogue artifacts
- real local-only config files

## Known Remaining Risk

Residual risk is now concentrated in legacy portability debt:

- older utilities with literal Windows or WSL paths
- agent/control-plane helpers that still assume a developer workstation layout
- audit/reference docs that inventory those legacy literals

These are polish and support-surface issues, not active privacy leaks.

## Release Recommendation

For public publication:

1. Prefer the sanitized public branch over private development history.
2. Keep local-only state in `.env.local`, `configs/config.local.yaml`, and ignored
   runtime/report directories.
3. Treat `scripts/bootstrap_install.py` plus `environment.yml` as the supported
   onboarding path for new Windows hosts.

## Related Documents

- [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](INSTALL_BOOTSTRAP.md)
- [`docs/releases/SHIP_PROFILE.md`](../releases/SHIP_PROFILE.md)
- [`docs/bootstrap/SCRIPT_REGISTRY.md`](SCRIPT_REGISTRY.md)
