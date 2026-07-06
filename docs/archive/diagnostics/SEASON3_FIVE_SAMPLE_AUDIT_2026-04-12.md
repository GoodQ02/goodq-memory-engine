<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-12 -->

# Season 3 Five-Sample Audit

## Scope

- Treatment epoch: `epoch_2025_12_23`
- Campaign run root: `reports/fresh_ingest_runs/20260411_194713_season3_feature_ladder/`
- Feature under audit: `scene_context_llm`
- Supplemental goal: verify output consistency using five deliberately chosen
  scene types instead of random spot checks

Audit categories:

1. dialogue-heavy
2. environment-heavy
3. edge-case / low signal
4. strong identity candidate
5. ambiguous scene

The purpose of this audit is to pressure-test the cognitive layer from five
different angles after the full five-episode treatment campaign passed.

## Selection Map

- `03x04 - The Dog` -> dialogue-heavy
- `03x05 - The Library` -> strong identity candidate
- `03x06 - The Parking Garage` -> environment-heavy
- `03x07 - The Cafe` -> ambiguous scene
- `03x08 - The Tape` -> edge-case / low signal

## 1. Dialogue-Heavy Audit

Episode:
- `03x04 - The Dog`

Scene:
- `24`

Why this scene:
- long transcript
- multiple speakers
- competing local topics
- easy place for the model to flatten into generic room talk

Evidence:
- caption:
  - `a man and woman standing in a kitchen`
- transcript anchor:
  - `how about if you and George go to the movies and I stay here and watch the dog tonight?`
  - `What about prognosis negative?`
- output summary:
  - `Kitchen conversation about prognosis negative.`
- output tags:
  - `kitchen`
  - `movie plan`
  - `dog`
  - `TV show`
  - `prognosis negative`

Assessment:
- pass
- The layer keeps the scene grounded in the real spoken topics instead of
  collapsing into vague domestic chatter.
- The tags are retrieval-useful and correctly reflect both location and topic.

Minor watch-point:
- The phrasing is terse, but it is honest and grounded.

## 2. Strong Identity Candidate Audit

Episode:
- `03x05 - The Library`

Scene:
- `18`

Why this scene:
- transcript strongly names a concrete identity candidate:
  - `Bookman`
- interaction dominance is stable and strong
- easy place for the layer to over-promote identity or invent social framing

Evidence:
- caption:
  - `a man in a suit and tie is sitting at a desk`
- transcript anchor:
  - `Look, Mr. Bookman, I returned that book.`
  - `Bad year for libraries. Bad year for America.`
- output summary:
  - `Conversation about bad year.`
- output tags:
  - `desk`
  - `book`
  - `sitting`
  - `reading`
  - `bad year`
- interaction dominance:
  - `speaker_id = SPEAKER_00`
  - `confidence = strong`
  - `dominant_share = 1.0`

Assessment:
- pass with caution
- The cognition layer stays non-authoritative and does not mutate identity
  truth, which is correct.
- It avoids inventing roles or social relationships.
- This is a good example of the system respecting the identity boundary.

Minor watch-point:
- The topic abstraction is slightly underpowered here.
- `Bookman` is transcript-supported and may be a candidate for future
  non-authoritative mention retention, but only if we preserve the current
  additive contract.

## 3. Environment-Heavy Audit

Episode:
- `03x06 - The Parking Garage`

Scene:
- `6`

Why this scene:
- highly environment-driven episode
- multiple cars, boxes, and garage signals
- easy place for the layer to invent personal narrative instead of spatial
  context

Evidence:
- caption:
  - `two men carrying boxes in a parking garage`
- object evidence:
  - `person`
  - `person`
  - `car`
  - `car`
- transcript anchor:
  - `you better find this car`
  - `I have to go to the bathroom`
- output summary:
  - `Two men carrying boxes in a parking garage discuss their plans.`
- output tags:
  - `parking garage`
  - `men`
  - `boxes`
  - `car`

Assessment:
- pass
- The layer correctly preserves the episode's environmental spine.
- It does not drift into unsupported interpersonal claims.
- This is exactly the kind of scene where a retrieval layer should preserve
  place and logistical tension first.

Minor watch-point:
- `thought came`-style residue is gone here, but environment scenes still
  benefit from pruning low-value visual filler over time.

## 4. Ambiguous Scene Audit

Episode:
- `03x07 - The Cafe`

Scene:
- `2`

Why this scene:
- caption is weak and generic:
  - two men by a sign
- transcript provides the real topic:
  - IQ test / guinea pig / research project
- good test of transcript-over-caption priority

Evidence:
- caption:
  - `two men standing in front of a sign`
- transcript anchor:
  - `She wants me to take an IQ test.`
  - `It's part of a research project, so I have to be a guinea pig.`
- output summary:
  - `Two men stand in front of a sign, facing each other, and discuss their intentions regarding an IQ test.`
- output tags:
  - `sign`
  - `men`
  - `intentionality`
  - `IQ test`
  - `guinea pig`

Assessment:
- pass
- The scene is correctly disambiguated by transcript rather than by caption.
- The layer surfaces the real semantic topic and ignores the temptation to
  narrativize the sign or street setting.

Minor watch-point:
- `intentionality` is more abstract than ideal.
- The topic is still right, but a future polish pass could favor plainer tags
  like `education test` or `research test`.

## 5. Edge-Case / Low-Signal Audit

Episode:
- `03x08 - The Tape`

Scene:
- `39`

Why this scene:
- short transcript
- stand-up style closing material
- sparse visual evidence
- easy place for the model to hallucinate or over-literalize

Evidence:
- caption:
  - `a man in a suit and tie standing on a stage`
- transcript anchor:
  - `what are you doing later by the ruptured remains of the fuselage?`
  - `About some peanuts over by the black box`
- output summary:
  - `Conversation about doing later.`
- output tags:
  - `stage`
  - `speech`
  - `surprise`
  - `doing later`
  - `ruptured remains`
- visible-presence signal:
  - `anonymous_person_1`
  - `confidence = supported`

Assessment:
- conditional pass
- The important success is negative:
  - it does not hallucinate a literal plane crash scene
  - it does not invent extra people or narrative action
- For low-signal stand-up material, containment matters more than elegance.

Minor watch-point:
- The phrasing is still awkward and overly literal.
- This is acceptable as an edge-case behavior, but not yet polished prose.

## Final Read

This five-scene audit supports the campaign-level conclusion:

- the cognition layer is stable across multiple scene types
- transcript priority is working
- unsupported social-role invention is controlled
- low-signal scenes are contained instead of amplified
- environment-heavy scenes retain place and logistics

## What This Adds Beyond the Campaign Memo

The campaign memo proves:
- batch-level stability
- pass/fail discipline
- broad semantic consistency

This sample audit proves:
- the layer is holding under qualitatively different scene shapes
- the system is not only passing on averages
- the cognition layer is behaving correctly in both strong-signal and
  awkward-signal conditions

## Remaining Minor Watch-List

Not blockers, but still worth tracking:

- occasional abstract tags such as `intentionality`
- some summaries are still intentionally dry enough to feel underwritten
- low-signal stand-up scenes remain contained but not elegant

These are polish issues, not correctness issues.
