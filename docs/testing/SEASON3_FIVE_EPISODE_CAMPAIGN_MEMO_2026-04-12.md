<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-12 -->

# Season 3 Five-Episode Campaign Memo

## Scope

- Treatment epoch: `epoch_2025_12_23`
- Campaign run root: `reports/fresh_ingest_runs/20260411_194713_season3_feature_ladder/`
- Feature under test: `scene_context_llm`
- Model endpoint:
  - `http://localhost:38005/v1/models`
  - `Qwen/Qwen2.5-0.5B-Instruct`
- Episode batch:
  - `03x04 - The Dog`
  - `03x05 - The Library`
  - `03x06 - The Parking Garage`
  - `03x07 - The Cafe`
  - `03x08 - The Tape`

This campaign reuses the validated `scene_context_llm` treatment logic from the
authoritative `03x03` pass and checks whether it remains grounded across five
additional Season 3 episodes without reopening the old generic-context failure.

## Campaign Result

The full five-episode campaign passed.

- Episodes passed: `5 / 5`
- Total scenes processed: `193`
- Scenes with `scene_context_llm`: `189`
- Scene-context coverage: `97.9%`
- Runs with `phase6_complete = true`: `5 / 5`
- Runs with `qdrant_ok = true`: `5 / 5`
- Runs with `generic_context_detected = false`: `5 / 5`

## Per-Episode Results

### `03x04 - The Dog`

- `scene_count = 38`
- `segments_with_scene_context_llm = 37`
- top tags:
  - `kitchen`
  - `dog`
  - `movie theater`
  - `airplane`

Representative sample:
- scene `20`
- summary: `Living room conversation about dog pound.`
- tags:
  - `group conversation`
  - `movie theater`
  - `dog pound`
- transcript anchor:
  - `we go right to the movies ... Going to the dog pound, everybody.`

Read:
- The layer stayed topic-grounded to the dog-pound / movie plan thread instead
  of falling back to vague social narration.

### `03x05 - The Library`

- `scene_count = 39`
- `segments_with_scene_context_llm = 39`
- top tags:
  - `book`
  - `table`
  - `library`
  - `case`

Representative sample:
- scene `2`
- summary:
  - `A group of coworkers discuss their recent work-related issues at the New York Public Library.`
- tags:
  - `new york public library`
  - `work-related issues`
  - `library staff`
  - `book return policy`
- transcript anchor:
  - `The New York Public Library says that I took out Tropic of Cancer...`

Read:
- The semantic layer correctly surfaced the actual library dispute rather than
  collapsing into room-level filler.

### `03x06 - The Parking Garage`

- `scene_count = 37`
- `segments_with_scene_context_llm = 35`
- top tags:
  - `car`
  - `parking garage`
  - `parking lot`
  - `rental car`

Representative sample:
- scene `6`
- summary:
  - `Two men carrying boxes in a parking garage discuss their plans.`
- tags:
  - `parking garage`
  - `car`
  - `boxes`
- transcript anchor:
  - `you better find this car ... really have to go to the bathroom`

Read:
- The system held the core episode setting and search-for-the-car logic without
  drifting into invented interpersonal stories.

### `03x07 - The Cafe`

- `scene_count = 39`
- `segments_with_scene_context_llm = 39`
- top tags:
  - `table`
  - `restaurant`
  - `iq test`
  - `kitchen`

Representative sample:
- scene `21`
- summary: `Table conversation about pakistani restaurant.`
- tags:
  - `restaurant environment`
  - `table seating`
  - `pakistani restaurant`
- transcript anchor:
  - `you would have the only authentic Pakistani restaurant in the whole neighborhood`

Read:
- The layer preserved the real restaurant/business topic and did not flatten it
  into generic dining-room chatter.

### `03x08 - The Tape`

- `scene_count = 40`
- `segments_with_scene_context_llm = 39`
- top tags:
  - `kitchen`
  - `cell phone`
  - `couch`
  - `living room`
  - `rental car`

Representative sample:
- scene `3`
- summary: `Couch conversation about phone who.`
- tags:
  - `cell phone`
  - `phone`
  - `calling china`
- transcript anchor:
  - `Need to use the phone. Who you calling? China.`

Read:
- The semantic layer stayed anchored to the phone / China / hair thread instead
  of inventing cinematic action.

## What This Proves

The `scene_context_llm` layer is now strong enough to treat as a validated
additive cognition surface.

What held across five episodes:

- Phase 6 stability
- vector persistence stability
- high `scene_context_llm` coverage
- no recurrence of the old generic-context failure
- continued transcript-led topic retrieval

This campaign moves the system from:

- single-episode success

to:

- multi-episode validated treatment behavior

## Remaining Watch-List (Minor, Not Blocking)

These are worth watching but did not justify reopening the runtime logic during
this campaign:

- occasional low-value visual tags such as `person`, `men`, or `group members`
- some scene summaries still prefer terse operator-note phrasing over richer but
  still-grounded phrasing
- a few episodes surface strongly visual tags (`table`, `couch`) alongside the
  more useful transcript-backed topic tags

These are polish opportunities, not campaign blockers.

## Operational Conclusion

The Season 3 treatment batch is successful.

Safe next moves:

1. Reuse the validated `scene_context_llm` logic on the remaining Season 3
   episodes.
2. Keep the control epoch (`epoch_2025_12_22`) locked.
3. Preserve the additive-only contract:
   - non-authoritative
   - auditable
   - no direct mutation of canonical truth outside explicit promotion
