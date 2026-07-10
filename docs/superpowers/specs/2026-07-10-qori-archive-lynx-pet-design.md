# Qori Archive Lynx Pet Design

## Purpose

Create a Codex-compatible animated pet that personifies GoodQ4All and complements an audit-first, stability-minded working style. Qori should make system state emotionally legible without adding visual noise.

## Character Summary

**Name:** Qori

**Archetype:** Archive lynx; organic guardian with cultivated machine anatomy

**Production style:** Tactile plush-bioceramic 3D mascot

**Description:** Qori is a local-first archive lynx who watches every scene, protects persistent memory, and brings calm, auditable focus to the work.

Qori is observant, patient, quietly amused, and resilient. The character should feel warm enough to be a familiar and engineered enough to embody a production-grade memory system. The technology appears grown into Qori's body, never bolted onto an ordinary animal.

## GoodQ4All Translation

| GoodQ4All quality | Qori expression |
| --- | --- |
| Local-first persistence | Protected amber scene-core held inside the body; no cloud imagery |
| Scene-centric memory | Broad tail formed from five overlapping scene-like segments |
| Multimodal perception | Cyan eye rings and alert lynx ears coordinate vision and audio attention |
| Knowledge graph | Cyan connective seams link the tail segments into one continuous structure |
| Auditability | Focused, readable gaze and deliberate review posture |
| Resilience | Grounded paws, protective tail behavior, and recovery-oriented failure animation |
| Surgical operation | Economical motion with one dominant cue per application state |

## Visual Identity

Qori has a compact whole-body lynx silhouette with a large readable head, alert tufted ears, sturdy paws, and a broad segmented tail. The silhouette must remain recognizable inside a 192 x 208 sprite cell.

### Materials and Palette

- Soft charcoal-indigo fur forms the living base.
- Smooth graphite bioceramic plates protect the brow, shoulders, chest, and tail.
- Bright cyan sensory rings and narrow connective seams indicate active perception.
- A protected amber core in the chest represents persistent scene memory, focus, and recovery.
- Restrained moss-green accents keep the engineered anatomy organic.
- Highlights are soft and tactile; surfaces must not read as chrome, hard military armor, or consumer electronics.

The selected chroma background must stay clearly separated from every character color. The final sprite contains no floor, shadow, glow, scenery, or detached visual effect.

### Face and Expression

Qori's face is intelligent, calm, and approachable rather than hyper-cute. Cyan irises sit within coherent physical eyes so look-direction animation can use the eyes, eyelids, brows, head, and ears together. A small knowing half-smile may appear in neutral poses, but the resting expression remains attentive.

### Signature Anatomy

- The amber scene-core is embedded and protected, never floating.
- Five broad tail plates overlap like durable scene records and remain physically connected.
- Cyan seams travel only across existing anatomy and never become loose circuitry or effects.
- Ear tufts are large enough to carry readable attention changes.
- Paws are broad and grounded to create a stable animation anchor.

## Attention-Friendly Motion Language

Qori uses a calm baseline and one dominant motion cue per state. Motion is purposeful and low-noise: no constant twitching, decorative particles, notification-like pulses, or competing secondary gestures.

| Application state | Animation intent |
| --- | --- |
| Idle | Slow breath, tiny ear swivel, and a restrained amber core pulse |
| Running right | Low agile lynx gait facing screen-right; alternating paws and controlled tail follow-through |
| Running left | Equivalent left-facing gait generated independently if mirroring would change anatomy or markings |
| Waving | One forepaw gives a restrained friendly greeting with no wave marks |
| Jumping | Compact spring and landing expressed only through body position |
| Failed | Ears lower, core dims slightly, and tail curls protectively; disappointed but not defeated |
| Waiting | Attentive head tilt and one open paw clearly request user input |
| Running / task work | Eyes scan, ears triangulate, tail segments subtly align, and the core becomes steady and focused; no literal foot-running |
| Review | Body settles, gaze narrows, one ear angles forward, and the tail becomes still |

Each loop must show real variation while preserving Qori's scale, baseline, identity, materials, and connected anatomy.

## Look-Direction Mechanics

Qori's paws and lower torso remain anchored. The eyes lead attention, followed by a restrained head turn, coordinated eyelid and brow change, and ear alignment. The shoulders may follow slightly at the strongest horizontal directions. Tail plates respond with a small delayed progression while remaining attached and stable.

Cardinal pose families:

- **000 up:** pupils, eyelids, muzzle angle, and both ears clearly lift toward 12 o'clock.
- **090 screen-right:** eyes and nose cross screen-right of the head center; the screen-right side of the face leads.
- **180 down:** gaze, eyelids, muzzle, and ear posture clearly settle downward.
- **270 screen-left:** eyes and nose cross screen-left of the head center; the screen-left side of the face leads.

The 16 directions form one continuous clockwise awareness sweep. Intermediate directions advance evenly in 22.5-degree steps. Whole-sprite rotation, broad raster warping, pupil-only direction changes, and independently restyled cells are prohibited.

## Production Contract

- Build a v2 pet with an 8 x 11 atlas using 192 x 208 cells.
- Final atlas size is 1536 x 2288 in PNG or WebP form.
- Package with `spriteVersionNumber: 2`.
- Generate one canonical base image before any row strip.
- Generate all distinct state rows from the canonical identity reference.
- Generate and approve four cardinal look anchors before the two coherent eight-pose look rows.
- Use deterministic scripts only for layout, extraction, registration, mirroring when explicitly safe, atlas composition, transparency cleanup, previews, and validation.
- Preserve connected components and avoid thin or detached tail, ear, core, or armor elements.

## Visual Avoidances

- No text, logos, code, screens, labels, interface panels, or readable symbols.
- No cloud motifs, wireless icons, or external storage metaphors.
- No weapons, tactical styling, aggressive posture, or militarized armor.
- No detached sparkles, tears, smoke, punctuation, motion lines, dust, shadows, glows, or floor marks.
- No generic robot joints, exposed cables, chrome plating, or bolted-on gadgets.
- No hyperactive idle loop, exaggerated cartoon panic, or attention-competing ornament.
- No identity drift, replacement eyes, changing tail segment count, or inconsistent core placement.

## Acceptance Criteria

Qori is complete only when:

- all nine standard animation rows are visually distinct and semantically correct;
- all 16 look directions form a coherent clockwise family with unmistakable cardinals;
- identity, materials, palette, proportions, core, and five-segment tail remain consistent;
- the idle loop is calm but visibly animated;
- waiting, task work, review, and failure read clearly at normal pet size;
- standard and extended contact sheets plus motion previews pass visual review;
- three isolated blind direction reviews pass the cardinal gates;
- direction semantics and continuity artifacts contain no unresolved hard failure;
- deterministic chroma cleanup reports success;
- the v2 atlas validator passes; and
- `pet.json` and `spritesheet.webp` are installed together in Qori's custom-pet directory.

## Deliverables

- Installed Qori v2 pet package.
- Final extended WebP spritesheet.
- Deterministic atlas validation report.
- Chroma cleanup report.
- Standard and extended contact sheets.
- Motion preview GIFs for all standard rows.
- Focused look-direction sheet, blind-review artifacts, direction semantics, and continuity report.
- Compact run summary with the final artifact paths.

## Non-Goals

- No GoodQ4All product logo or branded UI recreation.
- No repository runtime, pipeline, API, persistence, or interface changes.
- No alternate Qori variants in the first production run.
- No relaxation of v2 packaging or visual QA gates for schedule reasons.
