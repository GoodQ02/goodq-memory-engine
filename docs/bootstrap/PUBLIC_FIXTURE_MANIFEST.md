<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-08-02 -->

# Public Fixture Workflow

## Bundled-media status

| Path | Release status | Reason |
| --- | --- | --- |
| *(none)* | No media is bundled | Avoids stale, unlicensed, or unverifiable test assets |

## Current on-demand workflow

- `scripts/bootstrap_onboarding.py` fetches a bounded local clip from NASA
  Images asset `20230830_OSIRIS_Briefing_hbr`, *Press Conference - OSIRIS-REx
  Sample Return*. The official source metadata names six briefing participants,
  making it useful for speech, entity, and scene-path smoke coverage.
- The source is fetched at run time, transcoded locally, and remains ignored;
  it is not redistributed by this repository.
- NASA's media guidelines apply. Before changing the source, record the exact
  NASA asset ID, source URL, selection reason, and any rights notice shown on
  that asset. Do not use third-party media merely because it appears on a
  NASA-hosted page.
- Do not combine the local smoke with private reports, generated witness
  outputs, or user media.
- The future public path is two-tiered: a deterministic generated installation
  clip plus a separately pinned, per-asset-cleared audiovisual fixture for
  speech and scene coverage.
- Any bundled media asset requires a separate ownership or license record and
  a new manifest entry before inclusion.
