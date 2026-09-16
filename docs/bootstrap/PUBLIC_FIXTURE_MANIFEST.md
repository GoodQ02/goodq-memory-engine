<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-09-16 -->

# Public fixture scope

No personal media or prebuilt onboarding clip is bundled.
`scripts/install/generate_release_fixture_pack.py` creates deterministic synthetic
fixtures for the installer validation lane. Its fixture manifest and test suite
own those generated outputs; they are not speech-quality or personal-corpus proof.

For a realistic operator smoke, supply a short clip you own or are licensed to
process. The optional `scripts/bootstrap_onboarding.py` network helper is not a
preinstalled fixture or an offline readiness guarantee. Review source rights
before using external media. Keep generated media and private evidence ignored.
