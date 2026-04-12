# Scene Context LLM Audit - `03x09 The Nose Job`

## Scope

This memo audits the untouched-episode witness for `03x09 - The Nose Job` in the Season 3 treatment epoch.

Authority surfaces used:

- `reports/fresh_ingest_runs/20260412_115300_season3_feature_ladder/experiment_log.json`
- `%GOODQ_DATA%/epochs/epoch_2025_12_23/processing/03x09 - The Nose Job/temporal_index.json`
- `%GOODQ_DATA%/epochs/epoch_2025_12_23/processing/03x09 - The Nose Job/video/scene_manifest.json`

Public episode reference used for plot-shape comparison:

- Wikipedia synopsis for `The Nose Job`: <https://en.wikipedia.org/wiki/The_Nose_Job>

## Executive Read

`03x09` did not fail for the old reason.

The prior failure mode for `scene_context_llm` was broad hallucination:

- invented relationships
- invented outdoor/social-event settings
- cinematic prose detached from evidence

That failure mode does **not** reappear here.

`03x09` fails for a narrower and more structural reason:

- transcript-topic extraction degrades into weak fragments
- those weak fragments are promoted into `scene_context_llm`
- the new `scene_context_epistemic` payload then records those fragments as supported transcript evidence

So the runtime is healthy, the additive interpretation path is working, and the epistemic payload is persisting correctly. The seam is now topic extraction quality, especially in stand-up scenes, low-signal scenes, and open-ended dialogue scenes where naive bigram fallback produces junk.

## Witness Result

From the treatment ladder witness:

- feature: `scene_context_llm`
- status: `failed`
- `scene_count = 39`
- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_scene_context_llm = 38`
- `segments_with_scene_context_epistemic = 38`
- `generic_context_detected = true`

Interpretation:

- ingestion and persistence are healthy
- failure is quality-gate only

## Ground Truth Check

The episode's real plot shape is stable and easy to identify:

- George cannot get past Audrey's nose and indirectly encourages the surgery
- Jerry is torn between physical attraction to Isabel and intellectual disgust
- Kramer and Elaine retrieve Albert's jacket by posing as relatives
- Jerry's internal `brain vs penis` conflict becomes a chess metaphor

`03x09` output surfaces parts of that truth, but unevenly.

What works:

- `nose job`, `crop circles`, `Kramer`, `Audrey`, `Isabel`, `Miss Pepper`, `Professor von Nostrand`, `Hawaii`
- scene-level mention extraction still catches many episode entities and topics

What does not work well:

- stand-up opener becomes fragment-driven topic mush
- several scenes flatten into `Conversation about X` with low-value transcript shards
- some late scenes still center staging or visual props instead of the strongest spoken idea

## What Stayed Healthy

The stable rails remain intact:

- `phase6_complete = true`
- `qdrant_ok = true`
- `segments_with_candidate_visible_people = 8`
- `segments_with_interaction_dominance = 5`
- `segments_with_conversation_owner = 0`
- `segments_with_audio_emotion = 39`
- `segments_with_speaker_voice_signatures = 34`

Important: this is not an identity or dominance regression.

It is also not a persistence regression. `scene_context_llm` and `scene_context_epistemic` are both written and rolled up correctly.

## Pattern Audit

### 1. Stand-up / monologue handling is still under-clamped

Representative scenes:

- Scene `0`
- Scene `1`
- Scene `37`

Examples:

- Scene `0`
  - transcript is about pharmacists being elevated above everyone else and tiny prescription labels
  - output: `Conversation about half feet.`
  - tags include `half feet`, `give explanation`, and even `microwave oven`

- Scene `1`
  - transcript includes typing the tiny label, elevator small talk, and meeting a woman
  - output: `Conversation about little piece.`

- Scene `37`
  - transcript is just `Oh`
  - visual is a stage-style frame
  - output: `Conversation about stage.`
  - epistemic state is correctly only `partially_supported`

Interpretation:

- the current stand-up / monologue fallback does not engage aggressively enough
- weak transcript fragments are being treated as acceptable topic hints

### 2. Transcript fallback topic extraction is too naive

This is the dominant new failure mode.

Representative bad topic fragments:

- `half feet`
- `give explanation`
- `little piece`
- `matter nothing`
- `little who`
- `years later`
- `thinking nothing`
- `unfortunately live`
- `unless youd`
- `please isabel`
- `gonna see`
- `guessing okay`
- `kramer seriously`
- `cant stand`
- `right now`
- `swear nelson`
- `relax maybe`
- `were engaged`
- `miss pepper`
- `was name`
- `collar yeah`
- `shes like`
- `rhino okay`

These are not classic hallucinations. They are low-quality transcript shards surviving the extraction and normalization stack.

### 3. The epistemic layer is structurally correct but semantically downstream of bad topics

Representative evidence payloads:

- Scene `0`
  - transcript support recorded as `half feet`, `give explanation`
- Scene `1`
  - transcript support recorded as `little piece`, `piece paper`
- Scene `4`
  - transcript support recorded as `matter nothing`, `just believe`
- Scene `23`
  - transcript support recorded as `kramer seriously`, `seriously give`
- Scene `29`
  - transcript support recorded as `miss pepper`, `must professor`, `professor von`

Interpretation:

- `scene_context_epistemic` is not broken
- it is faithfully exposing what the analyzer believed
- because topic extraction is weak, the epistemic payload ends up explaining the wrong thing cleanly

That is useful. It means the new self-auditing layer is already doing its job: it makes the weakness observable instead of hiding it.

### 4. Strong scenes still exist and prove the lane is salvageable

Representative stronger scenes:

- Scene `9`
  - `Kitchen conversation about nose job.`
  - core topic is correct

- Scene `12`
  - `Couch conversation about nose job.`
  - topic is still correct and retrieval-usable

- Scene `25`
  - `Hawaii` is surfaced correctly

- Scene `29`
  - `Miss Pepper` / `Professor von Nostrand` / book discussion
  - this is much closer to episode truth than the weak stand-up scenes

So this is not a failed cognition architecture. It is a mostly working interpretation layer with a poor fallback topic extractor.

## Scene-Type Breakdown

### Dialogue-heavy scenes

These mostly remain usable when transcript contains strong explicit nouns:

- `nose job`
- `Hawaii`
- `crop circles`
- `Kramer`
- `Audrey`

Quality still drops when the transcript lacks those strong nouns and the model falls back to brittle n-gram fragments.

### Environment-heavy scenes

Visual settings remain conservative:

- `kitchen`
- `couch`
- `table`
- `restaurant`

That is acceptable as additive retrieval context, but too often it dominates when the transcript should dominate.

### Low-signal scenes

Low-signal handling is still too permissive.

Scene `37` should likely have fallen back to a minimal payload rather than `Conversation about stage.`

### Strong identity candidates

Identity rails remain conservative:

- `candidate_visible_people` stays anonymous
- named people come from dialogue mention surfaces, not from the LLM

That is still the right behavior.

### Ambiguous scenes

The weak extractor struggles hardest in ambiguous scenes with:

- open-ended dialogue
- short transcript bursts
- figurative language
- stage performance framing

These are exactly the scenes where a stricter fallback should win over a low-confidence topic phrase.

## Comparison To Earlier Validated Runs

Compared with the validated `03x03` and the five-episode campaign on `03x04`-`03x08`, `03x09` introduces a different weakness:

- not social-role invention
- not unsupported relationship language
- not generic `people talk` filler

Instead:

- transcript fragments are too readily promoted to canonical additive context

That means the previous fixes held. We are dealing with a new edge class, not a rollback of prior wins.

## Best Next Steps

### 1. Tighten transcript-topic extraction before touching the gate

Best next fix is in `steps/common/context_analyzer_llm.py`.

Priority changes:

- stop using naive bigram/unigram fallback when the resulting phrases are not semantically stable
- prefer named entities and explicit noun phrases over arbitrary adjacent-token pairs
- raise the threshold for accepting transcript-derived topic hints in stand-up scenes

### 2. Make stand-up / monologue routing more aggressive

For scenes with:

- stage or curtain visual evidence
- one-speaker-dominant transcript
- low-value extracted topic hints

prefer a deterministic monologue fallback such as:

- `Spoken monologue about prescription labels.`
- `Spoken monologue about crop circles.`

instead of `Conversation about half feet.`

### 3. Strengthen low-signal fallback for short transcript scenes

For scenes like `37`:

- transcript length is near-zero
- visual signal is generic
- no concrete topic is recoverable

The system should choose:

- `Minimal visual or dialogue content.`

instead of inventing a conversational topic.

### 4. Keep the gate unchanged for the moment

The current gate is still directionally useful.

It did not miss that the episode remained below the quality bar. The deeper issue is that many low-quality outputs are currently *not* generic enough to trigger the gate consistently, which suggests a future audit-only metric may be useful. But the right first patch is analyzer quality, not a softer gate.

## Bottom Line

`03x09` is a good failure.

It proves:

- runtime is stable
- additive interpretation still persists correctly
- the new epistemic payload is useful
- old hallucination classes stayed fixed

It also gives a clean next target:

- make transcript-topic extraction more selective
- make monologue and low-signal fallbacks more aggressive

This is a smaller, better problem than the one we had before.
