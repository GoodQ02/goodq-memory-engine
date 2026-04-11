# Scene Context LLM Audit - 03x03 "The Pen" - 2026-04-11

## Scope

- Epoch: `epoch_2025_12_23`
- Episode: `03x03 - The Pen`
- Feature under audit: `scene_context_llm`
- Run under review: `20260411_040152_season3_feature_ladder`

This audit compares generated `scene_context_llm` output against:

1. local transcript evidence
2. local caption/object evidence
3. episode-level public plot summaries for "The Pen"

## Canonical Artifacts Reviewed

- treatment epoch `03x03 - The Pen` `scene_manifest.json`
- treatment epoch `03x03 - The Pen` `temporal_index.json`
- treatment run `20260411_040152_season3_feature_ladder` `experiment_log.json`
- prior comparison run `20260410_223654_season3_feature_ladder` `experiment_log.json`

## Public Episode Truth Reference

Public summaries agree on the main episode shape:

- Jerry and Elaine visit Jerry's parents in Florida.
- Morty is being honored by the condo association.
- Jack Klompus pressures Jerry to take the astronaut pen, then wants it back.
- Elaine suffers from the sofa bed and heat.
- Jerry goes scuba diving and injures his eyes.
- The episode ends with fallout involving the ceremony, the chiropractor, and condo politics.

Reference links:

- IMDb: https://www.imdb.com/title/tt0697749/
- Apple TV synopsis: https://tv.apple.com/us/episode/the-pen/umc.cmc.593qq24zxezfrj486dzhvbm31
- Wikipedia plot: https://en.wikipedia.org/wiki/The_Pen

## Runtime Result

The run itself passed the platform and ingestion checks:

- `scene_count = 39`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm = 38`
- local `vLLM` endpoint was healthy

So the current failure is quality-only, not runtime.

## Quantitative Findings

### Current run (`20260411_040152`)

- `segments_with_scene_context_llm = 38`
- `unique_tag_count = 20`
- top tags:
  - `indoor conversation` `10`
  - `living room` `8`
  - `kitchen` `8`
  - `woman` `8`
  - `man` `7`
  - `rental car` `6`
  - `room` `3`
  - `conversation` `3`
  - `bed` `3`
  - `waiting` `2`

### Improvement vs prior failed run (`20260410_223654`)

The earlier run overfit to invented social and location framing:

- `social gathering` `14`
- `outdoor activity` `8`
- `alone` `4`
- `outdoor setting` `2`
- `old person` `1`

The current prompt patch materially improved grounding by removing most of that drift.

### Residual quality issues in current run

- scenes with generic tags: `24 / 38`
- scenes with role-like tags: `3 / 38`
- scenes with location/topic overreach tags: `2 / 38`

Observed generic/problematic tag counts:

- `indoor conversation` `10`
- `woman` `8`
- `man` `7`
- `room` `3`
- `conversation` `3`
- `waiting` `2`
- `family` `1`
- `friend` / `friends` `2` total
- `constitutional topics` `1`
- `hospital` `1`

## Episode-Theme Coverage Check

The model is still underweighting several core episode themes from transcript evidence.

### Terms found in transcript but weakly represented in output

- `florida`: transcript `3`, summaries `0`, tags `0`
- `condo`: transcript `4`, summaries `0`, tags `0`
- `president`: transcript `3`, summaries `0`, tags `0`
- `bylaws`: transcript `1`, summaries `0`, tags `0`
- `chiropractor`: transcript `1`, summaries `0`, tags `0`

### Terms with partial capture

- `pen`: transcript `21`, summaries `4`, tags `3`
- `back`: transcript `12`, summaries `2`, tags `1`
- `scuba`: transcript `3`, summaries `2`, tags `2`
- `astronaut`: transcript `4`, summaries `1`, tags `1`
- `biscayne`: transcript `2`, summaries `1`, tags `1`

### Terms over-amplified relative to transcript support

- `rental car`: transcript `2`, summaries `5`, tags `6`

This suggests the current prompt is better grounded than before, but still not weighting transcript salience correctly.

## Representative Good Outputs

### Scene 3

- transcript contains direct rental-car discussion and air-conditioning complaints
- output summary: `A group of people are talking in a living room about renting a car.`
- assessment: grounded, concise, acceptable

### Scene 10

- transcript centers on Jack pushing the pen as a gift
- output summary: `Three men are having a conversation in a kitchen about a gift they received.`
- assessment: still generic, but correctly anchored to the gift/pen exchange

### Scene 16

- transcript clearly supports scuba-diving and Biscayne discussion
- output summary: `A group of friends discuss their plans for a scuba diving trip to Biscayne Bay.`
- assessment: topic anchoring is strong, though `friends` is not explicitly supported

### Scene 32

- transcript strongly centers on taking back the pen
- output summary: `A group of people sit around a table, giving and taking pens, and arguing about a broken dental pen.`
- assessment: mostly grounded; pen conflict is correctly surfaced

## Representative Failures

### Scene 1 - stand-up literalized into event

- caption: black background with lights
- transcript: stand-up monologue with water/bathing-suit bits and fragmented airline/tape jokes
- output: `A man floats in water while others wait for a boat to arrive.`
- issue: the model turned comic material into literal scene action

### Scene 22 - unsupported family-role invention

- caption: woman lying on the floor in a room
- transcript: concern about burst capillaries, cold room, scuba aftermath
- output tags: `woman`, `family`, `room`
- output summary: `surrounded by her family`
- issue: role invention not supported by transcript or visible text

### Scene 26 - microphone/social framing drift

- transcript: complaint about the condo community, humidity, white shoes, emcee role, muscle relaxers
- output: `A woman sits alone on a couch, surrounded by men, while a man speaks to her through a microphone.`
- issue: invented scene geometry and social staging not grounded in evidence

### Scene 34 - unsupported object fixation

- caption: man and woman sitting on a couch
- transcript: lawyer, five more days, Jack has no case
- output: `looking at a microwave`
- issue: object/action inference unsupported by transcript and not salient to the scene

### Scene 35 / 36 - transcript topic underuse

- transcript includes condo constitution/bylaws/chiropractor material
- outputs reduce this to `two women converse in a room` and `constitutional issues`
- issue: episode-specific topics are washed out into vague abstractions

## Root Diagnosis

The current analyzer is no longer a storyteller, but it is still doing three things that lower quality:

1. It allows generic human tags to survive.
   - `man`, `woman`, `people`, `conversation`, `room`, `waiting`
   - these increase coverage without increasing retrieval value

2. It underweights transcript-salient episode topics.
   - `Florida`, `condo`, `president`, `bylaws`, `chiropractor` should be more visible
   - `rental car` is being over-amplified relative to actual episode importance

3. It still literalizes comedic monologue and fragments.
   - stand-up material gets treated as literal action instead of performance about a topic

## Recommended Next Surgical Fixes

### 1. Add a generic-tag post-filter

Drop or suppress these unless they are the only remaining usable tags:

- `man`
- `woman`
- `people`
- `conversation`
- `room`
- `waiting`
- `friend` / `friends`
- `family`

This should happen after generation, not by loosening the quality gate.

### 2. Add transcript-topic salience promotion

If a topic appears clearly in transcript and is episode-salient, prefer it over generic tags.

Likely candidates for this episode:

- `Florida`
- `condo`
- `president`
- `pen`
- `scuba`
- `back`
- `air conditioning`
- `bylaws`
- `chiropractor`

### 3. Add stand-up / monologue detection

If the scene looks like stage/curtain/microphone or a black-background stand-up segment:

- summarize it as a monologue/performance about a topic
- do not convert jokes into literal events

Example desired output:

- `Stand-up monologue about bathing suits and travel frustration.`

### 4. Tighten unsupported action filtering

Suppress activity-description patterns like:

- `looking at a microwave`
- `surrounded by men`
- `family watches`
- `waiting for someone`

unless directly supported by transcript or visible text.

## Follow-Up Result - First Passing Treatment Run

After the initial audit and corrective passes, `03x03` was rerun successfully under:

- `20260411_061212_season3_feature_ladder`

Confirmed outcome from the passing run:

- `scene_count = 39`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm = 38`
- `generic_context_detected = false`
- local model used: `Qwen/Qwen2.5-0.5B-Instruct`

Top tags in the passing run were materially more grounded:

- `pen` `12`
- `living room` `8`
- `rental car` `6`
- `kitchen` `6`
- `group conversation` `5`
- `condo` `4`
- `florida` `3`
- `air conditioning` `3`

This confirmed the structural problem was solved:

- broad social-event hallucinations were removed
- unsupported kinship and role invention was suppressed
- transcript-salient episode topics started surfacing in both tags and summaries

The remaining seam after the passing run was narrower and lexical rather than architectural:

- isolated transcript-fragment residue such as `alarmed god`, `people aware`, and `must some`
- occasional setting overreach like `bedroom` when only dialogue implied it

Those residual issues are appropriate for a narrower transcript-fragment cleanup pass rather than another broad prompt rewrite.

## Overall Verdict

`scene_context_llm` is now operationally viable on the local treatment path.

- runtime and local `vLLM` wiring are validated
- Phase 6 persists the additive scene context cleanly
- the major semantic drift problem is resolved
- remaining cleanup is lexical hardening, not architecture repair
