<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_MANIFEST -->
<!-- DOC_LAST_VERIFIED: 2026-05-11 -->

# Corpus Pack Manifest

This manifest classifies GoodQ corpus, reference, debug, scaffold, and memory
surfaces for offline packaging decisions.

It is subordinate to:

- `docs/bootstrap/OFFLINE_BUNDLE_CONTRACT.md`
- `docs/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md`
- `docs/architecture/INGEST_ORCHESTRATION_CONTRACT.md`
- `docs/architecture/MEMORY_STORAGE.md`

It does not authorize downloads, ingestion, package changes, model changes,
copying large payloads, or memory snapshot creation.

Current candidate inventory ledger:

- `docs/bootstrap/CORPUS_PACK_INVENTORY_LEDGER.md`

Current Reference Pack v0 proposal:

- `docs/bootstrap/REFERENCE_PACK_V0_SELECTION_PROPOSAL.md`

Current Reference Pack v0 license/source review:

- `docs/bootstrap/REFERENCE_PACK_V0_LICENSE_REVIEW_MATRIX.md`
- `docs/bootstrap/REFERENCE_PACK_V0_SOURCE_EVIDENCE_APPENDIX.md`

## Doctrine

GoodQ keeps these lanes separate:

- **Runtime assets** let the pipeline run.
- **Reference bank assets** contextualize what the pipeline observes.
- **Dataset corpus assets** support eval, research, testing, or future training.
- **Synthetic debug kit assets** prove behavior with owned fixture media.
- **GoodQ memory** is created from user-owned ingested media.
- **Foreign scaffold evidence** can explain how the system was tested, but it is
  never product memory, demo media, installer content, or a memory seed.

The base installer must boot clean and create fresh memory. It must not inherit
Seinfeld/test-run memory, private home media, generated witness outputs, optional
dataset corpora, optional reference banks, or unselected memory snapshots.

## Required Inventory Fields

Every selected corpus/reference/debug/memory pack must record:

- asset name
- path token or source surface
- size
- source
- license
- purpose
- runtime required
- installer required
- desktop-cache required
- NAS/cloud-bank eligible
- redistributable
- hash present
- refresh cadence
- risk
- classification

Machine-local paths, secrets, and token-bearing files must not appear in this
manifest. Use the portable tokens from `OFFLINE_BUNDLE_CONTRACT.md`.

## Current Classification Ledger

| Asset or Surface | Path Token / Surface | Classification | Runtime Required | Base Installer | Desktop Cache | NAS / Cloud Bank | Redistributable | Hash State | Risk | Next Action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Required model cache | `%GOODQ_MODEL_CACHE_ROOT%` | `model_cache_pack` | yes | yes | yes | yes, private or licensed | mixed | computed in dry-run manifest | license / gated model terms | restore rehearsal |
| Host tools | `%GOODQ_HOST_TOOLS_ROOT%` | `host_tools_pack` | yes | yes | yes | yes | mixed | computed in dry-run manifest | tool licenses | restore rehearsal |
| Windows env payload | `%GOODQ_WINDOWS_ENV_PACK_ROOT%` | `windows_env_pack` | yes | yes | yes | yes | private installer payload | computed in dry-run manifest | package license closure | restore rehearsal |
| WSL audio payload | `%GOODQ_WSL_AUDIO_PACK_ROOT%` | `wsl_audio_pack` | full desktop parity | yes for desktop parity | yes | yes, private installer payload | private installer payload | computed in dry-run manifest | restore import rehearsal | restore rehearsal |
| HF dataset cache | `%GOODQ_DATASET_CORPUS_ROOT%` | `optional_dataset_corpus_pack` | no | no | optional | yes, selected corpus only | mixed / unknown | deferred | size / license / staleness | create selected corpus manifest before copying |
| Registered dataset specs | `scripts/dataset_specs.py` | optional eval/research/training catalog | no | no | optional | yes, after selection | mixed / unknown | not a payload | script-local path hints / license | classify each selected dataset before packaging |
| NRC Emotion Lexicon | `%GOODQ_MODEL_CACHE_ROOT%/lexicons/NRC-Emotion-Lexicon` | emotion/language reference asset | no | no unless license-cleared | optional | yes, if license permits | unknown until license cleared | model-cache dry-run evidence only | redistribution rights | treat as user-provided or separately licensed for public bundles |
| Wikipedia dumps | `%GOODQ_REFERENCE_BANK_ROOT%/wikipedia` | `optional_reference_bank_pack` | no | no | optional | yes, selected dump only | license-bound | not selected | size / refresh / attribution | select official dump date and hash before use |
| Wikidata dumps | `%GOODQ_REFERENCE_BANK_ROOT%/wikidata` | `optional_reference_bank_pack` | no | no | optional | yes, selected dump only | license-bound | not selected | size / refresh / attribution | select official dump date and hash before use |
| OpenStreetMap extracts | `%GOODQ_REFERENCE_BANK_ROOT%/geo/osm` | `optional_reference_bank_pack` | no | no | optional | yes, selected region only | license-bound | not selected | ODbL attribution / stale maps | select region/date before copying |
| Astronomy / solar references | `%GOODQ_REFERENCE_BANK_ROOT%/temporal_astro` | `optional_reference_bank_pack` | no | no | optional | yes, selected source only | source-dependent | not selected | overclaiming inference | label outputs as reference context or forensic hypotheses |
| Survival / resilience references | `%GOODQ_REFERENCE_BANK_ROOT%/survival` | `optional_reference_bank_pack` | no | no | optional | yes, selected source only | source-dependent | not selected | high-stakes use | label as reference material, not emergency or medical authority |
| Owned synthetic debug kit | `%GOODQ_SYNTHETIC_DEBUG_KIT_ROOT%` | `optional_synthetic_debug_kit_pack` | no | no | optional | yes | yes if owner-approved | not created | fixture absence | create short owned fixture and expected-output contract |
| Tracked sample artifacts | `<repo-root>/samples/ingestion` tracked files | source-pack test/demo artifacts | no | source-pack only | optional | no, unless selected | unknown | source hash only | unclear fixture rights | do not treat as public debug kit until ownership is clear |
| Ignored Seinfeld scaffold media | `<repo-root>/samples/ingestion/Sein_Experiment` local ignored media | foreign scaffold evidence / exclude | no | no | no | no | no | none | legal / cognitive contamination | keep out of product, installer, memory, and demo paths |
| Third-party reference anchors | `reports/reference_anchors/README.md` public boundary only | private audit aid / exclude | no | no | no | no | no | none | legal / public-product confusion | exclude payloads; public examples must use fictional, owned, synthetic, or permissively licensed fixtures |
| Ignored private home media | `<repo-root>/samples/ingestion/FAMILY` local ignored media | private source media / exclude from base | no | no | operator-owned only | private pack only | no | none | privacy | use only as future user-owned ingestion target |
| Fresh-ingest witness outputs | `%GOODQ_DATA_ROOT%/reports/fresh_ingest_runs` | generated witness evidence / exclude from base | no | no | optional evidence | private/archive only | no unless sanitized | per-run only | privacy / size / stale state | never seed base memory from witnesses |
| Control recurrence outputs | `%GOODQ_DATA_ROOT%/reports/control_recurrence` | generated observer evidence / exclude from base | no | no | optional evidence | private/archive only | no unless sanitized | local artifact | stale operator state | stage only intentionally selected docs |
| Memory snapshot | `%GOODQ_MEMORY_SNAPSHOT_ROOT%` | `optional_memory_snapshot_pack` | no | no | optional private migration | private pack only | no | none selected | privacy / stale memory | no action until operator selects a clean snapshot |
| Legacy root model cache | legacy noncanonical model cache root | drift evidence / exclude | no | no | no | no | no | duplicate material matched by hash | drift confusion | keep out unless a future manifest proves need |

## Reference Source Policy

Use canonical public sources when selecting reference packs:

- Wikimedia dumps for Wikipedia text snapshots:
  <https://dumps.wikimedia.org/>
- Wikidata database downloads:
  <https://www.wikidata.org/wiki/Wikidata:Database_download>
- OpenStreetMap extracts by selected region/date:
  <https://download.geofabrik.de/>
- NRC emotion lexicons only under an appropriate license:
  <https://saifmohammad.com/WebPages/AccessResource.htm>
- Gaia archive material for star catalog references:
  <https://www.cosmos.esa.int/web/gaia/dr3>
- NOAA solar calculators or published calculation references:
  <https://gml.noaa.gov/grad/solcalc/>
- Public preparedness references from official sources such as FEMA/Ready.gov,
  Red Cross, NOAA/NWS, CDC, USDA extension, or local emergency management.

Hugging Face mirrors can be useful implementation sources only when the selected
dataset is versioned, license-reviewed, hash-recorded, and classified outside
personal memory.

## Selection Rules

1. No dataset becomes installer-required unless a runtime contract proves it.
2. No reference-bank fact becomes GoodQ personal memory.
3. No foreign scaffold media becomes demo, product, installer, or memory seed
   content.
4. No private home media enters a public or base bundle.
5. No generated witness output seeds a base install.
6. No high-stakes reference pack may use authority language beyond the selected
   source and confidence evidence.
7. No selected optional pack is sealed until size, source, license, hash, refresh
   cadence, and validation command are recorded.

## Open Work

- Create a selected optional dataset corpus manifest before copying the large
  dataset cache to NAS or installer storage.
- Create a selected optional reference-bank manifest before copying external
  reference sources.
- Produce an owned synthetic debug fixture and expected-output contract.
- Decide later, with explicit operator approval, whether any private memory
  snapshot should exist. None is selected now.
