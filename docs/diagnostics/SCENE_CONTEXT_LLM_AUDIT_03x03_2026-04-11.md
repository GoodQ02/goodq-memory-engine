<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: OPERATOR_NOTE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

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

## Final Verification Rerun (`20260411_103108`)

After the narrower transcript-fragment cleanup and the final post-normalization guardrails, the rerun passed the treatment gate cleanly.

### Final run result

- `scene_count = 39`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm = 38`
- `generic_context_detected = false`
- local endpoint probe:
  - `http://localhost:38005/v1/models -> 200`
  - model id: `Qwen/Qwen2.5-0.5B-Instruct`

### Final top tags

- `pen` `13`
- `living room` `7`
- `kitchen` `7`
- `rental car` `6`
- `condo` `4`
- `air conditioning` `3`
- `president` `3`
- `scuba diving` `3`
- `group conversation` `3`
- `florida` `2`

### Final consistency read

The final rerun shows a materially better semantic engine:

- transcript-salient episode themes now dominate retrieval tags instead of generic social framing
- the worst social hallucinations (`social gathering`, `outdoor activity`, `outdoor setting`) are gone
- generic human filler tags (`man`, `woman`, `conversation`, `room`, `waiting`) are fully suppressed at the tag layer
- the output remains short and operator-like rather than cinematic

### Representative final samples

#### Scene 1 - stand-up no longer literalized into physical action

- transcript: stand-up material about bathing suits and Florida
- final summary: `Conversation about florida.`
- final tags: `bathing suit`, `Florida`
- assessment: still terse, but no longer invents water, boats, or waiting

#### Scene 3 - rental-car arrival scene stays grounded

- caption: two women in a room with a blue backpack
- transcript: welcome to Florida, delayed at rental-car counter, discussion about using the car
- final summary: `Room conversation about rental car.`
- final tags: `blue backpack`, `room with a blue backpack`, `rental car`, `florida`
- assessment: grounded topic anchoring is good; the remaining weakness is a little too much caption phrasing in the tag set

#### Scene 22 - black-screen / weak-visual scene now stays topic-centered

- caption: person against black background
- transcript: air conditioner, pen, muscle relaxers
- final summary: `Conversation about air conditioning.`
- final tags: `air conditioning`, `background`, `muscle relaxers`, `pen`
- assessment: acceptable; no narrative invention, though `background` is low-value and could be pruned later

#### Scene 26 - conflict scene is correctly anchored to kitchen / pen argument

- caption: two men in a kitchen
- transcript: sponge cake, scotch tape, pen conflict, angry exchange
- final summary: `Two men in a kitchen scream at each other while holding a tie.`
- final tags: `kitchen`, `tied tie`, `men screaming`, `pen`
- assessment: conflict is correctly captured; the tie-focused phrasing is still too literal relative to transcript importance

#### Scene 34 - late episode topic weighting is better but still imperfect

- caption: man in suit at a table
- transcript: peanuts, scotch, pen, doctor warning about travel
- final summary: `Table conversation about pen.`
- final tags: `people sitting at a table`, `conversation about peanuts and scotch`, `pen`
- assessment: much better than prior broad social-event drift, but still underweights the medical/travel consequence in favor of table-level framing

#### Scene 35 - lawyer topic is now surfaced

- caption: man and woman sitting on a couch
- transcript: staying longer, lawyer, case
- final summary: `Couch conversation about lawyer.`
- final tags: `couch`, `microwave`, `lawyer`, `case`
- assessment: core topic is right; `microwave` remains a weak vision-led tag that may be worth suppressing if it stays low-value across episodes

### Remaining watch-list residue

The feature now passes, but a few narrow seams remain:

- residual unsupported social wording in a small subset of scenes:
  - `friends`
  - `family`
  - `couple`
- occasional low-value vision tags that are technically visible but semantically weak:
  - `background`
  - `microwave`
  - `blue backpack`
- a few scene summaries still favor room-level staging over stronger transcript consequence

These are polish issues, not feature blockers. The run is now consistent enough to treat `scene_context_llm` as a validated additive layer in the Season 3 treatment ladder.

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

## Final Authoritative Pass (`20260411_171418`)

The final verification run closed the last remaining seam and is the authoritative `03x03` result for this treatment ladder step.

### Authoritative result

- run root: `reports/fresh_ingest_runs/20260411_171418_season3_feature_ladder/`
- model endpoint: `http://localhost:38005/v1/models`
- model id used: `Qwen/Qwen2.5-0.5B-Instruct`
- `scene_count = 39`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm = 36`
- `generic_context_detected = false`

### Final top tags

- `pen` `10`
- `living room` `7`
- `rental car` `6`
- `kitchen` `6`
- `condo` `4`
- `group conversation` `4`
- `couch` `4`
- `florida` `3`
- `air conditioning` `3`
- `scuba diving` `3`

### Final residue sweep

A direct sweep of the persisted `scene_manifest.json` for the final authoritative pass found no remaining matches for the previously pinned residue terms:

- `friends`
- `family`
- `couple`
- `background`
- `microwave`
- `blue backpack`
- `room with a blue backpack`

That confirms the last cleanup pass removed the unsupported social-role wording and the low-value visible-tag residue instead of merely relaxing the gate.

### Closeout read

This is now strong enough to lock in as the validated `scene_context_llm` treatment behavior:

- the layer stays additive and non-authoritative
- transcript-backed episode topics are retrieval-visible
- generic social-event storytelling is gone
- role-like claims now require transcript support
- the gate and the analyzer are aligned with the system's evidence-first contract
