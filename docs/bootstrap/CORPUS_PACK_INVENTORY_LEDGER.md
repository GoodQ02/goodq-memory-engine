<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: INVENTORY -->
<!-- DOC_LAST_VERIFIED: 2026-05-12 -->

# Corpus Pack Inventory Ledger

## 1. Inventory Summary

This ledger is the first read-only inventory for GoodQ4All corpus, reference-bank, scaffold, and optional dataset material. It records what is known, what is eligible for future NAS/offline pack selection, and what is explicitly excluded from product, installer, demo, reference-bank, and cloud-bank use.

This ledger is not a download plan, copy manifest, license grant, memory snapshot, or installer payload seal. No dataset, media item, witness artifact, or memory output becomes base-installer-required by appearing here.

## 2. Policy Authority

The governing policy is [CORPUS_PACK_MANIFEST.md](CORPUS_PACK_MANIFEST.md). This ledger is subordinate to that manifest and to the offline bundle contract:

- [OFFLINE_BUNDLE_CONTRACT.md](../archive/bootstrap/OFFLINE_BUNDLE_CONTRACT.md)
- [OFFLINE_BUNDLE_REBUILD_PLAN.md](../archive/bootstrap/OFFLINE_BUNDLE_REBUILD_PLAN.md)

The hard policy remains:

- Seinfeld/test-run media is foreign scaffold evidence only.
- Private home media is user-owned local media only.
- Public/demo debug material must use owned synthetic media.
- Optional corpora and reference banks are never base-installer-required without a specific runtime proof.
- No memory snapshot is selected.

## 3. Selected Inventory Table

### Runtime And Installer Adjacent Assets

| asset_name | local_path_if_any | source_or_origin | size_if_known | license_status | purpose | pack_class | base_installer_required | desktop_cache_required | nas_pack_candidate | cloud_bank_eligible | offline_bundle_eligible | redistributable | refresh_cadence | risk | recommended_action | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GoodQ source tree | repo root | GoodQ project source | about 90 MB from dry-run manifest | redistributable | Base source and bootstrap logic | runtime_core | yes | yes | yes | yes | yes | yes | per release | none | keep | Source pack only; excludes local reports, caches, media, and private memory. |
| Bootstrap docs and contracts | `docs/bootstrap/` | GoodQ documentation | about 128 KB from dry-run manifest | redistributable | Operator contract and install policy | runtime_core | yes | yes | yes | yes | yes | yes | per release | staleness | keep | This ledger adds selection detail; contract remains authority for install packs. |
| Public config templates | `configs/`, `.env.example` style surfaces | GoodQ project templates | about 27 KB from dry-run manifest | redistributable | Reproducible config starting point | runtime_core | yes | yes | yes | yes | yes | yes | per release | operational | keep | Must not include secrets or machine-local overrides. |
| Windows package cache | local conda/pip cache selected by dry-run manifest | Conda and Python package caches | about 9.8 GB from dry-run manifest | separate-license | Offline Windows env reconstruction | runtime_core | yes | yes | yes | no | yes | unknown | per locked release | legal, staleness, size | license_review | Package redistribution must be checked by package/license before external sharing. |
| WSL audio wheelhouse | `wsl2_audio/` staged wheelhouse and scripts | GoodQ WSL audio lane | about 3.15 GB wheelhouse plus small scripts | separate-license | Offline WSL audio runtime bootstrap | runtime_core | yes | yes | yes | no | yes | unknown | per WSL lane seal | legal, staleness, operational | keep | Canonical WSL lane remains the sealed cu121 runtime contract. |
| WSL system package strategy | WSL package payload or distro export lane | Linux system packages or exported distro | about 186 MB partial payload; optional distro export about 48 GB | separate-license | Offline WSL system dependency reproduction | runtime_core | yes for full offline desktop | yes | yes | no | yes | unknown | per platform seal | legal, operational, size | defer | Strategy is not fully sealed; exported distro is the cleanest near-term reproducibility lane. |
| Runtime Hugging Face model cache | `%GOODQ_MODEL_CACHE_ROOT%/hub` | Bootstrap model registry and pinned HF snapshots | about 122.6 GB from dry-run manifest | separate-license | Runtime model availability | model_cache | yes for full local pipeline | yes | yes | no | yes | unknown | per model-registry seal | legal, staleness, size | license_review | Preserve HF snapshots, blobs, and refs structure; do not package tokens. |
| Whisper and YOLO assets | `%GOODQ_MODEL_CACHE_ROOT%` | Model registry and local model cache | about 3.1 GB from dry-run manifest | separate-license | Speech and object detection runtime | model_cache | yes for full local pipeline | yes | yes | no | yes | unknown | per model-registry seal | legal, staleness | license_review | Runtime assets, not reference-bank corpora. |
| Lexicons and transformer modules | `%GOODQ_MODEL_CACHE_ROOT%` and related cache roots | Optional/runtime NLP assets | about 6.0 GB from dry-run manifest | separate-license | Text enrichment and local model support | model_cache | no unless registry marks required | yes | yes | no | yes | unknown | per registry seal | legal, staleness | classify_only | NRC-style lexicons may remain optional even when cached. |
| Qdrant portable payload | configured host-tool source | Qdrant release payload | about 65 MB from dry-run manifest | separate-license | Local vector database service | host_tool | yes | yes | yes | no | yes | unknown | per tool seal | legal, operational | license_review | Installed service is not enough; sealed offline payload needs hash and validation. |
| NSSM portable payload | configured host-tool source | NSSM release payload | about 369 KB from dry-run manifest | separate-license | Windows service wrapper | host_tool | yes where service install uses NSSM | yes | yes | no | yes | unknown | per tool seal | legal, operational | license_review | Host tool payload, not corpus content. |
| FFmpeg portable payload | configured host-tool source | FFmpeg build payload | about 299 MB from dry-run manifest | separate-license | Media decoding and probing | host_tool | yes | yes | yes | no | yes | unknown | per tool seal | legal, staleness | license_review | Required host tool for media workflows. |
| Tesseract portable payload | configured host-tool source | Tesseract OCR payload | about 249 MB from dry-run manifest | separate-license | OCR runtime support | host_tool | yes for full optional OCR | yes | yes | no | yes | unknown | per tool seal | legal, staleness | license_review | OCR is optional at runtime but part of full desktop capability. |
| Poppler portable payload | configured host-tool source | Poppler payload | about 26 MB from dry-run manifest | separate-license | PDF rendering/extraction helper | host_tool | yes for PDF-capable desktop | yes | yes | no | yes | unknown | per tool seal | legal, staleness | license_review | Keep contract and dry-run sizes reconciled before sealing. |
| Piper executable and voices | configured piper tool and voice paths | Piper voice runtime assets | about 102 MB from dry-run manifest | separate-license | Local TTS voice capability | host_tool | no unless TTS profile requires it | yes for full desktop | yes | no | yes | unknown | per voice/tool seal | legal, operational | license_review | Piper is located but not yet fully hash-sealed as a redistributable pack. |

### Local Media, Scaffold, Generated Evidence, And Memory

| asset_name | local_path_if_any | source_or_origin | size_if_known | license_status | purpose | pack_class | base_installer_required | desktop_cache_required | nas_pack_candidate | cloud_bank_eligible | offline_bundle_eligible | redistributable | refresh_cadence | risk | recommended_action | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Private family ingestion samples | `samples/ingestion/FAMILY/` | User-owned private media | about 92.4 GB observed | user-provided | Future personal memory input | user_owned_private_media | no | no | yes, private-only | no | no | no | operator-selected | privacy, size | classify_only | Not product, demo, installer, reference-bank, or cloud-bank material. |
| Seinfeld experiment media | `samples/ingestion/Sein_Experiment/` | Third-party scaffold/test media | about 38.0 GB observed | excluded | Historical pipeline proving scaffold | scaffold_evidence | no | no | no | no | no | no | none | legal, size | exclude | May be represented only by abstract audit notes; never package as corpus or demo content. |
| Broad sample video | `samples/ingestion/broad_sample.mp4` | Local sample artifact | about 154 MB observed | unknown | Historical sample or test input | evaluation | no | no | no | no | no | unknown | none | legal | license_review | Do not promote until ownership and intended use are clear. |
| Anger elimination PDF | `samples/ingestion/anger_elimination.pdf` | Local sample artifact | about 720 KB observed | unknown | Historical PDF sample | evaluation | no | no | no | no | no | unknown | none | legal | license_review | Do not package until source and redistribution status are clear. |
| Seinfeld reference anchors | `reports/reference_anchors/seinfeld/` | Abstracted evaluation anchors | about 5 KB observed | excluded | Non-media audit anchor evidence | scaffold_evidence | no | no | no | no | no | no | none | legal | classify_only | May remain only if abstract, legally safe, and audit-scoring oriented. |
| Fresh ingest witness outputs | `reports/fresh_ingest_runs/` | Generated runtime evidence | not computed | excluded | Local witness and validation artifacts | scaffold_evidence | no | no | no | no | no | no | per witness | privacy, size | classify_only | Not installer content or reference-bank memory. |
| Control recurrence outputs | `reports/control_recurrence/` | Generated observer artifacts | not computed | excluded | Local recurrence audit evidence | scaffold_evidence | no | no | no | no | no | no | per report | operational | classify_only | Keep untracked local reports out of commits and bundles unless a deliberate audit pack is created. |
| Branding source assets | `branding/goodbrand.svg`, `branding/favicon.ico`, `branding/site.webmanifest` | GoodQ project branding | about 2 MB observed | redistributable | Stable product identity assets | public_branding_assets | no | no | yes | yes | yes | yes | per release | none | keep | These are source assets, not generated docs or runtime memory. |
| Generated branding HTML exports | `branding/*.html` | Local design/export workflow | varies | excluded | Local review exports | scaffold_evidence | no | no | no | no | no | no | per design pass | staleness | classify_only | Ignored by default; promote only through a deliberate docs, demo, or release surface. |
| Scratch workspace artifacts | `scratch/` | Local operator workspace | varies | excluded | Temporary staging, holds, and dry-run payloads | workspace_hygiene | no | no | no | no | no | no | per task | privacy, staleness | exclude | Ignored by default; any durable evidence should move to an owned docs or reports surface before promotion. |
| Memory snapshot | none selected | Operator-controlled future export | none | user-provided | Optional seed memory | excluded | no | no | no | no | no | no | operator-selected | privacy | defer | Base GoodQ boots clean and creates new memory. |
| Owned synthetic debug kit | not yet selected | Future owned generated media and fixtures | none | redistributable | Public/demo/debug material | synthetic_debug | no | yes once created | yes | yes | yes | yes | per release | none | replace_with_synthetic | This is the correct replacement lane for public samples and demos. |

### Dataset Specs And Local Dataset Cache Candidates

| asset_name | local_path_if_any | source_or_origin | size_if_known | license_status | purpose | pack_class | base_installer_required | desktop_cache_required | nas_pack_candidate | cloud_bank_eligible | offline_bundle_eligible | redistributable | refresh_cadence | risk | recommended_action | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hugging Face dataset cache root | `%GOODQ_DATASET_CORPUS_ROOT%` | Local HF dataset cache | large; top-level cache observed | separate-license | Optional evaluation/research corpus storage | research | no | no | yes | no until license-reviewed | no for base; yes for optional corpus pack after review | unknown | operator-selected | legal, size, staleness | classify_only | Treat the large dataset cache as optional corpus only, never base installer. |
| `emotion` dataset spec | dataset spec registry | `scripts/dataset_specs.py` | unknown | unknown | Emotion-language baseline evaluation | emotion_language | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered and locally visible; source/license must be confirmed before packaging. |
| GLUE SST-2 | dataset spec registry | `nyu-mll/glue`, `sst2` | unknown | unknown | Sentiment/language evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered baseline dataset candidate. |
| IMDb | dataset spec registry | `stanfordnlp/imdb` | unknown | unknown | Sentiment/language evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered baseline dataset candidate. |
| WikiQA | dataset spec registry | `wiki_qa` | unknown | unknown | QA evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered baseline dataset candidate. |
| WikiText 103 | dataset spec registry | `Salesforce/wikitext`, `wikitext-103-raw-v1` | unknown | separate-license | Language modeling/reference text | reference_knowledge | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered candidate; not runtime-required. |
| Simple English Wikipedia dataset | dataset spec registry | `wikimedia/wikipedia`, `20231101.simple` | unknown | redistributable | General reference text candidate | reference_knowledge | no | no | yes | yes with license metadata | yes as optional reference pack only | yes | dated dump version | legal, staleness | license_review | Prefer official Wikimedia dump/source notes when packaging. |
| ScienceQA | dataset spec registry | `lmms-lab/ScienceQA` | unknown | unknown | Multimodal science QA evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered STEM evaluation candidate. |
| SciQ | dataset spec registry | `allenai/sciq` | unknown | unknown | Science QA evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered STEM evaluation candidate. |
| AI2 ARC | dataset spec registry | `allenai/ai2_arc` | unknown | unknown | Science reasoning evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered STEM evaluation candidate. |
| GSM8K | dataset spec registry | `gsm8k` | unknown | unknown | Math reasoning evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered STEM evaluation candidate. |
| MMLU | dataset spec registry | `cais/mmlu` | unknown | unknown | General benchmark evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered evaluation candidate. |
| SuperGPQA | dataset spec registry | `m-a-p/SuperGPQA` | unknown | unknown | Evaluation/research | research | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered research candidate. |
| Common Voice 17 | dataset spec registry | `mozilla-foundation/common_voice_17_0` | unknown | separate-license | Speech evaluation/training reference | evaluation | no | no | yes | no unless gated license satisfied | no until reviewed | unknown | versioned release | legal, size, privacy | license_review | Spec marks the dataset gated; do not package blindly. |
| LibriSpeech ASR | dataset spec registry | `openslr/librispeech_asr` | unknown | unknown | Speech recognition evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered audio evaluation candidate. |
| Speech Commands | dataset spec registry | `speech_commands` | unknown | unknown | Audio command evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered audio evaluation candidate. |
| ESC-50 | dataset spec registry | `ashraq/esc50` | unknown | unknown | Environmental sound evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered audio evaluation candidate. |
| VoxBox | dataset spec registry | `SparkAudio/voxbox` | unknown | unknown | Speech/audio research | research | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, privacy | license_review | Registered audio research candidate. |
| SUPERB | dataset spec registry | `superb` | unknown | unknown | Speech benchmark evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered speech benchmark candidate. |
| COCO 2017 | dataset spec registry | `phiyodr/coco2017` | unknown | separate-license | Vision evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered vision evaluation candidate. |
| HuggingFaceM4 COCO | dataset spec registry | `HuggingFaceM4/COCO` | unknown | separate-license | Vision evaluation | evaluation | no | no | yes | no unless gated license satisfied | no until reviewed | unknown | operator-selected | legal, size | license_review | Spec marks the dataset gated. |
| LFW | dataset spec registry | `bitmind/lfw` | unknown | unknown | Face/identity evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, privacy | license_review | Do not use as demo content. |
| North America land use | dataset spec registry | `MapSpaceORNL/north-america-landuse-3class-v1` | unknown | unknown | Geospatial evaluation/reference | geo | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered geospatial candidate. |
| Geospatial data v2 | dataset spec registry | `andersonluisamaral/geospatial_data_v2` | unknown | unknown | Geospatial research/reference | geo | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered geospatial candidate. |
| NASA/IBM hurricane dataset | dataset spec registry | `ibm-nasa-geospatial/hurricane` | unknown | unknown | Weather/geospatial research | geo | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal, size | license_review | Registered geospatial candidate. |
| Sunspot Hunter | dataset spec registry | `rmayormartins/sunspot-hunter` | unknown | unknown | Astronomy/solar evaluation | temporal_astronomy | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered astronomy candidate. |
| MiraBest radio astronomy | dataset spec registry | `kwazzi-jack/mirabest-radio-astronomy-unofficial` | unknown | unknown | Radio astronomy evaluation | temporal_astronomy | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered astronomy candidate. |
| Cardiff multilingual tweet sentiment | dataset spec registry | `cardiffnlp/tweet_sentiment_multilingual` | unknown | unknown | Multilingual sentiment evaluation | emotion_language | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered language/emotion candidate. |
| XNLI | dataset spec registry | `xnli` | unknown | unknown | Cross-lingual NLI evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered language evaluation candidate. |
| Alpaca | dataset spec registry | `tatsu-lab/alpaca` | unknown | unknown | Instruction-following research | research | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered research candidate; not product memory. |
| TweetEval | dataset spec registry | `tweet_eval` | unknown | unknown | Tweet classification evaluation | emotion_language | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered language/emotion candidate. |
| SuperGLUE RTE | dataset spec registry | `super_glue`, `rte` | unknown | unknown | NLI evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered evaluation candidate. |
| SQuAD | dataset spec registry | `squad` | unknown | unknown | QA evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered QA evaluation candidate. |
| RACE | dataset spec registry | `race` | unknown | unknown | Reading comprehension evaluation | evaluation | no | no | yes | license-dependent | no until reviewed | unknown | operator-selected | legal | license_review | Registered QA evaluation candidate. |

### External Reference-Bank Candidates

| asset_name | local_path_if_any | source_or_origin | size_if_known | license_status | purpose | pack_class | base_installer_required | desktop_cache_required | nas_pack_candidate | cloud_bank_eligible | offline_bundle_eligible | redistributable | refresh_cadence | risk | recommended_action | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wikimedia dumps | not selected | Official Wikimedia dump service | varies by dump | redistributable | General reference text and encyclopedic grounding | reference_knowledge | no | no | yes | yes with license metadata | yes as optional reference pack only | yes | pinned dump date | legal, staleness, size | license_review | Use official dump legal notes and preserve dump date/version. |
| Wikidata dumps | not selected | Official Wikidata database downloads | varies by dump | redistributable | Structured entity/reference graph candidate | reference_knowledge | no | no | yes | yes with license metadata | yes as optional reference pack only | yes | pinned dump date | legal, staleness, size | license_review | Prefer explicit dump, schema, and license metadata. |
| OpenStreetMap Geofabrik extracts | not selected | Geofabrik OSM extract service | varies by region | redistributable | Offline geospatial reference | geo | no | no | yes | yes with ODbL compliance | yes as optional geo pack only | yes | region/date pinned | legal, staleness, size | license_review | Select limited regions first; preserve ODbL attribution/requirements. |
| NRC Emotion Lexicon | optional cache if present | NRC emotion resource provider | small | separate-license | Emotion-language lexicon enrichment | emotion_language | no | no | yes | no until license reviewed | optional only after license review | unknown | version pinned | legal | license_review | Existing cache readiness treats this as optional. |
| ESA Gaia releases | not selected | ESA Gaia archive/release service | large | redistributable | Astronomy reference corpus | temporal_astronomy | no | no | yes | license-dependent | no until reviewed | unknown | release pinned | legal, size, staleness | defer | Select exact table/subset before any packaging. |
| NOAA solar position resources | not selected | NOAA/GML solar calculator and related resources | small to moderate | redistributable | Temporal/astronomy helper reference | temporal_astronomy | no | no | yes | license-dependent | optional after source review | unknown | version/date pinned | staleness | license_review | Prefer sourceable algorithms/data, not web-only calculator state. |
| FEMA Ready.gov material | not selected | Ready.gov public preparedness guidance | small to moderate | redistributable | Survival/resilience reference material | survival_resilience | no | no | yes | license-dependent | optional after source review | unknown | reviewed release/date | staleness, legal | license_review | Keep as reference, not medical/legal authority. |
| American Red Cross preparedness material | not selected | Red Cross emergency preparedness guidance | small to moderate | separate-license | Survival/resilience reference material | survival_resilience | no | no | yes | no until license reviewed | no until license reviewed | unknown | reviewed release/date | legal, staleness | license_review | Treat as separate-license until redistribution terms are verified. |

## 4. Seinfeld / Foreign Scaffold Evidence

Seinfeld-related media, transcripts, scene memory, embeddings, or derivative artifacts are scaffold evidence only. They are excluded from:

- product memory
- demo media
- base installer payloads
- optional corpus packs
- public sample content
- cloud-bank material
- user-facing reference-bank material

Abstract reference anchors may remain only if they are legally safe, non-media, non-transcript, and audit-scoring oriented. If a future demo or public debug flow needs media, it must use the owned synthetic debug kit.

## 5. Private Home Media

Private home media, including `samples/ingestion/FAMILY/` or equivalent operator-owned footage, is classified as `user_owned_private_media`. It is not installer content, demo content, product memory, reference-bank content, optional corpus content, or cloud-bank content.

Private media may be backed up by the operator as a private NAS media pack, but that is outside the GoodQ base installer and outside public release material.

## 6. Synthetic Debug Kit

The future synthetic debug kit is the correct lane for public demos, install smoke tests, and reproducible debug samples. It must be owned or clearly redistributable, small enough for practical packaging, and separate from personal memory, scaffold media, and research corpora.

Minimum future criteria:

- owned synthetic video/audio/text inputs
- known expected scene count and transcript facts
- small fixture size
- no private people, third-party show content, or uncontrolled licensed media
- expected output checklist for OCR, ASR, WSL audio, embeddings, Phase 6, and Qdrant

## 7. Reference-Bank Candidates

Reference-bank candidates remain optional. The first safe selection should favor sources with explicit official origins, stable versioning, and clear redistribution terms. Current promising lanes are:

- Wikimedia/Wikidata for general reference and entity grounding
- OSM/Geofabrik for geospatial reference
- NRC or replacement emotion lexicons for emotion-language support after license review
- ESA/NOAA astronomy and solar resources after subset and license review
- FEMA/Ready.gov style preparedness material after source review
- Red Cross material only after separate-license review

Dataset cache entries from `scripts/dataset_specs.py` are evaluation/research candidates unless a future audit proves a runtime reference-bank purpose.

## 8. Runtime / Base Installer Rule

The lean base installer includes runtime requirements only:

- source and bootstrap scripts
- public config templates
- locked Windows environment payloads
- WSL audio runtime payloads needed for the selected profile
- required model caches
- required host tools
- validation scripts and contracts

The base installer does not include:

- optional corpora
- research/evaluation datasets
- memory snapshots
- private media
- Seinfeld/scaffold media
- witness outputs
- generated control recurrence reports
- cloud-bank/reference-bank material unless an explicit optional pack is selected

## 9. Open Questions

- Which exact optional reference pack should be selected first: general knowledge, geo, temporal/astronomy, emotion-language, or survival/resilience?
- Which dataset specs have redistribution terms that are acceptable for a NAS/offline pack?
- Which local HF dataset cache entries are complete, partial, or stale?
- Should optional dataset pack hashes be computed per dataset cache directory, per source archive, or both?
- Should any existing local sample besides owned synthetic fixtures be retained as a private-only regression asset?
- Which Piper voices are intended for long-term sealed use, and what are their redistribution terms?
- Should WSL system packages be sealed through an exported distro, package payload mirror, or documented prerequisite?
- What is the smallest owned synthetic debug kit that proves the full multimodal pipeline without third-party media?

## 10. Recommended Next Action

Create a small docs-only Reference Pack v0 selection proposal that names 3 to 5 low-risk candidates, records their official source URLs, licensing assumptions, expected size class, and validation method, and explicitly keeps all downloads/copies deferred until the operator approves staging.

Useful official source pages for that proposal:

- Wikimedia dumps legal notes: `https://dumps.wikimedia.org/legal.html`
- Wikimedia dumps: `https://dumps.wikimedia.org/`
- Wikidata database downloads: `https://www.wikidata.org/wiki/Wikidata:Database_download`
- Geofabrik download service: `https://download.geofabrik.de/`
- NRC Emotion Lexicon access page: `https://saifmohammad.com/WebPages/AccessResource.htm`
- ESA Gaia DR3 release page: `https://www.cosmos.esa.int/web/gaia/dr3`
- NOAA solar calculator resources: `https://gml.noaa.gov/grad/solcalc/`
- Ready.gov preparedness topics: `https://www.ready.gov/be-informed`
- Red Cross emergency preparedness: `https://www.redcross.org/get-help/how-to-prepare-for-emergencies.html`
