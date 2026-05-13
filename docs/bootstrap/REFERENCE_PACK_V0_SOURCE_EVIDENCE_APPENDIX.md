<!-- DOC_BADGE: EVIDENCE_APPENDIX -->
<!-- DOC_STATUS: SUPPORTING_EVIDENCE -->
<!-- DOC_LAST_VERIFIED: 2026-05-12 -->

# Reference Pack v0 Source Evidence Appendix

## 1. Purpose

This appendix records source-evidence facts for candidate Reference Pack v0
materials. It supports conservative packaging decisions by keeping source,
license, terms, attribution, and redistribution evidence visible before any
payload movement.

This appendix is not final legal approval, a payload manifest, a download plan,
installer authorization, or legal advice. It does not clear any candidate by
itself. A candidate can move beyond `review_needed` or `deferred` only when the
governing Reference Pack documents record explicit supporting evidence.

## 2. Evidence Rules

- Official source pages are preferred over mirrors, secondary summaries, or
  implementation convenience copies.
- Each candidate must record source URL, publisher, license or terms surface,
  redistribution status, attribution requirements, commercial-use status,
  modification status, packaging interpretation, blockers, and next action.
- Unclear or conflicting terms remain `review_needed` or `deferred`.
- Public-domain, open, permissive, or redistributable status must not be assumed
  without explicit source support.
- Dataset and evaluation corpus candidates remain separate from
  runtime-required installer assets.
- NAS pack, cloud-bank, offline-bundle, and installer eligibility are separate
  decisions.
- No candidate is payload-approved by this appendix alone.
- If source evidence is ambiguous, packaging status stays conservative.

## 3. Conservative Packaging Interpretation Table

| candidate | source / publisher | source evidence URL | license / terms summary | redistribution interpretation | attribution / share-alike / commercial / modification notes | packaging eligibility | status | blocker | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wikimedia text dump slice | Wikimedia Foundation and project contributors | `https://dumps.wikimedia.org/`; `https://dumps.wikimedia.org/legal.html` | Wikimedia dump legal notes describe textual content as generally GFDL plus CC BY-SA 4.0, with project-specific terms, exceptions, and possible fair-use or infringing material in dumps. | License-bound redistribution appears possible only after exact project, dump date, scope, attribution, and exception handling are recorded. | Attribution and share-alike obligations must be preserved; commercial and modification use are license-bound and must follow the selected project terms. | NAS: possible after metadata; cloud-bank: unknown until terms and access model are reviewed; offline bundle: optional only after metadata; installer: not cleared. | `review_needed` | Exact project, dump date, selected content scope, attribution text, exception handling, and checksum plan are missing. | Select one small official dump slice and record license, attribution, dump date, archive format, size, and checksum plan. |
| Wikidata entity dump slice | Wikimedia Foundation and Wikidata contributors | `https://www.wikidata.org/wiki/Wikidata:Database_download` | Wikidata database downloads distinguish CC0 structured data in selected namespaces from text, media, and other namespaces with different terms. | Redistribution appears clearer only for a selected CC0 structured-data scope; other namespaces and media remain out of scope unless separately reviewed. | CC0 structured data generally does not require attribution, but non-CC0 namespaces may; commercial and modification rights depend on selected namespace and artifact. | NAS: possible after scope restriction; cloud-bank: unknown until scope and terms are recorded; offline bundle: optional only after metadata; installer: not cleared. | `review_needed` | Exact dump format, namespace scope, exclusion rules, size, and checksum plan are missing. | Prefer a structured entity scope and record the CC0 boundary explicitly before staging. |
| Geofabrik / OpenStreetMap regional extract | OpenStreetMap Foundation, OSM contributors, and Geofabrik extract service | `https://download.geofabrik.de/`; `https://www.openstreetmap.org/copyright` | OSM data is under ODbL. Geofabrik provides regional extracts, but the OSM data license obligations still govern use. | License-bound redistribution may be possible when ODbL attribution, notice, and derived-database obligations are satisfied. | Attribution is required; share-alike or derived-database obligations may apply; commercial and modification use are license-bound under ODbL. | NAS: possible after region/date and ODbL metadata; cloud-bank: unknown until access and obligations are reviewed; offline bundle: optional only after metadata; installer: not cleared. | `review_needed` | Region, date, attribution strategy, ODbL notice handling, derived-database treatment, and checksum plan are missing. | Select one small region and record ODbL obligations, attribution text, extract date, and package metadata. |
| NOAA solar/time helper references | NOAA Global Monitoring Laboratory | `https://gml.noaa.gov/grad/solcalc/` | NOAA/GML solar calculator material is official, but the calculator page is no longer actively supported and exact redistributable artifact or method scope is not selected. | Redistribution is unknown until the selected artifact, formula, source note, or method text is identified and terms are reviewed. | Attribution, commercial use, and modification rights are unknown for a packaged artifact; unsupported-status wording must be preserved if referenced. | NAS: possible as source-linked reference after method selection; cloud-bank: unknown; offline bundle: unknown until exact artifact or method is selected; installer: not cleared. | `review_needed` | Exact artifact versus method, license or use terms, unsupported-status warning, and validation method are missing. | Verify official calculation-details material and decide whether to package source notes, formulas, or only source links. |
| Ready.gov preparedness reference slice | FEMA / Ready.gov / U.S. Department of Homeland Security | `https://www.ready.gov/be-informed`; `https://www.ready.gov/terms-and-conditions` | Ready.gov is an official preparedness source, but exact selected pages or PDFs and reuse terms must be reviewed before packaging. | Redistribution remains unknown until selected material and terms are recorded. | Attribution, trademark treatment, commercial use, modification rights, and high-stakes disclaimers need explicit review. | NAS: possible after exact pages or PDFs and terms are recorded; cloud-bank: unknown; offline bundle: unknown until terms are recorded; installer: not cleared. | `review_needed` | Exact pages or PDFs, reuse terms, attribution or trademark handling, and non-authority warnings are missing. | Select a small page/PDF slice and record terms, source date, attribution treatment, and warning language. |
| NRC Emotion Lexicon | National Research Council Canada / Saif M. Mohammad | `https://saifmohammad.com/WebPages/AccessResource.htm` | The access page requires a non-commercial or commercial license selection, requires citation or acknowledgment, and states that the data should not be redistributed. | Bundled redistribution is not cleared without separate permission or appropriate license evidence. | Attribution is required; commercial use requires commercial-license review; modification and redistribution rights are not clear for bundled packaging. | NAS: private/operator-provided cache only unless license allows more; cloud-bank: no; offline bundle: no unless separate permission allows packaging; installer: no. | `deferred` | Redistribution prohibition, license class, commercial rights, and product acknowledgment requirements are unresolved. | Do not include in Reference Pack v0 payload; keep as private/operator-provided cache or replace with clearer-license lexicon. |
| Red Cross preparedness material | The American National Red Cross | `https://www.redcross.org/get-help/how-to-prepare-for-emergencies.html`; `https://www.redcross.org/terms-of-use.html` | Red Cross terms grant limited personal, revocable, nontransferable, nonexclusive, non-commercial use and restrict copying, distribution, modification, sublicensing, and commercial exploitation unless expressly permitted. | Bundled redistribution is not cleared without explicit permission. | Attribution and trademark treatment would be required; copying, distribution, modification, and commercial use are restricted without permission. | NAS: link-only/private reference unknown; cloud-bank: no for payload copy; offline bundle: no; installer: no. | `deferred` | Separate permission, non-commercial limit, copying/distribution limits, modification limits, and trademark restrictions remain blockers. | Do not include in Reference Pack v0 payload; keep link-only citation or seek written permission before packaging. |

## 4. Candidate Evidence Records

### Wikimedia Text Dump Slice

- **Candidate name:** Wikimedia text dump slice
- **Intended reference-pack use:** General reference text substrate for
  contextual lookup, entity descriptions, and offline text grounding.
- **Official source surface:** `https://dumps.wikimedia.org/` and
  `https://dumps.wikimedia.org/legal.html`
- **Evidence summary:** Official dump and legal surfaces exist. Textual content
  is license-bound and includes project-specific terms and exceptions.
- **Conservative packaging interpretation:** Possible optional reference-pack
  candidate after exact dump, date, scope, attribution, and checksum metadata are
  recorded.
- **Status:** `review_needed`
- **Blocker / risk:** Project scope, attribution text, exception handling, and
  selected archive metadata are not yet recorded.
- **Next action:** Select one small official project/dump slice for a future
  clearance-decision pass. No downloads in this evidence pass.

### Wikidata Entity Dump Slice

- **Candidate name:** Wikidata entity dump slice
- **Intended reference-pack use:** Offline entity IDs, aliases, structured
  joins, and coarse reference relationships.
- **Official source surface:**
  `https://www.wikidata.org/wiki/Wikidata:Database_download`
- **Evidence summary:** Official database download documentation distinguishes
  CC0 structured-data namespaces from other content surfaces.
- **Conservative packaging interpretation:** Strong next-review candidate only
  if scope is restricted to clearly identified structured data and media/other
  namespaces remain excluded unless separately reviewed.
- **Status:** `review_needed`
- **Blocker / risk:** Exact dump format, namespace scope, exclusion rules, and
  checksum strategy are not yet recorded.
- **Next action:** Record a selected CC0 structured-data scope before any
  staging.

### Geofabrik / OpenStreetMap Regional Extract

- **Candidate name:** Geofabrik / OpenStreetMap regional extract
- **Intended reference-pack use:** Offline place, road, POI, region, and
  local-context grounding for user-owned media.
- **Official source surface:** `https://download.geofabrik.de/` and
  `https://www.openstreetmap.org/copyright`
- **Evidence summary:** Geofabrik provides region-selectable OSM extracts; OSM
  data remains governed by ODbL obligations.
- **Conservative packaging interpretation:** Plausible optional geo/reference
  candidate after region/date selection and ODbL compliance metadata.
- **Status:** `review_needed`
- **Blocker / risk:** Attribution, derived-database treatment, selected region,
  extract date, and checksum plan are missing.
- **Next action:** Select one small region and record ODbL notice, attribution,
  date, and packaging metadata before staging.

### NOAA Solar/Time Helper References

- **Candidate name:** NOAA solar/time helper references
- **Intended reference-pack use:** Temporal and solar-position context for
  timestamps, shadows, seasonality, and forensic hypotheses.
- **Official source surface:** `https://gml.noaa.gov/grad/solcalc/`
- **Evidence summary:** NOAA/GML is official, but the web calculator is not
  itself a selected artifact and carries unsupported-status context.
- **Conservative packaging interpretation:** Keep at `review_needed` until the
  candidate is narrowed to source notes, formulas, method documentation, or
  source links with explicit terms.
- **Status:** `review_needed`
- **Blocker / risk:** Exact artifact versus method is not selected; license/use
  and validation terms are not recorded.
- **Next action:** Verify calculation-details material and decide whether the
  reference pack should store method notes, formulas, or only source links.

### Ready.gov Preparedness Reference Slice

- **Candidate name:** Ready.gov preparedness reference slice
- **Intended reference-pack use:** Civic preparedness reference material for
  offline context, not emergency, medical, legal, or operational authority.
- **Official source surface:** `https://www.ready.gov/be-informed` and
  `https://www.ready.gov/terms-and-conditions`
- **Evidence summary:** Ready.gov is an official source, but exact pages or PDFs
  and reuse terms must be selected and reviewed.
- **Conservative packaging interpretation:** Possible future optional reference
  candidate only after source date, terms, attribution or trademark handling,
  and non-authority warnings are recorded.
- **Status:** `review_needed`
- **Blocker / risk:** Exact material, terms, attribution/trademark treatment,
  commercial use, modification rights, and high-stakes wording remain open.
- **Next action:** Select a small page/PDF slice and record terms before any
  payload movement.

### NRC Emotion Lexicon

- **Candidate name:** NRC Emotion Lexicon
- **Intended reference-pack use:** Optional local emotion-language lexicon if
  the operator has appropriate rights.
- **Official source surface:**
  `https://saifmohammad.com/WebPages/AccessResource.htm`
- **Evidence summary:** The access page requires license selection and states
  that data should not be redistributed.
- **Conservative packaging interpretation:** Not cleared for Reference Pack v0
  bundled payload. Private/operator-provided cache only unless separate rights
  are obtained.
- **Status:** `deferred`
- **Blocker / risk:** Redistribution, commercial use, modification rights, and
  product acknowledgment obligations remain blockers.
- **Next action:** Keep out of payload packaging or replace with a
  clearer-license lexicon.

### Red Cross Preparedness Material

- **Candidate name:** Red Cross preparedness material
- **Intended reference-pack use:** Possible preparedness reference material only
  if separately licensed.
- **Official source surface:**
  `https://www.redcross.org/get-help/how-to-prepare-for-emergencies.html` and
  `https://www.redcross.org/terms-of-use.html`
- **Evidence summary:** Terms restrict copying, distribution, modification,
  sublicensing, and commercial exploitation unless expressly permitted.
- **Conservative packaging interpretation:** Not cleared for Reference Pack v0
  bundled payload. Link-only citation or separate permission is required.
- **Status:** `deferred`
- **Blocker / risk:** Separate permission, non-commercial limits, copying and
  distribution restrictions, modification restrictions, and trademarks.
- **Next action:** Keep out of payload packaging unless written permission or a
  source-specific redistribution grant is obtained.

## 5. Non-Cleared / Deferred List

- NRC Emotion Lexicon remains non-cleared and `deferred` unless explicit
  redistribution permission or an appropriate license is obtained and recorded.
- Red Cross preparedness material remains non-cleared and `deferred` due to
  restrictive terms unless explicit permission is obtained and recorded.
- Any unclear candidate remains `review_needed`, not approved.
- This appendix does not approve downloads, copies, staging, archives,
  cloud-bank storage, offline-bundle inclusion, installer inclusion, or payload
  redistribution.

## 6. Explicit Packaging Boundary

- Reference Pack v0 evidence work does not put optional datasets into the base
  installer.
- Optional corpus and evaluation assets belong in separate corpus or reference
  packs.
- Seinfeld/test-run media, transcripts, embeddings, memory, and derived witness
  artifacts must not ship as base memory.
- Private home media must not ship as product, demo, public reference, or base
  installer content.
- Required runtime model cache assets are separate from optional dataset,
  evaluation, and reference-bank corpus assets.
- Fresh witness outputs, control recurrence reports, and memory snapshots do not
  become Reference Pack v0 payloads.

## 7. Relationship To Existing Docs

This appendix is subordinate supporting evidence for:

- [CORPUS_PACK_MANIFEST.md](CORPUS_PACK_MANIFEST.md)
- [CORPUS_PACK_INVENTORY_LEDGER.md](CORPUS_PACK_INVENTORY_LEDGER.md)
- [REFERENCE_PACK_V0_SELECTION_PROPOSAL.md](REFERENCE_PACK_V0_SELECTION_PROPOSAL.md)
- [REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md](REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md)
- [OFFLINE_BUNDLE_REBUILD_PLAN.md](OFFLINE_BUNDLE_REBUILD_PLAN.md)

The manifest remains the policy layer. The inventory ledger remains the
classification layer. The selection proposal names the candidate set. The
license review matrix records the current review state. This appendix records
the source-evidence trail needed for a future clearance-decision pass.
