# Qori Archive Lynx Pet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate, validate, package, and install Qori as a Codex-compatible v2 animated pet that embodies GoodQ4All's local-first, scene-centric, auditable, and resilient mission.

**Architecture:** Keep visual generation isolated to one `$imagegen` worker per job, with the selected base image serving as the canonical identity reference for every later row. The parent agent owns manifest updates and all deterministic processing: frame extraction, atlas assembly, transparency cleanup, direction validation, packaging, and cleanup. All generated artifacts live outside the repository under `%USERPROFILE%\.codex\pet-runs\qori-v2`.

**Tech Stack:** Codex `$imagegen`, Hatch Pet deterministic Python scripts, bundled workspace Python with Pillow, PowerShell, PNG/WebP, JSON.

## Global Constraints

- Use the bundled Python returned by `codex_app__load_workspace_dependencies`; never use bare system `python`.
- Use `%USERPROFILE%\.codex\skills\hatch-pet` as the skill directory.
- Use `%USERPROFILE%\.codex\pet-runs\qori-v2` as the run directory.
- Use `%USERPROFILE%\.codex\pets\qori` as the installation directory.
- Keep the GoodQ4All repository unchanged during pet production.
- Build an 8 x 11 v2 atlas from 192 x 208 cells; final dimensions must be 1536 x 2288.
- Package with `spriteVersionNumber: 2`.
- Keep Qori's five tail plates inside one broad connected silhouette; material boundaries and cyan seams show segmentation without narrow gaps.
- Use no text, logos, screens, cloud imagery, floor, shadow, glow, scenery, or detached effects.
- Generate every visual job with `$imagegen`; use deterministic scripts only for layout, extraction, registration, safe mirroring, assembly, cleanup, previews, and validation.
- Never patch a generated look cell individually; repair the complete containing eight-pose row.
- Cardinal look directions are hard gates: 000 up, 090 screen-right, 180 down, and 270 screen-left.
- Do not package until deterministic validation, blind direction validation, explicit 16-direction semantics, continuity review, and independent final visual QA pass.

## File Map

- Read: `docs/superpowers/specs/2026-07-10-qori-archive-lynx-pet-design.md` — approved design authority.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\pet_request.json` — normalized Qori request and chroma key.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\imagegen-jobs.json` — visual job dependency graph and selected-source provenance.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\references\canonical-base.png` — visual identity authority.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\*.png` — selected row-strip outputs.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\frames\` — deterministically extracted standard frames.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\final\spritesheet-extended.webp` — final v2 atlas.
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\` — contact sheets, previews, per-row review folders, direction evidence, validation, and run summary.
- Create: `%USERPROFILE%\.codex\pets\qori\pet.json` — installed v2 package manifest.
- Create: `%USERPROFILE%\.codex\pets\qori\spritesheet.webp` — installed Qori atlas.

---

### Task 1: Preflight and Prepare the Qori Run

**Files:**
- Read: `docs/superpowers/specs/2026-07-10-qori-archive-lynx-pet-design.md`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\pet_request.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\imagegen-jobs.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\prompts\`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\references\layout-guides\`

**Interfaces:**
- Consumes: approved Qori design specification and bundled Python path.
- Produces: prepared run folder, chosen chroma key, exact visual prompts, and job dependency graph.

- [ ] **Step 1: Load the bundled workspace runtime**

Call `codex_app__load_workspace_dependencies` and record the returned Python executable as `$PYTHON` for every deterministic command.

Expected: an absolute bundled Python path with Pillow available.

- [ ] **Step 2: Prepare the run folder**

Run in PowerShell after setting `$PYTHON` to the returned path:

```powershell
$SKILL_DIR = Join-Path $env:USERPROFILE '.codex\skills\hatch-pet'
$RUN_DIR = Join-Path $env:USERPROFILE '.codex\pet-runs\qori-v2'
& $PYTHON (Join-Path $SKILL_DIR 'scripts\prepare_pet_run.py') `
  --pet-name 'Qori' `
  --description 'Qori is a local-first archive lynx who watches every scene, protects persistent memory, and brings calm, auditable focus to the work.' `
  --output-dir $RUN_DIR `
  --pet-notes 'Compact archive lynx and organic guardian with cultivated machine anatomy; charcoal-indigo fur; matte graphite bioceramic brow, shoulder, chest, and one broad connected five-plate tail; cyan physical eye rings and connective seams; embedded amber scene-core; restrained moss accents; broad grounded paws; calm intelligent half-smile; technology grown into the body.' `
  --style-preset '3d-toy' `
  --style-notes 'Tactile plush-bioceramic 3D storybook mascot. Keep the five tail plates inside one connected silhouette, divided by material boundaries and cyan seams without narrow gaps. Low-noise, warm, precise, and readable at pet size.' `
  --force
```

Expected: `pet_request.json`, `imagegen-jobs.json`, prompts, and layout guides exist under `$RUN_DIR`.

- [ ] **Step 3: Verify job topology and chroma separation**

```powershell
$request = Get-Content (Join-Path $RUN_DIR 'pet_request.json') -Raw | ConvertFrom-Json
$jobs = Get-Content (Join-Path $RUN_DIR 'imagegen-jobs.json') -Raw | ConvertFrom-Json
$request | Select-Object pet_id, display_name, description, chroma_key
$jobs.jobs | Select-Object id, kind, status, depends_on, output_path
```

Expected: pet id `qori`; one base job; nine standard rows; `look-cardinals`; `look-row-9`; `look-row-10`; chroma key visually distinct from cyan, amber, moss, graphite, and indigo.

### Task 2: Generate and Approve Qori's Canonical Base

**Files:**
- Read: `%USERPROFILE%\.codex\pet-runs\qori-v2\prompts\base-pet.md`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\base.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\references\canonical-base.png`
- Modify: `%USERPROFILE%\.codex\pet-runs\qori-v2\imagegen-jobs.json`

**Interfaces:**
- Consumes: prepared base prompt with no external reference image.
- Produces: one approved full-body Qori image used as the identity lock for every row.

- [ ] **Step 1: Dispatch one isolated base worker**

Give the worker only the base job, prompt path, and these hard checks:

```text
Use $imagegen only. Generate one centered full-body Qori on the prepared flat chroma background. Preserve a compact archive-lynx silhouette, charcoal-indigo fur, matte graphite bioceramic armor, cyan physical eye rings and connected seams, embedded amber scene-core, moss accents, broad paws, and one broad connected tail with exactly five visible plates. No text, scenery, shadow, glow, gadgets, floating effects, or narrow gaps between tail plates. Return exactly two lines: `selected_source=` followed by the generated PNG's absolute filesystem path, then `qa_note=` followed by one sentence.
```

Expected: one selected PNG source and a QA note confirming full-body composition, connected anatomy, and forbidden-element absence.

- [ ] **Step 2: Copy the exact selected output and establish identity provenance**

The parent maps the worker's exact `selected_source` value into the `QORI_BASE_SELECTED_SOURCE` process variable before this shell step:

```powershell
if ([string]::IsNullOrWhiteSpace($env:QORI_BASE_SELECTED_SOURCE)) { throw 'QORI_BASE_SELECTED_SOURCE is required' }
$SOURCE = $env:QORI_BASE_SELECTED_SOURCE
if (-not (Test-Path -LiteralPath $SOURCE -PathType Leaf)) { throw "Selected base source does not exist: $SOURCE" }
Copy-Item -LiteralPath $SOURCE -Destination (Join-Path $RUN_DIR 'decoded\base.png') -Force
Copy-Item -LiteralPath (Join-Path $RUN_DIR 'decoded\base.png') -Destination (Join-Path $RUN_DIR 'references\canonical-base.png') -Force
```

Expected: both files exist and have identical hashes.

- [ ] **Step 3: Visually approve the base at pet scale**

Inspect only the canonical base. Reject it if Qori is cropped, humanoid, militarized, generic-robotic, over-detailed, detached, shadowed, or lacks a readable embedded core and connected five-plate tail.

Expected: Qori reads immediately as a warm archive lynx and remains legible when reduced near 192 x 208.

- [ ] **Step 4: Mark the base job complete**

```powershell
$manifestPath = Join-Path $RUN_DIR 'imagegen-jobs.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$baseJob = $manifest.jobs | Where-Object id -eq 'base'
$baseJob.status = 'complete'
$baseJob.source_path = $SOURCE
$baseJob.completed_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding utf8
(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json).jobs | Where-Object id -eq 'base' | Select-Object id, status, source_path, completed_at
```

Expected: `base.status` is `complete`; `idle` and `running-right` are ready.

### Task 3: Generate and Incrementally Validate Standard Animation Rows

**Files:**
- Read: `%USERPROFILE%\.codex\pet-runs\qori-v2\prompts\rows\*.md`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\idle.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\running-right.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\running-left.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\waving.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\jumping.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\failed.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\waiting.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\running.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\review.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\rows\idle\review.json`, `running-right\review.json`, `running-left\review.json`, `waving\review.json`, `jumping\review.json`, `failed\review.json`, `waiting\review.json`, `running\review.json`, and `review\review.json`
- Modify: `%USERPROFILE%\.codex\pet-runs\qori-v2\imagegen-jobs.json`

**Interfaces:**
- Consumes: canonical base plus each row's listed layout guide and input images.
- Produces: nine identity-consistent, individually validated standard row strips.

- [ ] **Step 1: Generate the identity and gait probes**

Dispatch separate isolated workers for `idle` and `running-right`. Each worker reads its prompt and retry prompt, attaches every input listed in `imagegen-jobs.json`, and returns only a selected source plus one-sentence QA note.

Expected: idle shows visible micro-variation without busy motion; running-right has eight separated poses facing and traveling screen-right with alternating gait.

- [ ] **Step 2: Copy and inspect each probe row before completion**

For each row, copy the selected output to its manifest `output_path`, then run:

```powershell
foreach ($ROW in @('idle', 'running-right')) {
  $ROW_QA = Join-Path $RUN_DIR "qa\rows\$ROW"
  & $PYTHON (Join-Path $SKILL_DIR 'scripts\extract_strip_frames.py') --decoded-dir (Join-Path $RUN_DIR 'decoded') --output-dir (Join-Path $ROW_QA 'frames') --states $ROW --method auto
  if ($LASTEXITCODE -ne 0) { throw "Frame extraction failed for $ROW" }
  & $PYTHON (Join-Path $SKILL_DIR 'scripts\inspect_frames.py') --frames-root (Join-Path $ROW_QA 'frames') --json-out (Join-Path $ROW_QA 'review.json') --states $ROW --require-components
  if ($LASTEXITCODE -ne 0) { throw "Frame inspection failed for $ROW" }
}
```

Expected: inspection exits zero, expected frame count is present, and `review.json` has no errors.

- [ ] **Step 3: Decide the left-running strategy**

Mirror only if every plate, seam, facial cue, core detail, and lighting relationship remains valid when flipped. Otherwise generate `running-left` independently with `$imagegen`.

Safe mirror command when explicitly approved:

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\derive_running_left_from_running_right.py') --run-dir $RUN_DIR --confirm-appropriate-mirror --decision-note 'Qori is bilaterally consistent in the approved running-right row; mirroring preserves the core, five connected tail plates, materials, and identity.'
```

Expected: `running-left` faces and travels screen-left without reversing animation timing.

- [ ] **Step 4: Generate the remaining six distinct state rows**

Keep up to three isolated row workers active for `waving`, `jumping`, `failed`, `waiting`, `running`, and `review`. Each worker must use the canonical base and matching layout guide, generate its state independently, and return only the selected source and QA note.

Expected: exact frame counts, flat chroma background, separated poses, connected tail/core/ears, and state-specific motion with no detached effects.

- [ ] **Step 5: Run incremental row inspection and repair only genuine source failures**

Repeat the extraction and inspection command from Step 2 for every row before marking it complete. Use `stable-slots` only when source scale and placement are stable but automatic component extraction causes motion popping.

Expected: all nine jobs have `status: complete`; every row review has no errors; warnings have explicit visual disposition.

### Task 4: Assemble and Review the Standard 8 x 9 Atlas

**Files:**
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\frames\`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\final\spritesheet.webp`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\contact-sheet.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\previews\*.gif`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\review.json`

**Interfaces:**
- Consumes: nine completed standard row strips.
- Produces: approved intermediate atlas and motion evidence for the look-direction stage.

- [ ] **Step 1: Extract, inspect, compose, and preview**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\extract_strip_frames.py') --decoded-dir (Join-Path $RUN_DIR 'decoded') --output-dir (Join-Path $RUN_DIR 'frames') --states all --method auto
& $PYTHON (Join-Path $SKILL_DIR 'scripts\inspect_frames.py') --frames-root (Join-Path $RUN_DIR 'frames') --json-out (Join-Path $RUN_DIR 'qa\review.json') --require-components
& $PYTHON (Join-Path $SKILL_DIR 'scripts\compose_atlas.py') --frames-root (Join-Path $RUN_DIR 'frames') --output (Join-Path $RUN_DIR 'final\spritesheet.png') --webp-output (Join-Path $RUN_DIR 'final\spritesheet.webp')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\make_contact_sheet.py') (Join-Path $RUN_DIR 'final\spritesheet.webp') --output (Join-Path $RUN_DIR 'qa\contact-sheet.png')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\render_animation_previews.py') --frames-root (Join-Path $RUN_DIR 'frames') --output-dir (Join-Path $RUN_DIR 'qa\previews')
```

Expected: 1536 x 1872 intermediate atlas, nine readable row previews, and no review errors.

- [ ] **Step 2: Run independent standard-row visual QA**

Inspect the contact sheet and all preview GIFs for identity drift, tail-plate changes, reversed gait, wrong row semantics, inert idle motion, clipping, overlap, and extraction-induced popping.

Expected: all rows pass before any look-direction generation begins.

### Task 5: Define Look Mechanics and Approve Four Cardinals

**Files:**
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\look-mechanics.md`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-cardinals.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-anchors\000.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-anchors\090.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-anchors\180.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-anchors\270.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-anchors-approved.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\cardinal-anchors.json`

**Interfaces:**
- Consumes: approved standard atlas and canonical base.
- Produces: explicit Qori mechanics and four semantically approved cardinal pose families.

- [ ] **Step 1: Write Qori's mechanics decision**

Record that paws/lower torso remain anchored; physical eyes lead; eyelids, brows, muzzle, head, and ears follow; shoulders respond slightly at horizontal extremes; the connected five-plate tail follows with subtle delay; the whole sprite never rotates.

Expected: the file names the 000, 090, 180, and 270 pose families and the one-step continuity budget.

- [ ] **Step 2: Generate one coherent four-cardinal strip**

Dispatch one isolated cardinal worker with the canonical base, approved standard contact sheet, cardinal guide, and look-mechanics file.

Expected: four separated poses ordered 000 up, 090 screen-right, 180 down, 270 screen-left, with nose and eye landmark evidence in the worker note.

- [ ] **Step 3: Extract and compose approved anchors**

```powershell
$CHROMA_KEY = (Get-Content (Join-Path $RUN_DIR 'pet_request.json') -Raw | ConvertFrom-Json).chroma_key.hex
& $PYTHON (Join-Path $SKILL_DIR 'scripts\extract_cardinal_anchors.py') --strip (Join-Path $RUN_DIR 'decoded\look-cardinals.png') --output-dir (Join-Path $RUN_DIR 'decoded\look-anchors') --chroma-key $CHROMA_KEY --json-out (Join-Path $RUN_DIR 'qa\cardinal-anchors.json')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\compose_cardinal_anchor_strip.py') --anchors-dir (Join-Path $RUN_DIR 'decoded\look-anchors') --output (Join-Path $RUN_DIR 'decoded\look-anchors-approved.png')
```

Expected: deterministic clipping report passes and every cardinal is unmistakable at normal pet size.

### Task 6: Generate and Gate Look Row 9

**Files:**
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-row-9.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\look-row-9-registered.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\look-row-9-registration.json`

**Interfaces:**
- Consumes: canonical base, approved contact sheet, look mechanics, and cardinal anchors.
- Produces: registered coherent directions 000 through 157.5 with no hard edge, semantic, or continuity failure.

- [ ] **Step 1: Generate row 9 as one coherent family**

Dispatch one isolated row worker for 000, 022.5, 045, 067.5, 090, 112.5, 135, and 157.5 in that exact order.

Expected: eight separated pose groups with continuous gaze/body progression and stable connected tail anatomy.

- [ ] **Step 2: Register row 9 and inspect final cells**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\assemble_extended_atlas.py') --base-atlas (Join-Path $RUN_DIR 'final\spritesheet.webp') --look-row-9 (Join-Path $RUN_DIR 'decoded\look-row-9.png') --neutral-cell (Join-Path $RUN_DIR 'frames\idle\00.png') --chroma-key $CHROMA_KEY --chroma-threshold 96 --registered-row-output (Join-Path $RUN_DIR 'qa\look-row-9-registered.png') --registration-manifest-output (Join-Path $RUN_DIR 'qa\look-row-9-registration.json')
```

Expected: all eight normalized cells pass edge checks; scale and baseline match idle; no wrong quadrant, reversal, or identity drift.

### Task 7: Generate Look Row 10 and Assemble the V2 Atlas

**Files:**
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\decoded\look-row-10.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\final\spritesheet-extended.webp`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\final\validation-extended.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\chroma-despill-extended.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\contact-sheet-extended.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\look-directions.png`

**Interfaces:**
- Consumes: approved row 9 registration plus the cardinal strip and identity references.
- Produces: complete cleaned and structurally valid 8 x 11 v2 atlas.

- [ ] **Step 1: Generate row 10 as one coherent family**

Dispatch one isolated row worker for 180, 202.5, 225, 247.5, 270, 292.5, 315, and 337.5, attaching completed row 9 as continuity evidence.

Expected: 180 begins one step after 157.5 and 337.5 ends one step before 000.

- [ ] **Step 2: Assemble, despill once, and validate**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\assemble_extended_atlas.py') --base-atlas (Join-Path $RUN_DIR 'final\spritesheet.webp') --registered-row-9 (Join-Path $RUN_DIR 'qa\look-row-9-registered.png') --row-9-registration (Join-Path $RUN_DIR 'qa\look-row-9-registration.json') --look-row-10 (Join-Path $RUN_DIR 'decoded\look-row-10.png') --neutral-cell (Join-Path $RUN_DIR 'frames\idle\00.png') --chroma-key $CHROMA_KEY --chroma-threshold 96 --output (Join-Path $RUN_DIR 'final\spritesheet-extended.png') --webp-output (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --manifest-output (Join-Path $RUN_DIR 'final\spritesheet-extended.json')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\despill_chroma_edges.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.png') --output (Join-Path $RUN_DIR 'final\spritesheet-extended.png') --webp-output (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --chroma-key $CHROMA_KEY --json-out (Join-Path $RUN_DIR 'qa\chroma-despill-extended.json')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\validate_atlas.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --json-out (Join-Path $RUN_DIR 'final\validation-extended.json') --chroma-key $CHROMA_KEY --require-v2
& $PYTHON (Join-Path $SKILL_DIR 'scripts\make_contact_sheet.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --output (Join-Path $RUN_DIR 'qa\contact-sheet-extended.png')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\make_direction_qa_sheet.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --output (Join-Path $RUN_DIR 'qa\look-directions.png')
```

Expected: 1536 x 2288 atlas; despill report `ok: true`; v2 validation passes.

### Task 8: Run Independent Direction, Continuity, and Final Visual QA

**Files:**
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-blind-pairs.png`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-blind-verdicts-1.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-blind-verdicts-2.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-blind-verdicts-3.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-blind-validation.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\direction-semantics.json`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\look-continuity.json`

**Interfaces:**
- Consumes: final v2 atlas and QA sheets.
- Produces: independent evidence that direction meaning, continuity, identity, and all state loops pass.

- [ ] **Step 1: Create the blind challenge and continuity report**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\make_direction_blind_qa_sheet.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --output (Join-Path $RUN_DIR 'qa\direction-blind-pairs.png') --answer-key (Join-Path $RUN_DIR 'qa\direction-blind-answer-key.json')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\measure_direction_continuity.py') (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') --json-out (Join-Path $RUN_DIR 'qa\look-continuity.json')
```

Expected: blind sheet contains seven horizontal and seven vertical pairs; continuity JSON covers every adjacent pair including row boundaries.

- [ ] **Step 2: Dispatch three isolated blind reviewers**

Each reviewer receives only `direction-blind-pairs.png`, never the atlas, labeled sheet, prompts, answer key, or another verdict.

Expected: three complete JSON verdict files using only `screen-left`, `screen-right`, `up`, `down`, or `ambiguous` on the requested axis.

- [ ] **Step 3: Combine and validate blind verdicts**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\combine_direction_blind_verdicts.py') --verdicts (Join-Path $RUN_DIR 'qa\direction-blind-verdicts-1.json') --verdicts (Join-Path $RUN_DIR 'qa\direction-blind-verdicts-2.json') --verdicts (Join-Path $RUN_DIR 'qa\direction-blind-verdicts-3.json') --json-out (Join-Path $RUN_DIR 'qa\direction-blind-verdicts.json')
& $PYTHON (Join-Path $SKILL_DIR 'scripts\validate_direction_blind_verdicts.py') --answer-key (Join-Path $RUN_DIR 'qa\direction-blind-answer-key.json') --verdicts (Join-Path $RUN_DIR 'qa\direction-blind-verdicts.json') --json-out (Join-Path $RUN_DIR 'qa\direction-blind-validation.json')
```

Expected: `ok: true`; no cardinal mismatch or ambiguity.

- [ ] **Step 4: Run one independent final visual QA worker**

Provide the standard and extended contact sheets, direction sheet, preview GIFs, semantics, blind validation, continuity, standard review, and v2 validation.

Expected: `visual_qa=pass`, all 16 directions receive explicit pass/warning/fail semantics, no hard failure remains, and any accepted minor warning is documented.

### Task 9: Package Qori and Retain the Audit Trail

**Files:**
- Create: `%USERPROFILE%\.codex\pets\qori\pet.json`
- Create: `%USERPROFILE%\.codex\pets\qori\spritesheet.webp`
- Create: `%USERPROFILE%\.codex\pet-runs\qori-v2\qa\run-summary.json`

**Interfaces:**
- Consumes: fully passing final atlas and complete QA evidence.
- Produces: installed Codex v2 pet plus compact retained audit trail.

- [ ] **Step 1: Install the validated package**

```powershell
$PET_DIR = Join-Path $env:USERPROFILE '.codex\pets\qori'
New-Item -ItemType Directory -Path $PET_DIR -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $RUN_DIR 'final\spritesheet-extended.webp') -Destination (Join-Path $PET_DIR 'spritesheet.webp') -Force
@{
  id = 'qori'
  displayName = 'Qori'
  description = 'Qori is a local-first archive lynx who watches every scene, protects persistent memory, and brings calm, auditable focus to the work.'
  spriteVersionNumber = 2
  spritesheetPath = 'spritesheet.webp'
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PET_DIR 'pet.json') -Encoding utf8
```

Expected: `pet.json` and `spritesheet.webp` exist together; manifest parses; sprite version is integer `2`.

- [ ] **Step 2: Revalidate the installed atlas**

```powershell
& $PYTHON (Join-Path $SKILL_DIR 'scripts\validate_atlas.py') (Join-Path $PET_DIR 'spritesheet.webp') --json-out (Join-Path $RUN_DIR 'final\validation-installed.json') --chroma-key $CHROMA_KEY --require-v2
```

Expected: installed copy independently passes v2 validation.

- [ ] **Step 3: Write the run summary and clean intermediates**

Retain the request, final WebP, validation, despill report, extended contact sheet, look-direction sheet, direction semantics, blind evidence, continuity report, preview GIFs, standard review, and run summary. Remove prompts, layout guides, generated row strips, extracted frames, PNG intermediates, standard atlas, and job manifest after successful installation unless debugging evidence is still needed.

Expected: compact retained QA set remains; installed package is untouched; no generated source is deleted before its decoded copy and final package are proven.
