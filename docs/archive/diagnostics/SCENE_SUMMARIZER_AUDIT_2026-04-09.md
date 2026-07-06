<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-09 -->

# Scene Summarizer Audit

This memo records a targeted, read-only audit of the canonical scene summarization surface:

- [scene_summarizer.py](../../steps/common/scene_summarizer.py)
- [memory.py](../../steps/common/memory.py)
- [apply_scene_summaries.py](../../scripts/apply_scene_summaries.py)
- fresh scene truth from current processing outputs

Goal:
- determine whether `scene_summarizer.py` is unused, stale, or mismatched against the current scene-memory contract
- identify the smallest safe modernization target before any runtime edits

## Bottom Line

`scene_summarizer.py` is still canonical and should remain active.

The issue is not that it is unwired. The issue is that it still prefers older top-level scene fields, while the current canonical caller in [memory.py](../../steps/common/memory.py) now builds scene metadata with most of the useful audio and keyframe context nested under:

- `scene_meta["keyframe"]`
- `scene_meta["audio"]`

That means the current template summarizer is often missing context that already exists in the scene record.

## Active Call Sites

Confirmed live or intentional callers:

- [memory.py](../../steps/common/memory.py)
  - `register_scene_bundle(...)` imports `generate_scene_summary`
  - canonical runtime uses `generate_scene_summary(..., use_llm=False)`
- [apply_scene_summaries.py](../../scripts/apply_scene_summaries.py)
  - standalone backfill script, not canonical runtime
- active tests:
  - [test_scene_summarizer_semantic_quality.py](../../tests/unit/test_scene_summarizer_semantic_quality.py)

Conclusion:
- not removable
- not experimental
- template path is canonical
- LLM path is secondary / off-path

## Current Canonical Input Shape

From [memory.py](../../steps/common/memory.py), `scene_meta` is assembled like this:

- top level:
  - `index`
  - `start`
  - `end`
  - `duration`
  - optional `confidence`
  - optional `detection`
  - optional `errors`
- nested `keyframe`:
  - `path`
  - `hash`
  - `tags`
  - `entities`
  - `objects`
  - `caption`
  - `ocr_text`
- nested `audio`:
  - `path`
  - `hash`
  - `transcript`
  - `sentiment`
  - `emotions`
  - `tags`
  - `entities`
  - `audio_emotion`
  - optional `transcript_meta`

Fresh processed scene records also show richer nested audio truth such as:

- `audio.emotion`
- `audio.emotion_scores`
- `audio.speaker_transcript`
- `audio.speakers`
- `audio.music_events`
- `audio.time_hints`
- `audio.sentiment.label`
- `audio.sentiment.score`

## What `scene_summarizer.py` Currently Expects

The template summarizer still prefers older top-level fields first:

- `caption`
- `objects`
- `face_count`
- `transcript`
- `speakers`
- `speaker_transcript`
- `sentiment_label`
- `sentiment_score`
- `emotions`
- `dominant_emotion`

It only partially falls back into nested audio:

- `audio.emotions`
- `audio.sentiment`
- `audio.audio_emotion`

The current fallback logic is incomplete for present-day scene truth.

## Concrete Mismatches

### 1. Visual fields are read from the wrong level first

The summarizer expects:

- `scene_meta["caption"]`
- `scene_meta["objects"]`
- `scene_meta["face_count"]`

But the canonical caller stores the main visual payload under:

- `scene_meta["keyframe"]["caption"]`
- `scene_meta["keyframe"]["objects"]`

Impact:
- summaries can underreport visual context even when keyframe truth exists

### 2. Transcript and speaker context are mostly nested now

The summarizer expects:

- `scene_meta["transcript"]`
- `scene_meta["speakers"]`
- `scene_meta["speaker_transcript"]`

But fresh scene records commonly keep them under:

- `scene_meta["audio"]["transcript"]`
- `scene_meta["audio"]["speakers"]`
- `scene_meta["audio"]["speaker_transcript"]`

Impact:
- summaries can miss dialogue and speaker context on canonical scene payloads

### 3. Sentiment shape is stale

The summarizer prefers:

- `sentiment_label`
- `sentiment_score`

But fresh audio payloads use:

- `audio.sentiment.label`
- `audio.sentiment.score`

Current fallback:
- `audio_meta.get("sentiment", sentiment_label)` can return a dict, not a label string

Impact:
- sentiment text can be wrong, suppressed, or poorly formatted

### 4. Emotion shape is stale

The summarizer supports:

- `emotions` as a list of `{label, score}`
- `dominant_emotion` as a simple string

But fresh audio payloads commonly use:

- `audio.emotion` as a string
- `audio.emotion_scores` as a dict of label -> score
- `audio.audio_emotion` as a string compatibility field

Current fallback still assumes `audio.audio_emotion` may be a list of dicts.

Impact:
- summaries can miss the dominant emotion even when canonical scene audio already contains it

### 5. The LLM path is not canonical

[memory.py](../../steps/common/memory.py) calls:

- `generate_scene_summary(scene_meta, cfg, use_llm=False)`

So the local-LLM summary path in [scene_summarizer.py](../../steps/common/scene_summarizer.py) is currently not part of canonical ingestion behavior.

It also still assumes:

- raw `requests.post(...)`
- direct `llm.api_url`
- a local chat endpoint default

Impact:
- this path should not be treated as production truth until deliberately adopted

## Why This Matters

This is a high-value target because it is:

- canonical
- active on every scene bundle registration
- currently underpowered relative to the actual scene truth already available

In other words:

- the system already knows more than the summary says
- fixing the summary is likely a small, high-leverage modernization

## Recommended Next Change

Do not replace the summarizer.

Do a surgical modernization of the template path only:

1. Normalize current scene payloads inside `generate_scene_summary_template(...)`
   - read `keyframe.caption` and `keyframe.objects`
   - read `audio.transcript`, `audio.speakers`, `audio.speaker_transcript`
   - read `audio.sentiment.label` / `audio.sentiment.score`
   - read `audio.emotion` / `audio.emotion_scores` / compatibility `audio.audio_emotion`

2. Keep the output semantics the same
   - concise deterministic scene summary
   - no new LLM dependency

3. Leave `generate_scene_summary_llm(...)` alone for now
   - it is not the canonical path
   - modernizing it should be a separate decision

4. Expand tests against current payload shapes
   - nested `keyframe`
   - nested `audio`
   - string `audio_emotion`
   - dict `audio.sentiment`

## Not Recommended Yet

- do not remove `scene_summarizer.py`
- do not route canonical ingestion through the LLM summary path
- do not merge this with `scene_context_llm`
- do not redesign summary semantics while we are still validating the current scene-memory truth model

## Short Version

`scene_summarizer.py` is still live and valuable, but it is summarizing an older version of the scene schema.

The best next move is a small template-only modernization so the summary reflects the scene truth we already have today.
