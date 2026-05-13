<!-- DOC_BADGE: REVIEW_MATRIX -->
<!-- DOC_STATUS: DRAFT_REVIEW -->
<!-- DOC_LAST_VERIFIED: 2026-05-12 -->

# Reference Pack v0 License Review Matrix

## 1. Purpose

This document is a source and license review matrix for Reference Pack v0
candidates. It records what is known, what remains unresolved, and what must be
reviewed before any payload movement.

This matrix is not:

- a payload manifest
- a download plan
- archive staging authorization
- installer authorization
- a license grant

No payload is approved for download, copy, staging, bundling, cloud-bank use, or
installer inclusion by this matrix alone.

## 2. Authority

This matrix is subordinate to:

- [CORPUS_PACK_MANIFEST.md](CORPUS_PACK_MANIFEST.md)
- [CORPUS_PACK_INVENTORY_LEDGER.md](CORPUS_PACK_INVENTORY_LEDGER.md)
- [REFERENCE_PACK_V0_SELECTION_PROPOSAL.md](REFERENCE_PACK_V0_SELECTION_PROPOSAL.md)

The manifest is the policy layer. The inventory ledger is the classification
layer. The selection proposal names low-risk candidates. This matrix records
license/source review status only.

## 3. Review Principles

- Official source surfaces are preferred.
- License clarity beats usefulness.
- Redistribution rights must be explicit.
- NAS eligibility does not automatically imply cloud eligibility.
- Cloud eligibility does not automatically imply installer eligibility.
- Gated datasets require separate review.
- Private media is excluded.
- Seinfeld/test-run material is excluded.
- Witness outputs are excluded.
- Memory snapshots are excluded.
- No asset is approved until source, license, attribution, and packaging status
  are clear.

## 4. Candidate Review Table

| candidate_name | official_source_url | source_owner_or_publisher | proposed_use | proposed_pack_class | license_summary | redistribution_status | attribution_required | commercial_use_status | modification_status | cloud_bank_eligible | nas_pack_eligible | offline_bundle_eligible | installer_eligible | refresh_cadence | risk_level | blockers | review_status | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wikimedia text dump slice | `https://dumps.wikimedia.org/` and `https://dumps.wikimedia.org/legal.html` | Wikimedia Foundation and project contributors | General reference text substrate for contextual lookup, not personal memory. | `reference_knowledge` | Wikimedia dump legal notes say textual content is generally GFDL plus CC BY-SA 4.0, with exceptions and controlling project terms. Fair-use or infringing content may exist in dumps. | yes, license-bound | yes | yes, license-bound | yes, share-alike/license-bound | unknown until exact project/dump and attribution package are selected | yes, after exact dump and metadata are selected | yes, optional reference pack only | no for base installer; unknown for optional installer add-on | pinned dump date, review before refresh | medium | exact project, dump date, namespace/content scope, attribution text, exception handling, hash format | review_needed | Select one small official Wikimedia project/dump slice, then record license, attribution, dump date, archive format, size, and checksum plan. |
| Wikidata entity dump slice | `https://www.wikidata.org/wiki/Wikidata:Database_download` | Wikimedia Foundation and Wikidata contributors | Offline entity IDs, aliases, and structured reference joins. | `reference_knowledge` | Wikidata database page states structured data in main, Property, Lexeme, and EntitySchema namespaces is CC0; text in other namespaces is CC BY-SA and media has other licenses. | yes for selected CC0 structured namespaces; unknown for other namespaces/media | no for CC0 structured data; yes or unknown for non-CC0 namespaces | yes for selected CC0 structured namespaces | yes for selected CC0 structured namespaces | unknown until selected namespace/dump scope is recorded | yes, after scope is restricted and recorded | yes, optional reference pack only | no for base installer; unknown for optional installer add-on | weekly source cadence; pin selected dump date | low to medium | exact dump format, namespace scope, exclusion of media/other namespaces, size, checksum format | review_needed | Prefer JSON entity dump subset or selected namespace scope; record CC0 scope explicitly before staging. |
| Geofabrik / OpenStreetMap regional extract | `https://download.geofabrik.de/` and `https://www.openstreetmap.org/copyright` | OpenStreetMap Foundation, OSM contributors, Geofabrik extract service | Offline place, road, POI, and region context for user-owned media. | `geo` | OSM data is licensed under ODbL. Copying, distribution, transmission, and adaptation are allowed with credit and share-alike obligations. Attribution and license notice are required. | yes, license-bound | yes | yes, license-bound | yes, share-alike/license-bound | unknown until ODbL obligations and attribution display/storage are designed | yes, after region/date/license metadata are recorded | yes, optional geo/reference pack only | no for base installer; unknown for optional installer add-on | select region/date; review source update cadence before refresh | medium | region selection, attribution strategy, ODbL notice, derived-database handling, checksum format | review_needed | Select one small region, record ODbL obligations, attribution text, region date, and package metadata before staging. |
| NOAA solar/time helper references | `https://gml.noaa.gov/grad/solcalc/` | NOAA Global Monitoring Laboratory | Temporal and solar-position context for timestamps, shadows, seasonality, and forensic hypotheses. | `temporal_astronomy` | NOAA/GML page is official, but the calculator is no longer actively supported and is provided for research and entertainment use; exact redistributable artifact or method must be selected. | unknown | unknown | unknown | unknown | unknown | yes, as source-linked reference after method/artifact selection | unknown until exact artifact/method is selected | no for base installer; unknown for optional installer add-on | pin source page or calculation details date | medium | exact artifact versus method, license/use terms, unsupported-status warning, validation method | review_needed | Verify official calculation-details page and decide whether to package source notes, formulas, or only source links. |
| Ready.gov preparedness reference slice | `https://www.ready.gov/be-informed` and `https://www.ready.gov/terms-and-conditions` | FEMA / Ready.gov / U.S. Department of Homeland Security | Civic preparedness reference material; not emergency, medical, or legal authority. | `survival_resilience` | Ready.gov is an official U.S. government preparedness source. Terms emphasize general information, responsibility to monitor changes, trademarks, and disclaimers; exact pages/PDFs still need terms review. | unknown | unknown | unknown | unknown | unknown | yes, after exact pages/PDFs and terms are recorded | unknown until exact pages/PDFs and terms are recorded | no for base installer; unknown for optional installer add-on | reviewed source date, refresh after official updates | medium | exact selected pages/PDFs, content reuse terms, trademark handling, high-stakes disclaimer wording | review_needed | Select a small page/PDF slice and record terms, source date, attribution/trademark treatment, and non-authority warnings. |
| NRC Emotion Lexicon | `https://saifmohammad.com/WebPages/AccessResource.htm` | National Research Council Canada / Saif M. Mohammad | Optional local emotion-language lookup if the operator has appropriate rights. | `emotion_language` | NRC access page requires selecting non-commercial or commercial license, requires citation/acknowledgment, and says not to redistribute the data. | no for bundled redistribution without separate permission | yes | unknown; commercial license required for commercial use | unknown | no | yes only as private/operator-provided cache | no unless separate permission allows packaging | no | version pinned if licensed | high | redistribution prohibition, license class, product/application acknowledgment, commercial rights | deferred | Do not include in Reference Pack v0 payload. Keep as license-review item or replace with clearer-license lexicon. |
| Red Cross preparedness material | `https://www.redcross.org/get-help/how-to-prepare-for-emergencies.html` and `https://www.redcross.org/terms-of-use.html` | The American National Red Cross | Possible preparedness reference material if separately licensed. | `survival_resilience` | Red Cross Terms of Use grant a personal, revocable, nontransferable, nonexclusive license for personal non-commercial use and restrict copying, distribution, modification, sublicensing, and commercial exploitation except as expressly permitted. | no without separate permission | yes | no without separate permission | no without separate permission | no | unknown for private NAS link-only reference; no for payload copy without permission | no | no | reviewed source date only if separately approved | high | separate permission, non-commercial limit, copying/distribution limits, modification limits, trademark restrictions | deferred | Do not include in Reference Pack v0 payload. Keep link-only citation or seek separate written permission before packaging. |

## 5. Explicit Non-Cleared Items

These items are not cleared for Reference Pack v0:

- Broad Hugging Face datasets without per-dataset license review.
- COCO, Common Voice, or other gated datasets unless separately reviewed.
- Seinfeld media, transcripts, embeddings, memory, or derived media.
- Private home media.
- Fresh witness outputs.
- Control recurrence reports.
- Memory snapshots.
- Local `broad_sample.mp4`.
- Local non-cleared PDF samples unless source and license are resolved.
- Runtime model cache assets; those belong in `model_cache_pack`, not Reference
  Pack v0.

## 6. Pack Eligibility Definitions

- **NAS pack eligible** means the asset may be a candidate for private local NAS
  storage after source, license, attribution, and checksum metadata are recorded.
- **Cloud-bank eligible** means the asset may be eligible for cloud-synchronized
  reference storage. This is stricter than NAS eligibility because distribution,
  account, service, and access-control terms may differ.
- **Offline-bundle eligible** means the asset may be packaged as an optional
  offline reference payload after source, license, attribution, archive format,
  size, hash, and validation method are recorded.
- **Installer eligible** means the asset may be included in an installer or
  installer add-on. This is the strictest decision and requires explicit
  redistribution rights plus installer-specific packaging review.

These are separate decisions. A source can be NAS-eligible and still be
cloud-bank-ineligible, offline-bundle-ineligible, or installer-ineligible.

## 7. Open Questions

- Exact source URLs for selected artifacts.
- Exact license terms for each selected artifact.
- Attribution requirements and required wording.
- Redistribution rights for NAS, cloud-bank, offline bundle, and installer
  contexts.
- Whether generated derivatives are allowed.
- Whether derived databases trigger share-alike or attribution requirements.
- Archive format.
- Checksum manifest format.
- Refresh cadence and stale-source warnings.
- Whether cloud-bank eligibility differs from NAS eligibility.
- Whether installer inclusion is allowed.
- Whether each source should include a machine-readable metadata record with
  source URL, publisher, date, license, attribution, and intended use.

## 8. Recommended Next Action

Perform source-link verification and license review only:

1. Choose exact candidate artifact scope, not payload bytes.
2. Record official source URL and selected source date.
3. Record license terms, attribution text, and redistribution status.
4. Mark NAS, cloud-bank, offline-bundle, and installer eligibility separately.
5. Leave all downloads, copying, archive creation, and checksum generation for a
   later explicit staging pass.
