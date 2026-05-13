<!-- DOC_BADGE: PROPOSAL -->
<!-- DOC_STATUS: DRAFT_SELECTION -->
<!-- DOC_LAST_VERIFIED: 2026-05-12 -->

# Reference Pack v0 Selection Proposal

## 1. Purpose

This document proposes the first small optional Reference Pack v0 selection for
GoodQ4All. It identifies low-risk candidates that may be worth license-reviewing
and later staging for NAS/offline/reference-bank use.

This proposal is not:

- a payload manifest
- a download plan
- a copy plan
- an installer requirement
- a memory snapshot
- a license grant

No payload movement is authorized by this document.

## 2. Authority

This proposal is subordinate to:

- [CORPUS_PACK_MANIFEST.md](CORPUS_PACK_MANIFEST.md)
- [CORPUS_PACK_INVENTORY_LEDGER.md](CORPUS_PACK_INVENTORY_LEDGER.md)

The manifest is the policy layer. The inventory ledger is the current
classification layer. This proposal only selects candidates for follow-up
review.

Follow-up source/license review matrix:

- [REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md](REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md)

## 3. Selection Principles

- Runtime assets stay separate from optional corpora.
- The base installer remains lean.
- No private media.
- No Seinfeld/test-run media.
- No memory snapshots.
- No fresh witness outputs.
- No recurrence artifacts.
- No gated or unclear-license corpus without review.
- Official source surfaces are preferred.
- The smallest useful first pack is preferred.
- License clarity beats feature excitement.

## 4. Recommended Reference Pack v0 Candidates

| candidate_name | source | proposed_pack_class | why_it_belongs | intended_use | redistributable_status | license_review_status | offline_bundle_eligible | nas_pack_candidate | cloud_bank_eligible | refresh_cadence | risk | recommended_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wikimedia text dump slice | `https://dumps.wikimedia.org/` and `https://dumps.wikimedia.org/legal.html` | `reference_knowledge` | Official source, broad general context, versionable dump surface, useful without becoming personal memory. | General reference substrate for contextual explanations, entity descriptions, and offline text grounding. | likely redistributable with attribution/share-alike obligations and project-specific exceptions | required before payload selection | yes after license metadata and dump date are recorded | yes | yes after license metadata is preserved | pinned dump date, reviewed before refresh | legal, staleness, size | license_review |
| Wikidata entity dump slice | `https://www.wikidata.org/wiki/Wikidata:Database_download` | `reference_knowledge` | Official structured entity dump surface; supports entity grounding without using witness memory as authority. | Offline entity IDs, aliases, coarse relationships, and reference joins. | likely redistributable for structured main/entity data, with namespace-specific terms | required before payload selection | yes after dump format, namespace scope, and license metadata are recorded | yes | yes after license metadata is preserved | pinned dump date, likely weekly source cadence | legal, staleness, size | license_review |
| Geofabrik OpenStreetMap regional extract | `https://download.geofabrik.de/` and `https://www.openstreetmap.org/export` | `geo` | Officially documented OSM extract route, region-selectable, smaller than full planet data, and useful for local-first place context. | Offline place, region, road, POI, and map-context grounding for user-owned media. | redistributable under ODbL-style obligations if attribution/share-alike requirements are met | required before payload selection | yes after region/date/license metadata are recorded | yes | yes after ODbL obligations are documented | pinned region/date; review source update cadence before refresh | legal, staleness, size | license_review |
| NOAA solar/time helper references | `https://gml.noaa.gov/grad/solcalc/` | `temporal_astronomy` | Official public scientific source surface; small, useful, and narrower than large astronomy catalogs. | Temporal and solar-position context for timestamps, shadows, seasonality, and forensic hypotheses. | likely redistributable/source-dependent; must avoid treating calculator output as sealed data without method notes | required before payload selection | unknown until exact artifact/method is selected | yes | unknown | version/date pinned for selected material | staleness, overclaiming | source_link_verification |
| Ready.gov preparedness reference slice | `https://www.ready.gov/be-informed` | `survival_resilience` | Official civic preparedness source, smaller than broad survival corpora, and useful as optional reference context. | Offline civic preparedness reference material; not emergency, medical, or legal authority. | likely redistributable/source-dependent; exact pages/PDFs need review | required before payload selection | unknown until exact pages/PDFs and terms are recorded | yes | unknown | reviewed source date; refresh after official updates | legal, staleness, high-stakes wording | license_review |

### Conditional Emotion-Language Candidate

NRC Emotion Lexicon remains a useful emotion-language candidate, but it should
not be automatically selected for Reference Pack v0. The current NRC access page
requires selecting a license, distinguishes non-commercial and commercial use,
and states that data should not be redistributed. Treat it as a review item, not
a pack payload.

| candidate_name | source | proposed_pack_class | why_it_belongs | intended_use | redistributable_status | license_review_status | offline_bundle_eligible | nas_pack_candidate | cloud_bank_eligible | refresh_cadence | risk | recommended_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NRC Emotion Lexicon | `https://saifmohammad.com/WebPages/AccessResource.htm` | `emotion_language` | Valuable small lexicon lane, but redistribution is explicitly constrained. | Optional local emotion-language lookup if the operator has appropriate license rights. | not redistributable as a bundled data payload without separate permission | required before any use beyond local/operator-provided cache | no until license is cleared | yes only as private/operator-provided asset | no until license is cleared | version pinned if licensed | legal | license_review |

## 5. Explicit Non-Selections For v0

Do not select these for Reference Pack v0:

- Seinfeld/test-run media, transcripts, embeddings, memory, or derived media.
- Private home media.
- Fresh witness outputs.
- Control recurrence reports.
- Memory snapshots.
- Broad Hugging Face dataset cache contents without per-dataset license review.
- COCO, Common Voice, or other gated datasets unless separately reviewed.
- Red Cross preparedness material unless separate-license review is complete.
- Local `broad_sample.mp4` unless source and redistribution status are resolved.
- Local non-cleared PDF samples unless source and redistribution status are
  resolved.
- Any runtime model cache asset; runtime models belong in `model_cache_pack`,
  not Reference Pack v0.

## 6. Proposed v0 Shape

Reference Pack v0 should stay small and boring:

1. General reference foundation:
   - Wikimedia text slice, or a smaller official Wikimedia project slice.
   - Wikidata entity slice only after dump format and namespace scope are
     selected.
2. Geo/time foundation:
   - one Geofabrik OSM regional extract
   - one NOAA solar/time reference surface or documented calculation method
3. Civic resilience foundation:
   - a small Ready.gov page/PDF slice after source-date and terms review
4. Optional emotion-language lane:
   - NRC only if license review permits local packaging, otherwise keep as
     operator-provided local cache or replace with a clearer-license lexicon.

This proposal deliberately avoids exact payload paths. The pack should receive
paths only when a selected source, license note, archive format, size, and hash
strategy are recorded.

## 7. Open License Questions

- What exact Wikimedia project, dump date, and content scope will be selected?
- Which Wikimedia license obligations must be preserved in the pack metadata?
- Which Wikidata namespaces or dump formats are selected, and which license terms
  apply to each?
- Which OSM/Geofabrik region is selected, and how will ODbL attribution and
  share-alike obligations be recorded?
- Which NOAA material is a sourceable artifact versus a web calculator interface?
- Which Ready.gov pages or PDFs are selected, and what use/redistribution terms
  apply to each?
- Is NRC permitted as a private local cache only, or can any redistributable
  emotion-language replacement be selected instead?
- Are any candidate sources unsuitable for cloud-bank use even if they are fine
  for private NAS storage?

## 8. Open Packaging Questions

- Exact source URLs for each selected artifact.
- Exact license terms and required attribution text.
- Archive format for the optional pack.
- Checksum manifest format.
- Refresh cadence and stale-pack warning policy.
- NAS directory convention.
- Whether cloud-bank eligibility differs from NAS eligibility.
- Whether pack validation should verify raw archive hash, unpacked file hashes,
  or both.
- Whether selected reference assets should include a machine-readable metadata
  file with source, date, license, and intended use.

## 9. Recommended Next Action

Create a docs-only license review table for these candidates. The table should
record official source URL, selected artifact scope, license terms, attribution
requirements, redistribution status, NAS eligibility, cloud-bank eligibility,
and a yes/no decision for Reference Pack v0 review.

Do not download, copy, or stage payloads in that next step.
